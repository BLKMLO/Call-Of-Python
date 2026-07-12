"""Boucle de gameplay : relie le niveau, le joueur, les ennemis, le rendu.

Un `Game` correspond à UN niveau. `main.py` en crée un nouveau à chaque
niveau (en transférant le joueur : arsenal et vie conservés) et lit sa
propriété `outcome` : None (en cours), "dead" ou "victory".
"""

import math
import random

import assets
import pygame

from ai import EnemyAI
from entities import ENEMY_TYPES, Pickup, Player, Prop
from hud import HUD
from level import Level
from particles import ParticleSystem
from raycaster import Raycaster, cast_ray, zoom_screen

MEDKIT_HEAL = 35
PICKUP_RADIUS = 0.55         # distance de ramassage
LEVEL_HEAL = 40              # PV rendus en passant au niveau suivant
GUNSHOT_HEARING = 9.0        # rayon dans lequel un tir alerte les ennemis
SHOUT_HEARING = 5.0          # rayon du cri d'alerte d'un ennemi

# Scancodes des touches 1..4 (indépendants de la disposition AZERTY/QWERTY).
SLOT_SCANCODES = {30: 0, 31: 1, 32: 2, 33: 3}


def new_stats():
    """Statistiques d'une partie (cumulées sur la campagne)."""
    return {"shots": 0, "hits": 0, "kills": 0, "time": 0.0}


