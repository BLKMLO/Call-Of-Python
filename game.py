"""Boucle de gameplay : relie le niveau, le joueur, les ennemis, le rendu.

`Game` est créé à chaque partie (bouton "Jouer") et exposé à `main.py`
via trois méthodes : `handle_event`, `update`, `draw`. Sa propriété
`outcome` vaut None tant que la partie est en cours, puis "dead" ou
"victory".
"""

import math

import pygame

from ai import EnemyAI
from entities import Enemy, Player
from hud import HUD
from level import Level
from raycaster import Raycaster, cast_ray


class Game:
    def __init__(self, screen, settings, sounds):
        self.settings = settings
        self.sounds = sounds
        self.level = Level()
        self.player = Player(*self.level.player_spawn)
        self.enemies = [Enemy(x, y) for x, y in self.level.enemy_spawns]
        self.ais = [EnemyAI(enemy) for enemy in self.enemies]
        self.raycaster = Raycaster(screen.get_size())
        self.hud = HUD(screen.get_size())
        self.paused = False
        self.outcome = None      # None (en cours), "dead" ou "victory"
        self.end_delay = 0.0     # petit délai avant l'écran de fin
        pygame.mouse.get_rel()   # purge le mouvement accumulé dans les menus

    # ------------------------------------------------------------------
    # Événements ponctuels (clics, touches)
    # ------------------------------------------------------------------
    def handle_event(self, event):
        """Retourne "menu" si le joueur demande à quitter la partie, sinon None."""
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.paused = not self.paused
                pygame.mouse.get_rel()  # évite un saut de caméra à la reprise
            elif self.paused and event.key == pygame.K_m:
                return "menu"
            elif event.key == self.settings.keys["recharger"]:
                self.player.weapon.start_reload()
                if self.player.weapon.reloading > 0.0:
                    self.sounds.play("reload")
        return None

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------
    def update(self, dt):
        if self.paused or self.outcome is not None and self.end_delay > 0.8:
            return

        player = self.player

        if player.alive:
            # Visée à la souris (mouvement relatif, curseur capturé).
            mouse_dx, _ = pygame.mouse.get_rel()
            player.rotate(mouse_dx, self.settings.mouse_factor())

            # Déplacements clavier.
            keys = pygame.key.get_pressed()
            old_pos = (player.x, player.y)
            player.move(dt, keys, self.settings.keys, self.level)
            moving = (player.x, player.y) != old_pos

            # Tir maintenu (arme automatique).
            if pygame.mouse.get_pressed()[0]:
                self._player_fire()

            player.update(dt)
            self.hud.update(dt, moving)

        # IA des ennemis → événements convertis en sons/feedback.
        for ai in self.ais:
            for event, _data in ai.update(dt, player, self.level):
                if event == "enemy_shot":
                    self.sounds.play("enemy_shot", volume_scale=0.8)
                elif event == "player_hit":
                    self.sounds.play("player_hit")

        # Conditions de fin (avec un léger délai pour "encaisser" la scène).
        if self.outcome is None:
            if not player.alive:
                self.outcome = "dead"
            elif all(not enemy.alive for enemy in self.enemies):
                self.outcome = "victory"
        else:
            self.end_delay += dt

    @property
    def finished(self):
        """Vrai quand l'écran de fin peut être affiché."""
        return self.outcome is not None and self.end_delay > 0.8

    # ------------------------------------------------------------------
    # Tir du joueur (hitscan)
    # ------------------------------------------------------------------
    def _player_fire(self):
        weapon = self.player.weapon
        if not weapon.fire():
            return
        self.sounds.play("player_shot", volume_scale=0.9)
        self.hud.on_player_shot()

        # Distance au mur dans l'axe de visée : un ennemi derrière un mur
        # ne peut pas être touché.
        wall_dist, _, _ = cast_ray(self.level, self.player.x, self.player.y,
                                   self.player.angle)

        best = None
        best_dist = wall_dist
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            dx, dy = enemy.x - self.player.x, enemy.y - self.player.y
            dist = math.hypot(dx, dy)
            if dist >= best_dist:
                continue
            # L'ennemi est touché si l'axe de visée passe dans son rayon.
            delta = math.atan2(dy, dx) - self.player.angle
            delta = (delta + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) < math.atan2(weapon.hit_radius, dist):
                best, best_dist = enemy, dist

        if best is not None:
            died = best.take_damage(weapon.damage)
            self.sounds.play("enemy_die" if died else "enemy_hit", volume_scale=0.7)
            if not died and best.ai_state == "idle":
                # Se faire tirer dessus réveille l'ennemi même sans le voir.
                best.ai_state = "chase"
                best.last_seen = (self.player.x, self.player.y)

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def draw(self, screen):
        self.raycaster.render(screen, self.player, self.level, self.enemies)
        self.hud.draw(screen, self.player, self.enemies, self.level)
        if self.paused:
            self.hud.draw_pause(screen)
