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
import secrets
from collections import deque

import pygame

from entities import (
    ENEMY_TYPES,
    Pickup,
    Player,
    Prop,
    RemotePlayer,
    move_with_entity_collisions,
)
from game import GUNSHOT_HEARING, SLOT_SCANCODES, Game, new_stats
from hud import HUD
from level import SURVIVAL_LEVEL, Level
from network import DEFAULT_PORT, UdpPeer
from particles import ParticleSystem
from raycaster import Raycaster, cast_ray, zoom_screen
from survival import SurvivalGame
from touch_controls import FINGER_EVENTS, TouchControls
from weapons import WEAPON_ORDER, WEAPON_SPECS, Weapon

RESPAWN_DELAY = 6.0        # secondes avant la réapparition d'un joueur
CLIENT_TIMEOUT = 6.0       # silence au-delà duquel l'hôte oublie un client
SNAP_INTERVAL = 1 / 15     # fréquence des instantanés de l'hôte
SEND_INTERVAL = 1 / 30     # fréquence d'envoi des entrées du client
JOIN_TIMEOUT = 5.0         # délai de connexion avant abandon
LOST_TIMEOUT = 5.0         # silence de l'hôte = connexion perdue
MAX_CLIENTS = 3            # quatre joueurs au total, hôte compris
MAX_REMOTE_FIRE_EVENTS = 32
PROTOCOL_VERSION = 2
MAX_RELIABLE_EVENTS = 512
MAX_EVENTS_PER_SNAPSHOT = 128
MOVE_BURST_SECONDS = 0.15
MOVE_JITTER = 0.03


def _starting_remote_weapons():
    """Arsenal coop initial, simulé de façon autoritaire par l'hôte."""
    return {
        weapon_id: Weapon(WEAPON_SPECS[weapon_id], level)
        for weapon_id, level in (
            ("pistol", 0),
            ("shotgun", 1),
            ("rifle", 1),
        )
    }


def _inventory_rows(weapons):
    """Inventaire compact répliqué ; munitions/cadence restent côté hôte."""
    return [
        [weapon_id, weapons[weapon_id].level]
        for weapon_id in WEAPON_ORDER
        if weapon_id in weapons
    ]


