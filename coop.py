"""Multijoueur LAN en coopération sur le Déferlement.

Architecture hôte-autoritaire, sans thread ni dépendance externe :

- L'HÔTE (`CoopHostGame`) fait tourner la vraie partie (vagues, IA,
  portes, objets). Il reçoit la position et les tirs des clients,
  résout leurs balles contre SES ennemis, et diffuse ~15 fois par
  seconde un instantané complet (joueurs, ennemis, objets, vague).
- Le CLIENT (`CoopClientGame`) simule localement son propre joueur
  (déplacements, collisions, arme) pour une visée sans latence, et
  affiche le reste du monde d'après les instantanés (les ennemis sont
  des "fantômes" interpolés). Sa vie est décidée par l'hôte.

Un joueur mort réapparaît au point de départ après quelques secondes ;
la partie n'est perdue que si TOUS les joueurs sont morts en même temps.
"""

import math
import random

import pygame

from entities import ENEMY_TYPES, Pickup, Player, Prop, RemotePlayer
from game import GUNSHOT_HEARING, SLOT_SCANCODES, new_stats
from hud import HUD
from level import SURVIVAL_LEVEL, Level
from network import DEFAULT_PORT, UdpPeer
from particles import ParticleSystem
from raycaster import Raycaster, cast_ray, zoom_screen
from survival import SurvivalGame

RESPAWN_DELAY = 6.0        # secondes avant la réapparition d'un joueur
CLIENT_TIMEOUT = 6.0       # silence au-delà duquel l'hôte oublie un client
SNAP_INTERVAL = 1 / 15     # fréquence des instantanés de l'hôte
SEND_INTERVAL = 1 / 30     # fréquence d'envoi des entrées du client
JOIN_TIMEOUT = 5.0         # délai de connexion avant abandon
LOST_TIMEOUT = 5.0         # silence de l'hôte = connexion perdue


def _revive(entity, health):
    """Ressuscite une entité billboard (restaure la taille du sprite)."""
    entity.health = health
    entity.SPRITE_HEIGHT = type(entity).SPRITE_HEIGHT
    entity.exploded = False