class Game:
    def __init__(self, screen, settings, sounds, level_index=0,
                 carry_player=None, level_config=None, carry_stats=None):
        self.settings = settings
        self.sounds = sounds
        self.level = Level(level_index, config=level_config)
        self.level_index = level_index
        self.stats = carry_stats if carry_stats is not None else new_stats()

        # Le joueur repart du spawn ; s'il vient du niveau précédent, il
        # garde son arsenal et récupère un peu de vie.
        self.player = Player(*self.level.player_spawn)
        if carry_player is not None:
            self.player.weapons = carry_player.weapons
            self.player.weapon_index = carry_player.weapon_index
            self.player.health = min(self.player.max_health,
                                     carry_player.health + LEVEL_HEAL)

        hp_mult = self.level.config["enemy_health_mult"]
        dmg_mult = self.level.config["enemy_damage_mult"]
        self.enemies = [ENEMY_TYPES[kind](x, y, hp_mult, dmg_mult)
                        for x, y, kind in self.level.enemy_spawns]
        self.ais = [EnemyAI(enemy) for enemy in self.enemies]
        self.pickups = [Pickup(x, y, kind, level_index)
                        for x, y, kind in self.level.pickup_spawns]
        self.props = [Prop(x, y, kind)
                      for x, y, kind in self.level.prop_spawns]

        self.particles = ParticleSystem()
        self.raycaster = Raycaster(screen.get_size(), self.level)
        self.hud = HUD(screen.get_size())
        self.paused = False
        self.outcome = None      # None (en cours), "dead" ou "victory"
        self.end_delay = 0.0     # petit délai avant l'écran de fin
        self.time = 0.0
        self.shake = 0.0         # amplitude du tremblement d'écran (0 → 1)
        self.show_fps = False    # bascule F3
        self.fps = 60.0          # FPS lissés (affichage)
        self.sparkle_timer = 0.0 # émission des étincelles des packs de vie
        self.step_distance = 0.0 # distance parcourue depuis le dernier pas
        self.step_side = False   # alterne les deux sons de pas
        pygame.mouse.get_rel()   # purge le mouvement accumulé dans les menus

    # ------------------------------------------------------------------
    # Événements ponctuels (clics, touches, molette)
    # ------------------------------------------------------------------
    def handle_event(self, event):
        """Retourne "menu" si le joueur demande à quitter la partie, sinon None."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.paused = not self.paused
                pygame.mouse.get_rel()  # évite un saut de caméra à la reprise
            elif self.paused and event.key == pygame.K_m:
                return "menu"
            elif event.key == pygame.K_F3:
                self.show_fps = not self.show_fps
            elif event.key == self.settings.keys["recharger"]:
                self.player.weapon.start_reload()
                if self.player.weapon.reloading > 0.0:
                    self.sounds.play("reload")
            elif event.scancode in SLOT_SCANCODES:   # touches 1..4
                if self.player.select_weapon(SLOT_SCANCODES[event.scancode]):
                    self.sounds.play("click", volume_scale=0.4)
        elif event.type == pygame.MOUSEWHEEL and not self.paused:
            # `flipped` = défilement "naturel" (pavés tactiles) : SDL
            # inverse alors le signe de y — on le rétablit pour que
            # molette vers le haut = arme précédente sur tous les OS.
            wheel_y = -event.y if getattr(event, "flipped", False) else event.y
            if wheel_y:
                self.player.cycle_weapon(-1 if wheel_y > 0 else 1)
                self.sounds.play("click", volume_scale=0.4)
        elif event.type == pygame.MOUSEBUTTONDOWN and not self.paused \
                and self.player.alive:
            if event.button == 1:
                # Premier coup au clic : indispensable pour le semi-auto.
                self._player_fire()
            elif event.button == 3:              # clic droit : mise en joue
                self.player.aiming = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.player.aiming = False
        return None

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------
    def update(self, dt):
        if self.paused or (self.outcome is not None and self.end_delay > 0.8):
            return
        self.time += dt
        self.fps = self.fps * 0.95 + (1.0 / max(dt, 1e-4)) * 0.05
        self.shake = max(0.0, self.shake - dt * 3.5)

        player = self.player
        if player.alive:
            self.stats["time"] += dt

            # Visée à la souris (mouvement relatif, curseur capturé).
            mouse_dx, mouse_dy = pygame.mouse.get_rel()
            if self.settings.invert_mouse:
                mouse_dx = -mouse_dx     # option : axe horizontal inversé
            player.rotate(mouse_dx, mouse_dy, self.settings.mouse_factor())

            # Déplacements clavier (sprint compris).
            keys = pygame.key.get_pressed()
            old_x, old_y = player.x, player.y
            moving = player.move(dt, keys, self.settings.keys, self.level)
            self.player_moving = moving   # relayé aux clients en coop LAN

            # Bruits de pas cadencés par la distance parcourue : le rythme
            # s'accélère naturellement en sprint.
            self.step_distance += math.hypot(player.x - old_x,
                                             player.y - old_y)
            if self.step_distance > 1.05:
                self.step_distance = 0.0
                self.step_side = not self.step_side
                self.sounds.play("step" if self.step_side else "step2",
                                 volume_scale=0.35)

            # Tir maintenu (armes automatiques uniquement).
            if pygame.mouse.get_pressed()[0] and player.weapon.spec.automatic:
                self._player_fire()

            player.update(dt)
            self.hud.update(dt, moving)
            self._check_pickups()

        # IA des ennemis → événements convertis en sons/effets/alertes.
        # Chaque ennemi vise le joueur le plus proche (un seul en solo,
        # plusieurs en coopération LAN).
        for ai in self.ais:
            target = self._ai_target(ai.enemy)
            for event, data in ai.update(dt, target, self.level):
                if event == "enemy_shot":
                    self.sounds.play("enemy_shot", volume_scale=0.9,
                                     pos=(data.x, data.y), listener=player)
                elif event == "player_hit":
                    enemy, victim = data
                    self._on_player_hit(enemy, victim)
                elif event == "explode":
                    self._explode(data)
                elif event == "spotted":
                    self._alert_allies((data.x, data.y), SHOUT_HEARING,
                                       exclude=data)

        self._separate_enemies()
        self._emit_lifepack_sparkles(dt)

        # Portes automatiques : s'ouvrent pour le joueur ET les ennemis.
        movers = [player] + [e for e in self.enemies if e.alive]
        for door_pos in self.level.update_doors(dt, movers):
            self.sounds.play("door", volume_scale=0.7,
                             pos=door_pos, listener=player)

        self.particles.update(dt)

        # Conditions de fin (avec un léger délai pour "encaisser" la scène).
        if self.outcome is None:
            self._check_outcome()
        else:
            self.end_delay += dt

    def _check_outcome(self):
        """Fin de partie standard ; surchargé par le mode survie."""
        if not self.player.alive:
            self.outcome = "dead"
        elif all(not enemy.alive for enemy in self.enemies):
            self.outcome = "victory"
            self.sounds.play("level_complete")

    def spawn_enemy(self, kind, x, y, hp_mult=1.0, dmg_mult=1.0):
        """Ajoute un ennemi en cours de partie (vagues du Déferlement)."""
        enemy = ENEMY_TYPES[kind](x, y, hp_mult, dmg_mult)
        self.enemies.append(enemy)
        self.ais.append(EnemyAI(enemy))
        return enemy

    # ------------------------------------------------------------------
    # Points d'ancrage surchargés par la coopération LAN (coop.py)
    # ------------------------------------------------------------------
    def _ai_target(self, enemy):
        """Cible de cet ennemi : le joueur (le plus proche, en coop)."""
        return self.player

    def _all_players(self):
        """Tous les joueurs à blesser (explosions...) ; un seul en solo."""
        return [self.player]

    def _extra_sprites(self):
        """Billboards supplémentaires (coéquipiers en coop)."""
        return []

    # ------------------------------------------------------------------
    # Dégâts subis et explosions
    # ------------------------------------------------------------------
    def _on_player_hit(self, enemy, victim):
        """Effets d'une balle ennemie encaissée par `victim`."""
        if victim is self.player:
            self.sounds.play("player_hit")
            self.shake = min(1.0, self.shake + 0.5)
            rel = math.atan2(enemy.y - victim.y,
                             enemy.x - victim.x) - victim.angle
            self.hud.on_player_hit(rel)

    def _explode(self, enemy):
        """Fait détoner un kamikaze : dégâts de zone sur les joueurs ET les
        autres ennemis (abattre un kamikaze dans la grappe paie)."""
        if enemy.exploded:
            return                   # ne détone qu'une seule fois
        enemy.exploded = True
        if enemy.alive:
            enemy.take_damage(10 ** 6)   # meurt dans sa propre explosion
        ex, ey = enemy.x, enemy.y
        self.particles.spawn_explosion(ex, ey)
        self.sounds.play("explosion", pos=(ex, ey), listener=self.player)

        radius = enemy.EXPLOSION_RADIUS
        for victim in self._all_players():
            if not victim.alive:
                continue
            dist = math.hypot(victim.x - ex, victim.y - ey)
            if dist < radius:
                damage = round(enemy.EXPLOSION_DAMAGE * (1 - dist / radius / 2)
                               * enemy.damage_mult)
                victim.take_damage(damage)
                self._on_player_hit(enemy, victim)
        for other in self.enemies:
            if other is enemy or not other.alive:
                continue
            dist = math.hypot(other.x - ex, other.y - ey)
            if dist < radius:
                damage = round(enemy.EXPLOSION_DAMAGE * (1 - dist / radius / 2))
                if other.EXPLODES:
                    damage *= 2   # les porteurs d'explosifs sont volatils
                died = other.take_damage(damage)
                if died:
                    self.particles.spawn_death(other.x, other.y)
                    if other.EXPLODES:
                        self._explode(other)   # réaction en chaîne
        if math.hypot(self.player.x - ex, self.player.y - ey) < radius * 3:
            self.shake = min(1.0, self.shake + 0.6)

    def _emit_lifepack_sparkles(self, dt):
        """Fait scintiller les packs de vie cachés (ce qui les trahit)."""
        self.sparkle_timer -= dt
        if self.sparkle_timer > 0.0:
            return
        self.sparkle_timer = 0.22
        for pickup in self.pickups:
            if pickup.kind == "lifepack" and not pickup.taken:
                self.particles.spawn_heal_sparkle(pickup.x, pickup.y)

    @property
    def finished(self):
        """Vrai quand l'écran de fin peut être affiché."""
        return self.outcome is not None and self.end_delay > 0.8

    def _alert_allies(self, position, radius, exclude=None):
        """Réveille les ennemis inactifs proches d'un bruit (tir, cri)."""
        for ai in self.ais:
            enemy = ai.enemy
            if enemy is exclude:
                continue
            if math.hypot(enemy.x - position[0], enemy.y - position[1]) < radius:
                ai.alert((self.player.x, self.player.y))

    def _separate_enemies(self):
        """Empêche les ennemis de s'empiler les uns sur les autres."""
        alive = [e for e in self.enemies if e.alive]
        for i, a in enumerate(alive):
            for b in alive[i + 1:]:
                dx, dy = b.x - a.x, b.y - a.y
                dist = math.hypot(dx, dy)
                min_dist = a.RADIUS + b.RADIUS
                if 1e-6 < dist < min_dist:
                    push = (min_dist - dist) / 2
                    ux, uy = dx / dist, dy / dist
                    a.x, a.y = self.level.move_with_collisions(
                        a.x, a.y, -ux * push, -uy * push, a.RADIUS)
                    b.x, b.y = self.level.move_with_collisions(
                        b.x, b.y, ux * push, uy * push, b.RADIUS)

    # ------------------------------------------------------------------
    # Objets à ramasser
    # ------------------------------------------------------------------
    def _check_pickups(self):
        player = self.player
        for pickup in self.pickups:
            if pickup.taken:
                continue
            if math.hypot(pickup.x - player.x, pickup.y - player.y) > PICKUP_RADIUS:
                continue
            if pickup.kind == "medkit":
                if player.health >= player.max_health:
                    continue  # reste au sol tant qu'on n'en a pas besoin
                player.health = min(player.max_health, player.health + MEDKIT_HEAL)
                self.sounds.play("heal")
            elif pickup.kind == "lifepack":
                if player.health >= player.max_health:
                    continue
                player.health = player.max_health   # soin complet
                self.particles.spawn_heal_burst(pickup.x, pickup.y)
                self.sounds.play("heal")
                self.hud.show_message("Pack de vie : soin complet !")
            else:
                weapon_id = pickup.kind.split(":", 1)[1]
                result = player.add_weapon(weapon_id, pickup.level_index)
                weapon = next(w for w in player.weapons if w.spec.id == weapon_id)
                self.sounds.play("pickup")
                label = {"new": "Nouvelle arme : ",
                         "upgrade": "Arme améliorée : ",
                         "ammo": "Munitions : "}[result]
                self.hud.show_message(label + weapon.display_name)
            pickup.taken = True

    # ------------------------------------------------------------------
    # Tir du joueur (hitscan, multi-plombs pour le fusil à pompe)
    # ------------------------------------------------------------------
    def _player_fire(self):
        weapon = self.player.weapon
        if not weapon.fire():
            return
        self.sounds.play(weapon.spec.sound, volume_scale=0.9)
        self.hud.on_player_shot()
        if weapon.spec.id in ("shotgun", "minigun"):
            self.shake = min(1.0, self.shake + 0.18)

        self.stats["shots"] += 1
        # En visée, la dispersion est fortement réduite (tir précis).
        spread = weapon.spec.spread * (1.0 - 0.75 * self.player.ads)
        results = []
        for _ in range(weapon.spec.pellets):
            angle = self.player.angle + random.uniform(-spread, spread)
            results.append(self._hitscan(self.player.x, self.player.y, angle,
                                         weapon.damage,
                                         weapon.spec.hit_radius))
        hits = [r for r in results if r is not None]
        if hits:
            self.stats["hits"] += 1
            self.stats["kills"] += sum(1 for r in hits if r == "kill")
            self.hud.on_enemy_hit(killed="kill" in hits)

        # Le bruit du coup de feu attire les ennemis du secteur.
        self._alert_allies((self.player.x, self.player.y), GUNSHOT_HEARING)

    def _hitscan(self, ox, oy, angle, damage, hit_radius=0.35):
        """Résout une balle depuis (ox, oy) : "kill", "hit" ou None (mur).

        Utilisé par le tir du joueur local ET par les tirs des coéquipiers
        en coopération LAN (résolus par l'hôte).
        """
        wall_dist, wall_tile, _, _ = cast_ray(self.level, ox, oy, angle)
        best = None
        best_dist = wall_dist
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dx, dy = enemy.x - ox, enemy.y - oy
            dist = math.hypot(dx, dy)
            if dist >= best_dist:
                continue
            # L'ennemi est touché si l'axe de la balle passe dans son rayon.
            delta = math.atan2(dy, dx) - angle
            delta = (delta + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) < math.atan2(hit_radius, dist):
                best, best_dist = enemy, dist

        if best is None:
            # Impact sur un mur : poussière teintée de la texture touchée.
            hx = ox + math.cos(angle) * (wall_dist - 0.05)
            hy = oy + math.sin(angle) * (wall_dist - 0.05)
            tex = self.level.config["theme"].get(wall_tile)
            color = assets.average_color(tex) if tex else (120, 120, 120)
            self.particles.spawn_wall_dust(hx, hy, color)
            return None

        died = best.take_damage(damage)
        if died:
            self.particles.spawn_death(best.x, best.y)
            self.sounds.play("enemy_die", volume_scale=0.8,
                             pos=(best.x, best.y), listener=self.player)
            if best.EXPLODES:
                self._explode(best)   # un kamikaze abattu détone
            return "kill"
        self.particles.spawn_blood(best.x, best.y)
        self.sounds.play("enemy_hit", volume_scale=0.6,
                         pos=(best.x, best.y), listener=self.player)
        if best.ai_state == "idle":
            # Se faire tirer dessus réveille l'ennemi même sans le voir.
            best.ai_state = "chase"
            best.last_seen = (ox, oy)
        return "hit"

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def draw(self, screen):
        # Billboards : décors, cadavres, ennemis, coéquipiers, objets.
        sprites = list(self.enemies) + self._extra_sprites() + self.props
        for pickup in self.pickups:
            if not pickup.taken:
                pickup.v_offset = 0.12 + pickup.bob_offset(self.time)
                sprites.append(pickup)

        # Horizon : visée verticale + secousse aléatoire du tremblement.
        pitch_px = int(self.player.pitch * self.raycaster.height)
        if self.shake > 0.0:
            pitch_px += int(random.uniform(-1, 1) * self.shake
                            * self.raycaster.height * 0.02)

        self.raycaster.render(screen, self.player, self.level, sprites,
                              self.particles, pitch_px)
        if self.player.ads > 0.01:
            zoom_screen(screen, self.player.zoom)   # lunette de visée
        self.hud.draw(screen, self.player, self.enemies, self.level,
                      self.pickups, fps=self.fps if self.show_fps else None,
                      survival=self.survival_info(), stats=self.stats)
        if self.paused:
            self.hud.draw_pause(screen)

    def survival_info(self):
        """Infos de vagues pour le HUD ; None hors mode survie."""
        return None