def _finite_float(value, low=None, high=None):
    """Convertit une valeur réseau en flottant fini et éventuellement borné."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number):
        return None
    if low is not None and number < low:
        return None
    if high is not None and number > high:
        return None
    return number


def _revive(entity, health):
    """Ressuscite une entité billboard (restaure la taille du sprite)."""
    entity.health = health
    entity.SPRITE_HEIGHT = type(entity).SPRITE_HEIGHT
    entity.exploded = False
    entity.roll_timer = 0.0
    entity.roll_invuln = 0.0
    entity.roll_cooldown = 0.0
    if hasattr(entity, "shield"):
        entity.shield = Player.SHIELD_DURATION


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
        self.event_journal = deque()
        self.event_sequence = 0
        self.session_id = secrets.token_hex(8)
        self.snapshot_sequence = 0
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
        client = self.clients[pid]
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
                self._grant_remote_weapon(
                    client, weapon_id, pickup.level_index,
                )
                self._queue_net_event(
                    ["wpk", pid, weapon_id, pickup.level_index],
                )
            pickup.taken = True

    def _explode(self, enemy):
        if not enemy.exploded:
            self._queue_net_event(
                ["ex", round(enemy.x, 2), round(enemy.y, 2)],
            )
        super()._explode(enemy)

    def _on_enemy_impact(self, enemy, fatal=False):
        """Affiche l'impact côté hôte et le réplique à chaque client."""
        super()._on_enemy_impact(enemy, fatal=fatal)
        if enemy.net_id is not None:
            self._queue_net_event(["ei", enemy.net_id, int(fatal)])

    def _queue_net_event(self, event):
        """Ajoute un événement immédiat et à la file fiable acquittée."""
        if not hasattr(self, "event_journal"):
            self.event_journal = deque()
            self.event_sequence = 0
        self.event_sequence += 1
        self.net_events.append(event)
        self.event_journal.append((self.event_sequence, event))
        while len(self.event_journal) > MAX_RELIABLE_EVENTS:
            self.event_journal.popleft()

    @staticmethod
    def _grant_remote_weapon(client, weapon_id, level):
        """Applique un ramassage à l'inventaire autoritaire du client."""
        weapons = client["weapons"]
        owned = weapons.get(weapon_id)
        if owned is None or level > owned.level:
            weapons[weapon_id] = Weapon(WEAPON_SPECS[weapon_id], level)
        else:
            owned.ammo = owned.spec.magazine_size
            owned.reloading = 0.0
        client["active_weapon"] = weapon_id

    # -- boucle ----------------------------------------------------------
    def update(self, dt):
        self.net_time += dt
        self._net_receive()
        if not self.paused and self.outcome is None:
            for client in self.clients.values():
                client["player"].update_timers(dt)
                for weapon in client["weapons"].values():
                    weapon.update(dt)
        super().update(dt)
        if not self.paused and self.outcome is None:
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
                self._handle_join(message, addr)
            elif kind == "in":
                self._handle_input(message, addr)

    def _handle_join(self, message, addr):
        protocol = (
            PROTOCOL_VERSION
            if message.get("v") == PROTOCOL_VERSION
            else 1
        )
        for pid, client in self.clients.items():
            if client["addr"] == addr:      # re-join du même client
                client["protocol"] = protocol
                self.peer.send({
                    "t": "welcome", "id": pid,
                    "v": PROTOCOL_VERSION, "sid": self.session_id,
                    "es": getattr(self, "event_sequence", 0),
                }, addr)
                return
        if len(self.clients) >= MAX_CLIENTS:
            self.peer.send({"t": "full"}, addr)
            return
        pid = self.next_pid
        self.next_pid += 1
        x, y = self.level.player_spawn
        self.clients[pid] = {
            "addr": addr,
            "player": RemotePlayer(pid, x + random.uniform(-0.3, 0.3), y),
            "last_seen": self.net_time,
            "protocol": protocol,
            "last_input_sequence": -1,
            "last_reload_sequence": 0,
            "event_ack": getattr(self, "event_sequence", 0),
            "move_credit": Player.SPEED * MOVE_BURST_SECONDS + MOVE_JITTER,
            "last_motion_time": self.net_time,
            "last_roll_sequence": 0,
            "pending_roll_sequence": None,
            "legacy_roll_latched": False,
            "weapons": _starting_remote_weapons(),
            "active_weapon": "rifle",
        }
        self.peer.send({
            "t": "welcome", "id": pid,
            "v": PROTOCOL_VERSION, "sid": self.session_id,
            "es": getattr(self, "event_sequence", 0),
        }, addr)
        self.hud.show_message(f"Joueur {pid + 1} a rejoint la partie")

    def _handle_input(self, message, addr):
        pid = message.get("id")
        if isinstance(pid, bool) or not isinstance(pid, int):
            return
        client = self.clients.get(pid)
        if client is None or client["addr"] != addr:
            return

        protocol = client.get("protocol", 1)
        if protocol >= PROTOCOL_VERSION:
            if message.get("sid") != getattr(self, "session_id", None):
                return
            event_ack = message.get("ea")
            if (isinstance(event_ack, int)
                    and not isinstance(event_ack, bool)
                    and client.get("event_ack", 0)
                    <= event_ack
                    <= getattr(self, "event_sequence", 0)):
                client["event_ack"] = event_ack
            input_sequence = message.get("iq")
            if (not isinstance(input_sequence, int)
                    or isinstance(input_sequence, bool)
                    or not 0 <= input_sequence <= 2 ** 31 - 1
                    or input_sequence
                    <= client.get("last_input_sequence", -1)):
                return
            client["last_input_sequence"] = input_sequence

        client["last_seen"] = self.net_time
        remote = client["player"]
        if (not remote.alive or self.paused
                or self.outcome is not None):
            return

        angle = _finite_float(message.get("a"))
        if angle is not None:
            remote.angle = angle % math.tau

        requested_roll = _finite_float(
            message.get("rt", 0.0), 0.0, Player.ROLL_DURATION,
        )
        raw_roll_sequence = message.get("rs")
        if (isinstance(raw_roll_sequence, int)
                and not isinstance(raw_roll_sequence, bool)
                and 0 <= raw_roll_sequence <= 2 ** 31 - 1):
            last_sequence = client.get("last_roll_sequence", 0)
            if requested_roll and raw_roll_sequence > last_sequence:
                client["pending_roll_sequence"] = raw_roll_sequence
            pending_sequence = client.get("pending_roll_sequence")
            if pending_sequence is not None and not remote.rolling:
                self._start_remote_roll(remote)
                client["last_roll_sequence"] = pending_sequence
                client["pending_roll_sequence"] = None
        elif raw_roll_sequence is None:
            # Anciens clients : un front montant est exigé. Un vieux paquet
            # UDP `rt>0` arrivé en retard ne relance donc pas la roulade.
            latched = client.get("legacy_roll_latched", False)
            if not requested_roll:
                client["legacy_roll_latched"] = False
            elif not latched:
                client["legacy_roll_latched"] = True
                if not remote.rolling:
                    self._start_remote_roll(remote)

        aiming = message.get("ad", 0)
        remote.aiming = bool(
            aiming is True
            or (isinstance(aiming, int)
                and not isinstance(aiming, bool)
                and aiming == 1)
        ) and not remote.rolling

        x = _finite_float(message.get("x"), 0.0, self.level.width)
        y = _finite_float(message.get("y"), 0.0, self.level.height)
        speed = (
            Player.ROLL_SPEED if remote.rolling
            else Player.SPEED * (Player.ADS_MULT if remote.aiming else 1.0)
        )
        capacity = speed * MOVE_BURST_SECONDS + MOVE_JITTER
        motion_elapsed = max(
            0.0,
            self.net_time - client.get("last_motion_time", self.net_time),
        )
        client["last_motion_time"] = self.net_time
        move_credit = min(
            capacity,
            client.get("move_credit", capacity) + motion_elapsed * speed,
        )
        if x is not None and y is not None:
            blockers = [
                entity
                for entity in self.enemies + self._all_players()
                if entity is not remote and entity.alive
            ]
            moved = self._accept_remote_position(
                remote, x, y, move_credit, blockers,
            )
            remote.moving = moved > 1e-9
            client["move_credit"] = max(0.0, move_credit - moved)
        else:
            remote.moving = False
            client["move_credit"] = move_credit

        weapon_id = message.get("wid")
        if weapon_id in client["weapons"]:
            client["active_weapon"] = weapon_id
        active_weapon = client["weapons"][client["active_weapon"]]

        reload_sequence = message.get("rl")
        if (isinstance(reload_sequence, int)
                and not isinstance(reload_sequence, bool)
                and client.get("last_reload_sequence", 0)
                < reload_sequence <= 2 ** 31 - 1):
            client["last_reload_sequence"] = reload_sequence
            active_weapon.start_reload()

        fire_events = message.get("fx", [])
        # Les anciens couples [angle, dégâts] ne permettent pas de vérifier
        # arme, chargeur, cadence ni nombre de plombs. Un hôte v2 les refuse.
        if (protocol < PROTOCOL_VERSION or remote.rolling
                or not isinstance(fire_events, list)):
            return
        for trigger in fire_events[:MAX_REMOTE_FIRE_EVENTS]:
            if not isinstance(trigger, (list, tuple)) or len(trigger) != 2:
                continue
            trigger_weapon_id, raw_angles = trigger
            weapon = client["weapons"].get(trigger_weapon_id)
            if (weapon is None
                    or trigger_weapon_id != client["active_weapon"]
                    or not isinstance(raw_angles, list)
                    or len(raw_angles) != weapon.spec.pellets):
                continue
            angles = []
            max_delta = weapon.spec.spread + 0.025
            for raw_angle in raw_angles:
                shot_angle = _finite_float(raw_angle)
                if shot_angle is None:
                    angles = []
                    break
                delta = (
                    shot_angle - remote.angle + math.pi
                ) % math.tau - math.pi
                if abs(delta) > max_delta:
                    angles = []
                    break
                angles.append(shot_angle)
            if not angles or not weapon.fire():
                continue
            self._resolve_remote_shot(pid, remote, weapon, angles)

    @staticmethod
    def _start_remote_roll(remote):
        """Démarre une roulade distante validée par l'hôte."""
        if not remote.rolling:
            remote.roll_timer = Player.ROLL_DURATION
            remote.roll_invuln = 0.0
            remote.roll_cooldown = Player.ROLL_COOLDOWN

    def _accept_remote_position(self, remote, target_x, target_y, allowance,
                                blockers=()):
        """Accepte une position dans le crédit hôte et sans traversée."""
        dx, dy = target_x - remote.x, target_y - remote.y
        distance = math.hypot(dx, dy)
        allowance = max(0.0, allowance)
        if distance <= 1e-9 or allowance <= 0.0:
            return 0.0
        if distance > allowance:
            scale = allowance / distance
            dx, dy = dx * scale, dy * scale
            distance = allowance
        steps = max(1, math.ceil(distance / 0.1))
        step_x, step_y = dx / steps, dy / steps
        old = (remote.x, remote.y)
        for _ in range(steps):
            next_pos = move_with_entity_collisions(
                self.level, remote.x, remote.y,
                step_x, step_y, remote.RADIUS, blockers,
            )
            if next_pos == (remote.x, remote.y):
                break
            remote.x, remote.y = next_pos
        return math.hypot(remote.x - old[0], remote.y - old[1])

    def _resolve_remote_shot(self, pid, remote, weapon, angles):
        """Résout un déclenchement dont l'arme et la cadence sont hôte."""
        remote.flash_timer = 0.12   # les autres voient l'éclair de tir
        for angle in angles:
            result = self._hitscan(
                remote.x, remote.y, angle, weapon.damage,
                weapon.spec.hit_radius,
            )
            if result is not None:
                self._queue_net_event(
                    ["hm", pid, 1 if result == "kill" else 0],
                )
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
                    self.player.roll_timer = 0.0
                    self.player.roll_invuln = 0.0
                    self.player.roll_cooldown = 0.0
                    self.player.activate_shield()
                else:
                    entity.x, entity.y = x, y
                    _revive(entity, 60)
                self._queue_net_event(
                    ["rs", pid, round(x, 2), round(y, 2)],
                )
                self.respawns.pop(pid, None)
            else:
                self.respawns[pid] = timer

    def _prune_clients(self):
        for pid in [p for p, c in self.clients.items()
                    if self.net_time - c["last_seen"] > CLIENT_TIMEOUT]:
            del self.clients[pid]
            self.respawns.pop(pid, None)

    def _broadcast(self):
        host_weapons = {
            weapon.spec.id: weapon for weapon in self.player.weapons
        }
        players = [[0, round(self.player.x, 2), round(self.player.y, 2),
                    round(self.player.angle, 3), self.player.health,
                    int(getattr(self, "player_moving", False)),
                    int(self.hud.flash > 0), int(self.player.rolling),
                    round(self.player.roll_timer, 2),
                    _inventory_rows(host_weapons),
                    self.player.weapon.spec.id]]
        for pid, client in self.clients.items():
            remote = client["player"]
            players.append([pid, round(remote.x, 2), round(remote.y, 2),
                            round(remote.angle, 3), remote.health,
                            int(remote.moving), int(remote.flash_timer > 0),
                            int(remote.rolling), round(remote.roll_timer, 2),
                            _inventory_rows(client["weapons"]),
                            client["active_weapon"]])
        enemies = [[e.net_id, e.KIND, round(e.x, 2), round(e.y, 2),
                    round(e.angle, 3), e.health, int(e.moving),
                    int(e.flash_timer > 0), int(e.aiming), int(e.rolling),
                    round(e.roll_timer, 2), e.max_health, int(e.possessed)]
                   for e in self.enemies if e.net_id is not None]
        static_pickups = [p for p in self.pickups if not p.dynamic]
        dynamic_pickups = [
            [p.net_id, round(p.x, 2), round(p.y, 2), p.kind, int(p.taken)]
            for p in self.pickups if p.dynamic
        ]
        snapshot = {
            "t": "snap",
            "pl": players,
            "en": enemies,
            # Les lignes dynamiques sont ajoutées après les booléens historiques :
            # un ancien client les ignore naturellement après son zip statique.
            "pk": [int(p.taken) for p in static_pickups] + dynamic_pickups,
            "wv": self.survival_info(),
            "ov": self.outcome or "",
            "pa": int(self.paused),
            "ev": self.net_events,
        }
        self.snapshot_sequence += 1
        for client in self.clients.values():
            payload = snapshot
            if client.get("protocol", 1) >= PROTOCOL_VERSION:
                payload = dict(snapshot)
                payload["sid"] = self.session_id
                payload["sq"] = self.snapshot_sequence
                ack = client.get("event_ack", 0)
                floor = (
                    self.event_journal[0][0] - 1
                    if self.event_journal
                    else ack
                )
                payload["eb"] = max(ack, floor)
                payload["rev"] = [
                    [sequence, event]
                    for sequence, event in self.event_journal
                    if sequence > ack
                ][:MAX_EVENTS_PER_SNAPSHOT]
            self.peer.send(
                payload, client["addr"],
                compress=client.get("protocol", 1) >= PROTOCOL_VERSION,
            )
        self.net_events = []
        reliable_clients = [
            client for client in self.clients.values()
            if client.get("protocol", 1) >= PROTOCOL_VERSION
        ]
        if reliable_clients:
            minimum_ack = min(
                client.get("event_ack", 0)
                for client in reliable_clients
            )
            while (self.event_journal
                   and self.event_journal[0][0] <= minimum_ack):
                self.event_journal.popleft()
        else:
            self.event_journal.clear()

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
        self.base_pickup_count = len(self.pickups)
        self.dynamic_pickups = {}
        self.props = [Prop(x, y, kind)
                      for x, y, kind in self.level.prop_spawns]

        self.particles = ParticleSystem()
        self.raycaster = Raycaster(screen.get_size(), self.level)
        self.hud = HUD(screen.get_size())
        self.touch = TouchControls(screen.get_size())
        self.stats = new_stats()
        self.paused = False
        self.host_paused = False
        self.outcome = None
        self.end_delay = 0.0
        self.time = 0.0
        self.shake = 0.0
        self.show_fps = False
        self.fps = 60.0
        self.sparkle_timer = 0.0
        self.step_distance = 0.0
        self.step_side = False
        self._mouse_fire_held = False
        self._mouse_aim_held = False

        # Réseau
        self.peer = UdpPeer()
        self.host_addr = (host_ip, port)
        self.pid = None
        self.join_wait = 0.0
        self.join_resend = 0.0
        self.last_snap = 0.0
        self.disconnected = False
        self.disconnect_reason = ""
        self.pending_fires = []    # [[arme, [angles...]], ...] à envoyer
        self.send_timer = 0.0
        self.input_sequence = 0
        self.reload_sequence = 0
        self.host_session = None
        self.last_snapshot_sequence = -1
        self.last_event_sequence = 0

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

    @property
    def controls_paused(self):
        """Pause locale ou pause autoritaire imposée par l'hôte."""
        return self.paused or self.host_paused

    def resize(self, size):
        """Adapte le client répliqué après un changement de mode vidéo."""
        self.raycaster.resize(size)
        self.hud.resize(size)
        self.touch.resize(size)

    def survival_info(self):
        return self.wave_info

    # -- événements -------------------------------------------------------
    def handle_event(self, event):
        if event.type == pygame.WINDOWFOCUSLOST:
            self.player.aiming = False
            self._mouse_fire_held = False
            self._mouse_aim_held = False
            self.touch.reset()
            if self.outcome is None:
                self.paused = True
            pygame.mouse.get_rel()
            return None
        if event.type in FINGER_EVENTS:
            actions = self.touch.handle_event(event)
            for action in actions:
                result = self._handle_touch_action(action)
                if result is not None:
                    return result
            return None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                if not self.host_paused:
                    self.paused = not self.paused
                self.player.aiming = False
                self._mouse_fire_held = False
                self._mouse_aim_held = False
                self.touch.reset()
                pygame.mouse.get_rel()
            elif self.controls_paused and event.key == pygame.K_m:
                return "menu"
            elif event.key == pygame.K_F3:
                self.show_fps = not self.show_fps
            elif (not self.controls_paused and self.player.alive
                  and self.outcome is None
                  and (event.key == self.settings.keys["roulade"]
                       or (self.settings.keys["roulade"] in
                           (pygame.K_LSHIFT, pygame.K_RSHIFT)
                           and event.key in (pygame.K_LSHIFT,
                                             pygame.K_RSHIFT)))):
                self.player.start_roll(
                    pygame.key.get_pressed(), self.settings.keys,
                )
            elif (not self.controls_paused and self.outcome is None
                  and self.player.alive
                  and event.key == self.settings.keys["recharger"]):
                self._request_reload()
            elif (not self.controls_paused and self.outcome is None
                  and self.player.alive
                  and event.scancode in SLOT_SCANCODES):
                if self.player.select_weapon(SLOT_SCANCODES[event.scancode]):
                    self.sounds.play("click", volume_scale=0.4)
        elif (event.type == pygame.MOUSEWHEEL and not self.controls_paused
              and self.outcome is None and self.player.alive):
            # Voir game.py : rétablit le sens de la molette en défilement
            # "naturel" (event.flipped) et ignore les molettes horizontales.
            wheel_y = -event.y if getattr(event, "flipped", False) else event.y
            if wheel_y:
                self.player.cycle_weapon(-1 if wheel_y > 0 else 1)
                self.sounds.play("click", volume_scale=0.4)
        elif (event.type == pygame.MOUSEBUTTONDOWN
              and not getattr(event, "touch", False)
              and not self.controls_paused
              and self.outcome is None and self.player.alive):
            if event.button == 1:
                self._mouse_fire_held = True
                self._fire()
            elif event.button == 3 and not self.player.rolling:
                self._mouse_aim_held = True
                self.player.aiming = True
        elif (event.type == pygame.MOUSEBUTTONUP
              and not getattr(event, "touch", False)):
            if event.button == 1:
                self._mouse_fire_held = False
            elif event.button == 3:
                self._mouse_aim_held = False
                self.player.aiming = self.touch.aim_held
        return None

    def _handle_touch_action(self, action):
        if action == "pause":
            if not self.host_paused:
                self.paused = not self.paused
            self.player.aiming = False
            self._mouse_fire_held = False
            self._mouse_aim_held = False
            # Libère aussi les commandes posées pendant la pause afin qu'un
            # tir/ADS ne parte pas tout seul à la reprise.
            self.touch.reset()
            pygame.mouse.get_rel()
            return None
        if action == "menu":
            return "menu" if self.controls_paused else None
        if (self.controls_paused or self.outcome is not None
                or not self.player.alive):
            return None
        if action == "fire_down":
            self._fire()
        elif action in ("aim_down", "aim_up"):
            self.player.aiming = (
                not self.player.rolling
                and (self._mouse_aim_held or self.touch.aim_held)
            )
        elif action == "roll":
            self.player.start_roll(
                pygame.key.get_pressed(), self.settings.keys,
                self.touch.movement_axes(),
            )
        elif action == "reload":
            self._request_reload()
        elif action == "weapon":
            self.player.cycle_weapon(1)
            self.sounds.play("click", volume_scale=0.4)
        return None

    def _request_reload(self):
        """Démarre une recharge locale et séquence la demande pour l'hôte."""
        weapon = self.player.weapon
        was_reloading = weapon.reloading > 0.0
        weapon.start_reload()
        if not was_reloading and weapon.reloading > 0.0:
            self.reload_sequence += 1
            self.sounds.play("reload")

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
        if player.alive and not self.controls_paused and self.outcome is None:
            self.stats["time"] += dt
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            touch_dx, touch_dy = self.touch.consume_look()
            mouse_dx += touch_dx
            mouse_dy += touch_dy
            if self.settings.invert_mouse:
                mouse_dx, mouse_dy = -mouse_dx, -mouse_dy   # option : souris inversée
            if not player.rolling:
                player.aiming = self._mouse_aim_held or self.touch.aim_held
                player.rotate(mouse_dx, mouse_dy, self.settings.mouse_factor())
            keys = pygame.key.get_pressed()
            old_x, old_y = player.x, player.y
            touch_axes = (self.touch.movement_axes()
                          if self.touch.enabled else None)
            moving = player.move(
                dt, keys, self.settings.keys, self.level, touch_axes,
                [
                    entity
                    for entity in (
                        list(self.ghosts.values())
                        + list(self.allies.values())
                    )
                    if entity.alive
                ],
            )
            if player.rolling:
                self.step_distance = 0.0
            else:
                self.step_distance += math.hypot(player.x - old_x,
                                                 player.y - old_y)
            if self.step_distance > 1.05:
                self.step_distance = 0.0
                self.step_side = not self.step_side
                self.sounds.play("step" if self.step_side else "step2",
                                 volume_scale=0.35)
            if (not player.rolling
                    and (self._mouse_fire_held or self.touch.fire_held)
                    and player.weapon.spec.automatic):
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
        if self.player.rolling:
            return
        weapon = self.player.weapon
        if not weapon.fire():
            return
        self.sounds.play(weapon.spec.sound, volume_scale=0.9)
        if weapon.reloading > 0.0:
            # Dernière cartouche : rechargement automatique audible,
            # comme côté solo (game.py).
            self.sounds.play("reload")
        self.hud.on_player_shot()
        if weapon.spec.id in ("shotgun", "minigun"):
            self.shake = min(1.0, self.shake + 0.18)
        self.stats["shots"] += 1
        spread = weapon.spec.spread * (1.0 - 0.75 * self.player.ads)
        angles = []
        for _ in range(weapon.spec.pellets):
            angle = self.player.angle + random.uniform(-spread, spread)
            angles.append(round(angle, 4))
            # Poussière d'impact locale (l'hôte décide des vrais dégâts).
            wall_dist, _, _, _ = cast_ray(self.level, self.player.x,
                                          self.player.y, angle)
            hx = self.player.x + math.cos(angle) * (wall_dist - 0.05)
            hy = self.player.y + math.sin(angle) * (wall_dist - 0.05)
            self.particles.spawn_wall_dust(hx, hy, (110, 110, 110))
        self.pending_fires.append([weapon.spec.id, angles])
        if len(self.pending_fires) > MAX_REMOTE_FIRE_EVENTS:
            # Une longue perte réseau ne doit pas rejouer une rafale ancienne
            # en bloc lorsque la liaison revient.
            del self.pending_fires[:-MAX_REMOTE_FIRE_EVENTS]

    # -- réseau -----------------------------------------------------------
    def _ensure_joined(self, dt):
        if self.pid is None:
            self.join_wait += dt
            self.join_resend -= dt
            if self.join_resend <= 0.0:
                self.join_resend = 0.7
                self.peer.send({
                    "t": "join", "v": PROTOCOL_VERSION,
                }, self.host_addr)
            if self.join_wait > JOIN_TIMEOUT:
                self.disconnected = True
                self.disconnect_reason = "Impossible de joindre l'hôte."
        elif self.time - self.last_snap > LOST_TIMEOUT:
            self.disconnected = True
            self.disconnect_reason = "Connexion à l'hôte perdue."

    def _net_send(self, dt):
        if self.pid is None:
            return
        self.send_timer -= dt
        if self.send_timer > 0.0 and not self.pending_fires:
            return
        self.send_timer = SEND_INTERVAL
        self.input_sequence = (self.input_sequence + 1) % (2 ** 31)
        self.peer.send({
            "t": "in", "id": self.pid,
            "v": PROTOCOL_VERSION,
            "sid": self.host_session,
            "iq": self.input_sequence,
            "ea": self.last_event_sequence,
            "x": round(self.player.x, 3), "y": round(self.player.y, 3),
            "a": round(self.player.angle, 3),
            "ad": int(self.player.aiming),
            "rt": round(self.player.roll_timer, 3),
            "rs": self.player.roll_sequence,
            "rl": self.reload_sequence,
            "wid": self.player.weapon.spec.id,
            "fx": self.pending_fires,
        }, self.host_addr)
        self.pending_fires = []

    def _net_receive(self):
        for message, addr in self.peer.receive():
            if addr != self.host_addr:
                continue
            kind = message.get("t")
            if kind == "welcome":
                pid = message.get("id")
                if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
                    session_id = message.get("sid")
                    if (message.get("v") == PROTOCOL_VERSION
                            and (not isinstance(session_id, str)
                                 or not 1 <= len(session_id) <= 64)):
                        continue
                    event_sequence = message.get("es", 0)
                    if (not isinstance(event_sequence, int)
                            or isinstance(event_sequence, bool)
                            or not 0 <= event_sequence <= 2 ** 63 - 1):
                        continue
                    if session_id != self.host_session:
                        self.last_snapshot_sequence = -1
                        self.last_event_sequence = event_sequence
                        self.input_sequence = 0
                    self.host_session = session_id
                    self.pid = pid
            elif kind == "full":
                self.disconnected = True
                self.disconnect_reason = "Partie complète (4 joueurs maximum)."
            elif kind == "snap" and self.pid is not None:
                self.last_snap = self.time
                self._apply_snapshot(message)

    def _apply_snapshot(self, snap):
        if not self._accept_snapshot_header(snap):
            return False
        players = snap.get("pl")
        enemies = snap.get("en")
        pickups = snap.get("pk")
        wave = snap.get("wv")
        if not isinstance(players, list) or not isinstance(enemies, list):
            return False
        paused = snap.get("pa", 0)
        if not (isinstance(paused, bool)
                or (isinstance(paused, int)
                    and not isinstance(paused, bool)
                    and paused in (0, 1))):
            return False
        self._set_host_paused(bool(paused))
        events = self._snapshot_events(snap)
        impact_ids = set()
        for event in events:
            if (isinstance(event, (list, tuple)) and len(event) == 3
                    and event[0] == "ei"
                    and isinstance(event[1], int)
                    and not isinstance(event[1], bool)
                    and (isinstance(event[2], bool)
                         or (isinstance(event[2], int)
                             and event[2] in (0, 1)))):
                impact_ids.add(event[1])
        self._apply_players(players)
        self._apply_enemies(enemies, impact_ids)
        if isinstance(pickups, list):
            self._apply_pickups(pickups)
        self._apply_wave(wave)
        for event in events:
            self._apply_event(event)
        outcome = snap.get("ov")
        if outcome in ("dead", "victory") and self.outcome is None:
            self.outcome = outcome
        self.synced = True
        return True

    def _accept_snapshot_header(self, snap):
        """Rejette une autre session et tout instantané dupliqué/retardé."""
        session_id = snap.get("sid")
        sequence = snap.get("sq")
        host_session = getattr(self, "host_session", None)
        if session_id is None and sequence is None:
            return host_session is None  # compatibilité avec un hôte v1
        if (not isinstance(session_id, str)
                or not 1 <= len(session_id) <= 64
                or session_id != host_session
                or not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or not 0 <= sequence <= 2 ** 63 - 1):
            return False
        if sequence <= getattr(self, "last_snapshot_sequence", -1):
            return False
        self.last_snapshot_sequence = sequence
        return True

    def _snapshot_events(self, snap):
        """Extrait uniquement la suite fiable, contiguë et non déjà jouée."""
        reliable = snap.get("rev")
        if not isinstance(reliable, list):
            events = snap.get("ev", [])
            return events[:MAX_EVENTS_PER_SNAPSHOT] if isinstance(events, list) else []

        baseline = snap.get("eb", getattr(self, "last_event_sequence", 0))
        if (isinstance(baseline, int) and not isinstance(baseline, bool)
                and 0 <= baseline <= 2 ** 63 - 1):
            self.last_event_sequence = max(
                getattr(self, "last_event_sequence", 0), baseline,
            )
        expected = getattr(self, "last_event_sequence", 0) + 1
        accepted = []
        for row in reliable[:MAX_EVENTS_PER_SNAPSHOT]:
            if (not isinstance(row, (list, tuple)) or len(row) != 2
                    or not isinstance(row[0], int)
                    or isinstance(row[0], bool)
                    or not isinstance(row[1], (list, tuple))):
                continue
            sequence, event = row
            if sequence < expected:
                continue
            if sequence > expected:
                break
            accepted.append(event)
            expected += 1
        self.last_event_sequence = expected - 1
        return accepted

    def _set_host_paused(self, paused):
        """Applique la pause hôte et neutralise toute commande déjà armée."""
        was_paused = getattr(self, "host_paused", False)
        self.host_paused = paused
        if paused and not was_paused:
            self.player.aiming = False
            self._mouse_fire_held = False
            self._mouse_aim_held = False
            self.pending_fires.clear()
            self.touch.reset()
            pygame.mouse.get_rel()

    def _apply_players(self, players):
        seen = set()
        level = getattr(self, "level", None)
        max_x = getattr(level, "width", 100000.0)
        max_y = getattr(level, "height", 100000.0)
        for data in players:
            # Roulade ajoutée en fin de ligne : accepte les anciens hôtes à
            # sept champs sans casser une session LAN mixte.
            if not isinstance(data, (list, tuple)) or len(data) < 7:
                continue
            pid = data[0]
            if isinstance(pid, bool) or not isinstance(pid, int):
                continue
            x = _finite_float(data[1], 0.0, max_x)
            y = _finite_float(data[2], 0.0, max_y)
            angle = _finite_float(data[3])
            health = _finite_float(data[4], 0.0, 100.0)
            if None in (x, y, angle, health):
                continue
            health = round(health)
            moving, flash = bool(data[5]), bool(data[6])
            rolling = bool(data[7]) if len(data) > 7 else False
            roll_timer = (_finite_float(data[8], 0.0, Player.ROLL_DURATION)
                          if len(data) > 8 else 0.0)
            inventory = data[9] if len(data) > 9 else None
            active_weapon = data[10] if len(data) > 10 else None
            if roll_timer is None:
                roll_timer = 0.0
            if pid == self.pid:
                # Sa propre vie est décidée par l'hôte.
                was_alive = self.player.alive
                if health <= 0:
                    self.player.shield = 0.0
                    self.player.roll_timer = 0.0
                    self.player.roll_invuln = 0.0
                    self.player.health = 0
                elif not was_alive:
                    self.player.health = health
                    self.player.x, self.player.y = x, y
                    self.player.roll_timer = 0.0
                    self.player.roll_invuln = 0.0
                    self.player.roll_cooldown = 0.0
                    self.player.activate_shield()
                    self.hud.show_message(
                        "Vous êtes de retour dans la bataille !",
                    )
                elif health < self.player.health:
                    self.player.health = health
                    self.player.hurt_flash = 0.35
                    self.sounds.play("player_hit")
                    self.shake = min(1.0, self.shake + 0.5)
                else:
                    self.player.health = health
                drift = math.hypot(self.player.x - x, self.player.y - y)
                if (not self.synced or self.host_paused or drift > 0.65):
                    self.player.x, self.player.y = x, y
                if isinstance(inventory, list):
                    self._apply_authoritative_inventory(
                        inventory, active_weapon,
                    )
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
            ally.roll_timer = roll_timer if rolling else 0.0
            ally.roll_invuln = 0.0
            if flash and ally.flash_timer <= 0.0:
                ally.flash_timer = 0.12
                self.sounds.play("player_shot", volume_scale=0.5,
                                 pos=(ally.x, ally.y), listener=self.player)
            if health <= 0 and ally.alive:
                ally.shield = 0.0
                ally.roll_invuln = 0.0
                ally.take_damage(10 ** 6)
                self.particles.spawn_death(ally.x, ally.y)
            elif health > 0 and not ally.alive:
                _revive(ally, health)
            else:
                ally.health = health
        for pid in [p for p in self.allies if p not in seen]:
            del self.allies[pid]

    def _apply_authoritative_inventory(self, rows, active_weapon):
        """Réconcilie les armes possédées sans écraser la prédiction de tir."""
        validated = {}
        for row in rows[:len(WEAPON_ORDER)]:
            if (not isinstance(row, (list, tuple)) or len(row) != 2
                    or row[0] not in WEAPON_SPECS):
                continue
            level = _finite_float(row[1], 0.0, 3.0)
            if level is None:
                continue
            validated[row[0]] = round(level)
        if not validated:
            return
        previous_active = self.player.weapon.spec.id
        owned = {weapon.spec.id: weapon for weapon in self.player.weapons}
        for weapon_id, level in validated.items():
            weapon = owned.get(weapon_id)
            if weapon is None or weapon.level != level:
                owned[weapon_id] = Weapon(WEAPON_SPECS[weapon_id], level)
        self.player.weapons = [
            owned[weapon_id]
            for weapon_id in WEAPON_ORDER
            if weapon_id in owned and weapon_id in validated
        ]
        if not self.player.weapons:
            return
        selected = (
            previous_active
            if previous_active in validated
            else active_weapon
        )
        self.player.weapon_index = next(
            (
                index for index, weapon in enumerate(self.player.weapons)
                if weapon.spec.id == selected
            ),
            0,
        )

    def _apply_enemies(self, enemies, replicated_impact_ids=None):
        seen = set()
        replicated_impact_ids = replicated_impact_ids or set()
        level = getattr(self, "level", None)
        max_x = getattr(level, "width", 100000.0)
        max_y = getattr(level, "height", 100000.0)
        for data in enemies:
            # Visée puis roulade ont été ajoutées en fin de ligne : les
            # instantanés historiques à huit ou neuf champs restent acceptés.
            if not isinstance(data, (list, tuple)) or len(data) < 8:
                continue
            net_id, kind = data[0], data[1]
            if (isinstance(net_id, bool) or not isinstance(net_id, int)
                    or kind not in ENEMY_TYPES):
                continue
            x = _finite_float(data[2], 0.0, max_x)
            y = _finite_float(data[3], 0.0, max_y)
            angle = _finite_float(data[4])
            health = _finite_float(data[5], 0.0, 100000.0)
            if None in (x, y, angle, health):
                continue
            health = round(health)
            moving, flash = bool(data[6]), bool(data[7])
            aiming = bool(data[8]) if len(data) > 8 else False
            rolling = bool(data[9]) if len(data) > 9 else False
            roll_timer = (_finite_float(data[10], 0.0, 1.0)
                          if len(data) > 10 else 0.0)
            max_health = (_finite_float(data[11], 1.0, 100000.0)
                          if len(data) > 11 else None)
            possessed = bool(data[12]) if len(data) > 12 else False
            if roll_timer is None:
                roll_timer = 0.0
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
            ghost.set_possessed(possessed)
            if max_health is not None:
                ghost.max_health = round(max_health)
            ghost.moving = bool(moving)
            ghost.aiming = aiming
            ghost.roll_timer = roll_timer if rolling else 0.0
            ghost.roll_invuln = ghost.roll_timer
            if not aiming:
                ghost.aim_timer = 0.0
            if flash and ghost.flash_timer <= 0.0:
                ghost.flash_timer = 0.12
                self.sounds.play("enemy_shot", volume_scale=0.9,
                                 pos=(ghost.x, ghost.y), listener=self.player)
            if health <= 0 and ghost.alive:
                ghost.roll_invuln = 0.0
                ghost.take_damage(10 ** 6)
                if net_id not in replicated_impact_ids:
                    self._emit_enemy_impact(ghost, fatal=True)
                self.sounds.play("enemy_die", volume_scale=0.8,
                                 pos=(ghost.x, ghost.y), listener=self.player)
            elif 0 < health < ghost.health:
                if net_id not in replicated_impact_ids:
                    self._emit_enemy_impact(ghost)
                ghost.hurt_timer = 0.09   # flash blanc de l'impact
                ghost.health = health
            else:
                ghost.health = max(0, health)
            sync_phase = getattr(ghost, "sync_phase_from_health", None)
            if sync_phase is not None:
                sync_phase()
        for net_id in [n for n in self.ghosts if n not in seen]:
            del self.ghosts[net_id]

    def _apply_pickups(self, rows):
        """Applique les objets statiques puis les apparitions du Colosse."""
        static_rows = rows[:self.base_pickup_count]
        for pickup, taken in zip(self.pickups[:self.base_pickup_count],
                                 static_rows):
            # Une ligne dynamique mal placée ne doit pas valoir True par
            # simple conversion booléenne.
            if (isinstance(taken, bool)
                    or (isinstance(taken, int)
                        and not isinstance(taken, bool)
                        and taken in (0, 1))):
                pickup.taken = bool(taken)

        seen = set()
        for data in rows[self.base_pickup_count:]:
            if not isinstance(data, (list, tuple)) or len(data) != 5:
                continue
            net_id, x, y, kind, taken = data
            if (isinstance(net_id, bool) or not isinstance(net_id, int)
                    or not 0 <= net_id <= 1000000
                    or kind not in ("medkit", "lifepack")):
                continue
            if not (isinstance(taken, bool)
                    or (isinstance(taken, int)
                        and not isinstance(taken, bool)
                        and taken in (0, 1))):
                continue
            x = _finite_float(x, 0.0, self.level.width)
            y = _finite_float(y, 0.0, self.level.height)
            if x is None or y is None:
                continue
            seen.add(net_id)
            pickup = self.dynamic_pickups.get(net_id)
            if pickup is None:
                pickup = Pickup(x, y, kind, self.level_index)
                pickup.dynamic = True
                pickup.hidden = False
                pickup.net_id = net_id
                self.dynamic_pickups[net_id] = pickup
                self.pickups.append(pickup)
                if self.synced:
                    self.particles.spawn_portal(x, y)
                    self.sounds.play("spawn", volume_scale=0.75,
                                     pos=(x, y), listener=self.player)
            pickup.x, pickup.y = x, y
            pickup.taken = bool(taken)
        # L'hôte conserve normalement les objets pris. La suppression reste
        # gérée pour tolérer une future politique de nettoyage.
        for net_id in [dynamic_id for dynamic_id in self.dynamic_pickups
                       if dynamic_id not in seen]:
            pickup = self.dynamic_pickups.pop(net_id)
            if pickup in self.pickups:
                self.pickups.remove(pickup)

    def _apply_wave(self, wave_info):
        if not isinstance(wave_info, dict):
            return
        wave = _finite_float(wave_info.get("wave"), 0.0, 999.0)
        final = _finite_float(wave_info.get("final"), 1.0, 999.0)
        remaining = _finite_float(wave_info.get("remaining"), 0.0, 100000.0)
        next_in = _finite_float(wave_info.get("next_in"), 0.0, 3600.0)
        if None in (wave, final, remaining, next_in):
            return
        clean = {"wave": round(wave), "final": round(final),
                 "remaining": round(remaining), "next_in": next_in,
                 "intermission": bool(wave_info.get("intermission"))}
        if clean["wave"] > self.wave_info["wave"] and self.synced:
            self.sounds.play("wave", volume_scale=0.9)
            self.hud.announce(f"VAGUE {clean['wave']}")
        self.wave_info = clean

    def _apply_event(self, event):
        if not isinstance(event, (list, tuple)) or not event:
            return
        kind = event[0]
        if kind == "ex" and len(event) == 3:
            _, x, y = event
            x = _finite_float(x, 0.0, self.level.width)
            y = _finite_float(y, 0.0, self.level.height)
            if x is None or y is None:
                return
            self.particles.spawn_explosion(x, y)
            self.sounds.play("explosion", pos=(x, y), listener=self.player)
            if math.hypot(x - self.player.x, y - self.player.y) < 5:
                self.shake = min(1.0, self.shake + 0.5)
        elif kind == "hm" and len(event) == 3 and event[1] == self.pid:
            self.stats["hits"] += 1
            killed = 1 if event[2] else 0
            self.stats["kills"] += killed
            self.hud.on_enemy_hit(killed=bool(killed))
        elif kind == "ei" and len(event) == 3:
            net_id, fatal = event[1], event[2]
            if (isinstance(net_id, bool) or not isinstance(net_id, int)
                    or not (isinstance(fatal, bool)
                            or (isinstance(fatal, int)
                                and fatal in (0, 1)))):
                return
            enemy = self.ghosts.get(net_id)
            if enemy is not None:
                self._emit_enemy_impact(enemy, fatal=bool(fatal))
        elif kind == "rs" and len(event) == 4 and event[1] == self.pid:
            x = _finite_float(event[2], 0.0, self.level.width)
            y = _finite_float(event[3], 0.0, self.level.height)
            if x is None or y is None:
                return
            self.player.x, self.player.y = x, y
            self.player.health = 60
            self.player.roll_timer = 0.0
            self.player.roll_invuln = 0.0
            self.player.roll_cooldown = 0.0
            self.player.activate_shield()
            self.hud.show_message("Vous êtes de retour dans la bataille !")
        elif (kind == "wpk" and len(event) == 4 and event[1] == self.pid
              and event[2] in WEAPON_SPECS):
            _, _, weapon_id, level = event
            level = _finite_float(level, 0.0, 3.0)
            if level is None:
                return
            level = round(level)
            self.player.add_weapon(weapon_id, level)
            self.sounds.play("pickup")
            weapon = next(w for w in self.player.weapons
                          if w.spec.id == weapon_id)
            self.hud.show_message("Arme récupérée : " + weapon.display_name)

    def _emit_enemy_impact(self, enemy, fatal=False):
        """Retour typé reçu de l'hôte, sans décider localement des dégâts."""
        self.particles.spawn_impact(
            enemy.x, enemy.y, enemy.impact_type, fatal=fatal,
        )
        self.sounds.play(
            f"{enemy.impact_type}_hit", volume_scale=0.68,
            pos=(enemy.x, enemy.y), listener=self.player,
        )

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
        if self.player.rolling:
            Game._player_roll_camera(self, screen)
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
        if self.controls_paused:
            self.hud.draw_pause(screen)
        self.touch.draw(screen, paused=self.controls_paused)

    def close(self):
        self.peer.close()