# ----------------------------------------------------------------------
# Hôte
# ----------------------------------------------------------------------
class CoopHostGame(SurvivalGame):
    """Le Déferlement, hébergé : partie locale + service des clients."""

    def __init__(self, screen, settings, sounds, carry_player=None,
                 port=DEFAULT_PORT):
        super().__init__(screen, settings, sounds, carry_player=carry_player)
        self.peer = UdpPeer(port)
        self.clients = {}          # pid -> {"addr", "player", "last_seen"}
        self.respawns = {}         # pid -> compte à rebours de réapparition
        self.next_pid = 1
        self.net_events = []       # événements du prochain instantané
        self.net_time = 0.0        # horloge réseau (avance même en pause)
        self.snap_timer = 0.0
        self._next_enemy_id = 0

    # -- hooks du Game de base -----------------------------------------
    def spawn_enemy(self, kind, x, y, hp_mult=1.0, dmg_mult=1.0):
        enemy = super().spawn_enemy(kind, x, y, hp_mult, dmg_mult)
        enemy.net_id = self._next_enemy_id
        self._next_enemy_id += 1
        return enemy

    def _all_players(self):
        return [self.player] + [c["player"] for c in self.clients.values()]

    def _ai_target(self, enemy):
        """Chaque ennemi harcèle le joueur vivant le plus proche."""
        candidates = [p for p in self._all_players() if p.alive]
        if not candidates:
            return self.player
        return min(candidates, key=lambda p: math.hypot(p.x - enemy.x,
                                                        p.y - enemy.y))

    def _extra_sprites(self):
        return list(c["player"] for c in self.clients.values())

    def _check_outcome(self):
        """Défaite seulement quand TOUS les joueurs sont à terre."""
        if all(not p.alive for p in self._all_players()):
            self.outcome = "dead"

    def _check_pickups(self):
        super()._check_pickups()   # le joueur hôte
        for pid, client in self.clients.items():
            self._check_remote_pickups(pid, client["player"])

    def _check_remote_pickups(self, pid, remote):
        if not remote.alive:
            return
        for index, pickup in enumerate(self.pickups):
            if pickup.taken or math.hypot(pickup.x - remote.x,
                                          pickup.y - remote.y) > 0.55:
                continue
            if pickup.kind == "medkit":
                if remote.health >= remote.max_health:
                    continue
                remote.health = min(remote.max_health, remote.health + 35)
            elif pickup.kind == "lifepack":
                if remote.health >= remote.max_health:
                    continue
                remote.health = remote.max_health
                self.particles.spawn_heal_burst(pickup.x, pickup.y)
            else:
                weapon_id = pickup.kind.split(":", 1)[1]
                self.net_events.append(["wpk", pid, weapon_id,
                                        pickup.level_index])
            pickup.taken = True

    def _explode(self, enemy):
        if not enemy.exploded:
            self.net_events.append(["ex", round(enemy.x, 2),
                                    round(enemy.y, 2)])
        super()._explode(enemy)

    # -- boucle ----------------------------------------------------------
    def update(self, dt):
        self.net_time += dt
        self._net_receive()
        super().update(dt)
        self._update_respawns(dt)
        self._prune_clients()
        self.snap_timer -= dt
        if self.snap_timer <= 0.0:
            self.snap_timer = SNAP_INTERVAL
            self._broadcast()

    def _net_receive(self):
        for message, addr in self.peer.receive():
            kind = message.get("t")
            if kind == "join":
                self._handle_join(addr)
            elif kind == "in":
                self._handle_input(message, addr)

    def _handle_join(self, addr):
        for pid, client in self.clients.items():
            if client["addr"] == addr:      # re-join du même client
                self.peer.send({"t": "welcome", "id": pid}, addr)
                return
        pid = self.next_pid
        self.next_pid += 1
        x, y = self.level.player_spawn
        self.clients[pid] = {
            "addr": addr,
            "player": RemotePlayer(pid, x + random.uniform(-0.3, 0.3), y),
            "last_seen": self.net_time,
        }
        self.peer.send({"t": "welcome", "id": pid}, addr)
        self.hud.show_message(f"Joueur {pid + 1} a rejoint la partie")

    def _handle_input(self, message, addr):
        client = self.clients.get(message.get("id"))
        if client is None or client["addr"] != addr:
            return
        client["last_seen"] = self.net_time
        remote = client["player"]
        if remote.alive:
            remote.moving = (abs(remote.x - message["x"])
                             + abs(remote.y - message["y"])) > 0.01
            remote.x = float(message["x"])
            remote.y = float(message["y"])
            remote.angle = float(message["a"])
            for angle, damage in message.get("fx", []):
                self._resolve_remote_fire(message["id"], remote,
                                          float(angle), int(damage))

    def _resolve_remote_fire(self, pid, remote, angle, damage):
        remote.flash_timer = 0.12   # les autres voient l'éclair de tir
        result = self._hitscan(remote.x, remote.y, angle, damage)
        if result is not None:
            self.net_events.append(["hm", pid, 1 if result == "kill" else 0])
        self._alert_allies((remote.x, remote.y), GUNSHOT_HEARING)

    def _update_respawns(self, dt):
        for pid, entity in [(0, self.player)] + [
                (pid, c["player"]) for pid, c in self.clients.items()]:
            if entity.alive:
                self.respawns.pop(pid, None)
                continue
            timer = self.respawns.get(pid, RESPAWN_DELAY) - dt
            if timer <= 0.0 and self.outcome is None:
                x, y = self.level.player_spawn
                x += random.uniform(-0.3, 0.3)
                if pid == 0:
                    self.player.health = 60
                    self.player.x, self.player.y = x, y
                else:
                    entity.x, entity.y = x, y
                    _revive(entity, 60)
                self.net_events.append(["rs", pid, round(x, 2), round(y, 2)])
                self.respawns.pop(pid, None)
            else:
                self.respawns[pid] = timer

    def _prune_clients(self):
        for pid in [p for p, c in self.clients.items()
                    if self.net_time - c["last_seen"] > CLIENT_TIMEOUT]:
            del self.clients[pid]
            self.respawns.pop(pid, None)

    def _broadcast(self):
        players = [[0, round(self.player.x, 2), round(self.player.y, 2),
                    round(self.player.angle, 3), self.player.health,
                    int(getattr(self, "player_moving", False)),
                    int(self.hud.flash > 0)]]
        for pid, client in self.clients.items():
            remote = client["player"]
            players.append([pid, round(remote.x, 2), round(remote.y, 2),
                            round(remote.angle, 3), remote.health,
                            int(remote.moving), int(remote.flash_timer > 0)])
        enemies = [[e.net_id, e.KIND, round(e.x, 2), round(e.y, 2),
                    round(e.angle, 3), e.health, int(e.moving),
                    int(e.flash_timer > 0), int(e.aiming)]
                   for e in self.enemies if e.net_id is not None]
        snapshot = {
            "t": "snap",
            "pl": players,
            "en": enemies,
            "pk": [int(p.taken) for p in self.pickups],
            "wv": self.survival_info(),
            "ov": self.outcome or "",
            "ev": self.net_events,
        }
        for client in self.clients.values():
            self.peer.send(snapshot, client["addr"])
        self.net_events = []

    # -- rendu -----------------------------------------------------------
    def draw(self, screen):
        super().draw(screen)
        if not self.player.alive and self.outcome is None:
            self.hud.draw_dead_overlay(screen)

    def close(self):
        self.peer.close()


# ----------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------
class CoopClientGame:
    """Vue cliente : joueur local réactif, monde piloté par l'hôte.

    Expose la même interface que `Game` pour la boucle de `main.py`
    (handle_event / update / draw / finished / outcome / stats / wave).
    """

    def __init__(self, screen, settings, sounds, host_ip, port=DEFAULT_PORT):
        self.settings = settings
        self.sounds = sounds
        self.level = Level(4, config=SURVIVAL_LEVEL)
        self.level_index = 4
        self.player = Player(*self.level.player_spawn)
        self.player.add_weapon("shotgun", 1)
        self.player.add_weapon("rifle", 1)
        self.player.select_weapon(2)
        self.player.activate_shield()  # invulnérabilité le temps de s'orienter
        self.pickups = [Pickup(x, y, kind, 1)
                        for x, y, kind in self.level.pickup_spawns]
        self.props = [Prop(x, y, kind)
                      for x, y, kind in self.level.prop_spawns]

        self.particles = ParticleSystem()
        self.raycaster = Raycaster(screen.get_size(), self.level)
        self.hud = HUD(screen.get_size())
        self.stats = new_stats()
        self.paused = False
        self.outcome = None
        self.end_delay = 0.0
        self.time = 0.0
        self.shake = 0.0
        self.show_fps = False
        self.fps = 60.0
        self.sparkle_timer = 0.0
        self.step_distance = 0.0
        self.step_side = False

        # Réseau
        self.peer = UdpPeer()
        self.host_addr = (host_ip, port)
        self.pid = None
        self.join_wait = 0.0
        self.join_resend = 0.0
        self.last_snap = 0.0
        self.disconnected = False
        self.pending_fires = []    # [[angle, dégâts], ...] à envoyer
        self.send_timer = 0.0

        # Monde répliqué
        self.ghosts = {}           # net_id -> ennemi fantôme
        self.allies = {}           # pid -> RemotePlayer
        self.wave_info = {"wave": 0, "final": 30, "remaining": 0,
                          "next_in": 0.0, "intermission": True}
        self.synced = False        # premier instantané reçu
        pygame.mouse.get_rel()

    @property
    def wave(self):
        return self.wave_info["wave"]

    @property
    def finished(self):
        return self.outcome is not None and self.end_delay > 0.8

    def resize(self, size):
        """Adapte le client répliqué après un changement de mode vidéo."""
        self.raycaster.resize(size)
        self.hud.resize(size)

    def survival_info(self):
        return self.wave_info

    # -- événements -------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.paused = not self.paused
                pygame.mouse.get_rel()
            elif self.paused and event.key == pygame.K_m:
                return "menu"
            elif event.key == pygame.K_F3:
                self.show_fps = not self.show_fps
            elif event.key == self.settings.keys["recharger"]:
                self.player.weapon.start_reload()
                if self.player.weapon.reloading > 0.0:
                    self.sounds.play("reload")
            elif event.scancode in SLOT_SCANCODES:
                if self.player.select_weapon(SLOT_SCANCODES[event.scancode]):
                    self.sounds.play("click", volume_scale=0.4)
        elif event.type == pygame.MOUSEWHEEL and not self.paused:
            # Voir game.py : rétablit le sens de la molette en défilement
            # "naturel" (event.flipped) et ignore les molettes horizontales.
            wheel_y = -event.y if getattr(event, "flipped", False) else event.y
            if wheel_y:
                self.player.cycle_weapon(-1 if wheel_y > 0 else 1)
                self.sounds.play("click", volume_scale=0.4)
        elif event.type == pygame.MOUSEBUTTONDOWN and not self.paused \
                and self.player.alive:
            if event.button == 1:
                self._fire()
            elif event.button == 3:              # clic droit : mise en joue
                self.player.aiming = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.player.aiming = False
        return None

    # -- boucle -------------------------------------------------------------
    def update(self, dt):
        self.time += dt
        self.fps = self.fps * 0.95 + (1.0 / max(dt, 1e-4)) * 0.05
        self.shake = max(0.0, self.shake - dt * 3.5)
        self._net_receive()
        self._ensure_joined(dt)
        if self.disconnected or (self.outcome is not None
                                 and self.end_delay > 0.8):
            return
        if self.outcome is not None:
            self.end_delay += dt

        player = self.player
        if player.alive and not self.paused and self.outcome is None:
            self.stats["time"] += dt
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            if self.settings.invert_mouse:
                mouse_dx, mouse_dy = -mouse_dx, -mouse_dy   # option : souris inversée
            player.rotate(mouse_dx, mouse_dy, self.settings.mouse_factor())
            keys = pygame.key.get_pressed()
            old_x, old_y = player.x, player.y
            moving = player.move(dt, keys, self.settings.keys, self.level)
            self.step_distance += math.hypot(player.x - old_x,
                                             player.y - old_y)
            if self.step_distance > 1.05:
                self.step_distance = 0.0
                self.step_side = not self.step_side
                self.sounds.play("step" if self.step_side else "step2",
                                 volume_scale=0.35)
            if pygame.mouse.get_pressed()[0] and player.weapon.spec.automatic:
                self._fire()
            player.update(dt)
            self.hud.update(dt, moving)

        # Fantômes : interpolation douce vers les positions de l'hôte.
        for ghost in self.ghosts.values():
            blend = min(1.0, dt * 10)
            ghost.x += (ghost.net_x - ghost.x) * blend
            ghost.y += (ghost.net_y - ghost.y) * blend
            ghost.update_timers(dt)
        for ally in self.allies.values():
            blend = min(1.0, dt * 10)
            ally.x += (ally.net_x - ally.x) * blend
            ally.y += (ally.net_y - ally.y) * blend
            ally.update_timers(dt)

        # Portes simulées localement (mêmes règles que l'hôte).
        movers = ([player] + [g for g in self.ghosts.values() if g.alive]
                  + [a for a in self.allies.values() if a.alive])
        for door_pos in self.level.update_doors(dt, movers):
            self.sounds.play("door", volume_scale=0.7,
                             pos=door_pos, listener=player)

        self._emit_sparkles(dt)
        self.particles.update(dt)
        self._net_send(dt)

    # -- tir local ------------------------------------------------------
    def _fire(self):
        weapon = self.player.weapon
        if not weapon.fire():
            return
        self.sounds.play(weapon.spec.sound, volume_scale=0.9)
        self.hud.on_player_shot()
        if weapon.spec.id in ("shotgun", "minigun"):
            self.shake = min(1.0, self.shake + 0.18)
        self.stats["shots"] += 1
        spread = weapon.spec.spread * (1.0 - 0.75 * self.player.ads)
        for _ in range(weapon.spec.pellets):
            angle = self.player.angle + random.uniform(-spread, spread)
            self.pending_fires.append([round(angle, 4), weapon.damage])
            # Poussière d'impact locale (l'hôte décide des vrais dégâts).
            wall_dist, _, _, _ = cast_ray(self.level, self.player.x,
                                          self.player.y, angle)
            hx = self.player.x + math.cos(angle) * (wall_dist - 0.05)
            hy = self.player.y + math.sin(angle) * (wall_dist - 0.05)
            self.particles.spawn_wall_dust(hx, hy, (110, 110, 110))

    # -- réseau -----------------------------------------------------------
    def _ensure_joined(self, dt):
        if self.pid is None:
            self.join_wait += dt
            self.join_resend -= dt
            if self.join_resend <= 0.0:
                self.join_resend = 0.7
                self.peer.send({"t": "join"}, self.host_addr)
            if self.join_wait > JOIN_TIMEOUT:
                self.disconnected = True
        elif self.time - self.last_snap > LOST_TIMEOUT:
            self.disconnected = True

    def _net_send(self, dt):
        if self.pid is None:
            return
        self.send_timer -= dt
        if self.send_timer > 0.0 and not self.pending_fires:
            return
        self.send_timer = SEND_INTERVAL
        self.peer.send({
            "t": "in", "id": self.pid,
            "x": round(self.player.x, 3), "y": round(self.player.y, 3),
            "a": round(self.player.angle, 3),
            "fx": self.pending_fires,
        }, self.host_addr)
        self.pending_fires = []

    def _net_receive(self):
        for message, addr in self.peer.receive():
            if addr[0] != self.host_addr[0]:
                continue
            kind = message.get("t")
            if kind == "welcome":
                self.pid = int(message["id"])
            elif kind == "snap" and self.pid is not None:
                self.last_snap = self.time
                self._apply_snapshot(message)

    def _apply_snapshot(self, snap):
        self._apply_players(snap["pl"])
        self._apply_enemies(snap["en"])
        for pickup, taken in zip(self.pickups, snap["pk"]):
            pickup.taken = bool(taken)
        self._apply_wave(snap["wv"])
        for event in snap["ev"]:
            self._apply_event(event)
        if snap["ov"] and self.outcome is None:
            self.outcome = snap["ov"]
        self.synced = True

    def _apply_players(self, players):
        seen = set()
        for pid, x, y, angle, health, moving, flash in players:
            if pid == self.pid:
                # Sa propre vie est décidée par l'hôte.
                if health < self.player.health:
                    self.player.take_damage(self.player.health - health)
                    self.sounds.play("player_hit")
                    self.shake = min(1.0, self.shake + 0.5)
                else:
                    self.player.health = health
                continue
            seen.add(pid)
            ally = self.allies.get(pid)
            if ally is None:
                ally = RemotePlayer(pid, x, y)
                ally.net_x, ally.net_y = x, y
                self.allies[pid] = ally
                if self.synced:
                    self.hud.show_message(f"Joueur {pid + 1} a rejoint la partie")
            ally.net_x, ally.net_y = x, y
            ally.angle = angle
            ally.moving = bool(moving)
            if flash and ally.flash_timer <= 0.0:
                ally.flash_timer = 0.12
                self.sounds.play("player_shot", volume_scale=0.5,
                                 pos=(ally.x, ally.y), listener=self.player)
            if health <= 0 and ally.alive:
                ally.take_damage(10 ** 6)
                self.particles.spawn_death(ally.x, ally.y)
            elif health > 0 and not ally.alive:
                _revive(ally, health)
            else:
                ally.health = health
        for pid in [p for p in self.allies if p not in seen]:
            del self.allies[pid]

    def _apply_enemies(self, enemies):
        seen = set()
        for data in enemies:
            # Le dernier champ (visée) a été ajouté sans casser les hôtes
            # plus anciens : un instantané à 8 champs reste accepté.
            net_id, kind, x, y, angle, health, moving, flash = data[:8]
            aiming = bool(data[8]) if len(data) > 8 else False
            seen.add(net_id)
            ghost = self.ghosts.get(net_id)
            if ghost is None:
                ghost = ENEMY_TYPES[kind](x, y)
                ghost.net_x, ghost.net_y = x, y
                self.ghosts[net_id] = ghost
                if self.synced:
                    self.particles.spawn_portal(x, y)
                    self.sounds.play("spawn", volume_scale=0.8,
                                     pos=(x, y), listener=self.player)
            ghost.net_x, ghost.net_y = x, y
            ghost.angle = angle
            ghost.moving = bool(moving)
            ghost.aiming = aiming
            if not aiming:
                ghost.aim_timer = 0.0
            if flash and ghost.flash_timer <= 0.0:
                ghost.flash_timer = 0.12
                self.sounds.play("enemy_shot", volume_scale=0.9,
                                 pos=(ghost.x, ghost.y), listener=self.player)
            if health <= 0 and ghost.alive:
                ghost.take_damage(10 ** 6)
                self.particles.spawn_death(ghost.x, ghost.y)
                self.sounds.play("enemy_die", volume_scale=0.8,
                                 pos=(ghost.x, ghost.y), listener=self.player)
            elif 0 < health < ghost.health:
                self.particles.spawn_blood(ghost.x, ghost.y)
                ghost.hurt_timer = 0.09   # flash blanc de l'impact
                ghost.health = health
            else:
                ghost.health = max(0, health)
        for net_id in [n for n in self.ghosts if n not in seen]:
            del self.ghosts[net_id]

    def _apply_wave(self, wave_info):
        if wave_info["wave"] > self.wave_info["wave"] and self.synced:
            self.sounds.play("wave", volume_scale=0.9)
            self.hud.announce(f"VAGUE {wave_info['wave']}")
        self.wave_info = wave_info

    def _apply_event(self, event):
        kind = event[0]
        if kind == "ex":
            _, x, y = event
            self.particles.spawn_explosion(x, y)
            self.sounds.play("explosion", pos=(x, y), listener=self.player)
            if math.hypot(x - self.player.x, y - self.player.y) < 5:
                self.shake = min(1.0, self.shake + 0.5)
        elif kind == "hm" and event[1] == self.pid:
            self.stats["hits"] += 1
            self.stats["kills"] += event[2]
            self.hud.on_enemy_hit(killed=bool(event[2]))
        elif kind == "rs" and event[1] == self.pid:
            self.player.x, self.player.y = event[2], event[3]
            self.player.health = 60
            self.hud.show_message("Vous êtes de retour dans la bataille !")
        elif kind == "wpk" and event[1] == self.pid:
            _, _, weapon_id, level = event
            self.player.add_weapon(weapon_id, level)
            self.sounds.play("pickup")
            weapon = next(w for w in self.player.weapons
                          if w.spec.id == weapon_id)
            self.hud.show_message("Arme récupérée : " + weapon.display_name)

    def _emit_sparkles(self, dt):
        self.sparkle_timer -= dt
        if self.sparkle_timer > 0.0:
            return
        self.sparkle_timer = 0.22
        for pickup in self.pickups:
            if pickup.kind == "lifepack" and not pickup.taken:
                self.particles.spawn_heal_sparkle(pickup.x, pickup.y)

    # -- rendu -------------------------------------------------------------
    def draw(self, screen):
        sprites = (list(self.ghosts.values()) + list(self.allies.values())
                   + self.props)
        for pickup in self.pickups:
            if not pickup.taken:
                pickup.v_offset = 0.12 + pickup.bob_offset(self.time)
                sprites.append(pickup)

        pitch_px = int(self.player.pitch * self.raycaster.height)
        if self.shake > 0.0:
            pitch_px += int(random.uniform(-1, 1) * self.shake
                            * self.raycaster.height * 0.02)
        self.raycaster.render(screen, self.player, self.level, sprites,
                              self.particles, pitch_px)
        if self.player.ads > 0.01:
            zoom_screen(screen, self.player.zoom)   # lunette de visée
        self.hud.draw(screen, self.player, list(self.ghosts.values()),
                      self.level, self.pickups,
                      fps=self.fps if self.show_fps else None,
                      survival=self.wave_info, stats=self.stats)
        if self.pid is None:
            self.hud.show_message("Connexion à l'hôte...")
        if not self.player.alive and self.outcome is None:
            self.hud.draw_dead_overlay(screen)
        if self.paused:
            self.hud.draw_pause(screen)

    def close(self):
        self.peer.close()
