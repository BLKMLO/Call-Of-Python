"""Non-régressions de la passe correctifs et performances.

Couvre les bugs corrigés (animation de marche figée, branche de couverture
suspendue au test kamikaze, gâchette manette qui rendait les armes
semi-automatiques automatiques) et prouve que les optimisations de rendu et
de perception ne changent aucun résultat.
"""

import math
import os
import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import entities
import raycaster
from ai import EnemyAI
from entities import Kamikaze, Player, Soldier
from game import Game
from gamepad import GamepadInput
from hud import HUD
from level import LEVELS, SURVIVAL_LEVEL, Level
from raycaster import Raycaster, cast_ray, cast_ray_layers, has_line_of_sight
from settings import DEFAULT_KEYS
from touch_controls import TouchControls


def _reference_layers(level, ox, oy, angle, heights, screen_dist, horizon,
                      ray_cos, max_depth=raycaster.MAX_DEPTH):
    """Traversée d'origine : parcourt la carte entière derrière chaque mur."""
    grid = level.grid
    width, height = level.width, level.height
    doors = level.doors
    sin_a = math.sin(angle) or 1e-8
    cos_a = math.cos(angle) or 1e-8
    map_x, map_y = int(ox), int(oy)
    step_x = 1 if cos_a > 0 else -1
    step_y = 1 if sin_a > 0 else -1
    t_max_x = ((map_x + 1 if step_x > 0 else map_x) - ox) / cos_a
    t_max_y = ((map_y + 1 if step_y > 0 else map_y) - oy) / sin_a
    t_delta_x, t_delta_y = step_x / cos_a, step_y / sin_a
    hits = []
    highest_top = float(horizon + 1)
    for _ in range(max_depth * 3):
        if t_max_x < t_max_y:
            map_x += step_x
            depth = t_max_x * ray_cos
            t_max_x += t_delta_x
            vertical = True
        else:
            map_y += step_y
            depth = t_max_y * ray_cos
            t_max_y += t_delta_y
            vertical = False
        if not (0 <= map_x < width and 0 <= map_y < height) or depth > max_depth:
            break
        tile = grid[map_y][map_x]
        if tile == ".":
            continue
        off = ((oy + depth / ray_cos * sin_a) if vertical
               else (ox + depth / ray_cos * cos_a)) % 1.0
        if tile == "D":
            gap = doors[(map_x, map_y)]["open"] if (map_x, map_y) in doors else 0.0
            if off >= gap:
                off -= gap
            else:
                continue
        depth = max(depth, 0.02)
        top = horizon + screen_dist / depth * (0.5 - heights.get(tile, 1.0))
        if top < highest_top:
            hits.append((depth, tile, vertical, off))
            highest_top = top
            if highest_top <= 0:
                break
    return hits


def _reference_line_of_sight(level, x0, y0, x1, y1):
    """Ligne de vue d'origine : rayon toujours lancé sur toute sa portée."""
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 1e-6:
        return True
    angle = math.atan2(y1 - y0, x1 - x0)
    if level.first_cover_hit(x0, y0, angle, dist) < dist - 0.05:
        return False
    depth, _, _, _ = cast_ray(level, x0, y0, angle)
    return depth > dist - 0.05


class _CountingFont:
    """Police déléguée qui compte les rendus de glyphes (types C non patchables)."""

    def __init__(self, font):
        self._font = font
        self.calls = 0

    def render(self, *args, **kwargs):
        self.calls += 1
        return self._font.render(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._font, name)


def _walkable(level):
    return [(x + 0.5, y + 0.5)
            for y in range(level.height) for x in range(level.width)
            if level.grid[y][x] == "." and (x, y) not in level.prop_tiles]


class BugfixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((800, 600))
        cls.screen = pygame.display.get_surface()
        cls.settings = SimpleNamespace(
            keys=dict(DEFAULT_KEYS),
            invert_mouse=False,
            mouse_factor=lambda: 0.0022,
        )

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_walking_enemy_alternates_its_two_poses(self):
        """`anim_time` restait à zéro : tous les ennemis marchaient figés."""
        level = Level(0)
        player = Player(*level.player_spawn)
        # Hors portée de tir mais dans la portée de détection : il marche.
        enemy = Soldier(player.x + 10.0, player.y)
        enemy.ai_state = "chase"
        enemy.last_seen = (player.x, player.y)
        ai = EnemyAI(enemy)

        poses = set()
        walking = 0
        for _ in range(90):
            ai.update(1 / 60, player, level)
            if enemy.moving:
                walking += 1
                poses.add("walk" if int(enemy.anim_time * 6) % 2 == 0
                          else "walk2")
        self.assertGreater(walking, 30)
        # Le compteur suit les pas effectués (au pas de simulation près : il
        # est incrémenté d'après l'état de déplacement de la frame précédente).
        self.assertAlmostEqual(enemy.anim_time, walking / 60.0, delta=0.02)
        self.assertEqual(poses, {"walk", "walk2"})

    def test_kamikaze_still_detonates_at_contact(self):
        """La branche « couverture » ne conditionne plus l'explosion."""
        level = Level(0)
        player = Player(*level.player_spawn)
        enemy = Kamikaze(player.x + 0.4, player.y)
        enemy.ai_state = "chase"
        ai = EnemyAI(enemy)
        with patch("ai.has_line_of_sight", return_value=True):
            events = ai.update(1 / 60, player, level)
        self.assertIn("explode", [name for name, _ in events])

    def test_enemy_in_cover_state_still_moves_and_returns_to_chase(self):
        """L'état « cover » ne dépendait plus que du test kamikaze."""
        level = Level(0)
        player = Player(*level.player_spawn)
        enemy = Soldier(player.x + 5.0, player.y)
        enemy.health = 10
        ai = EnemyAI(enemy)
        ai.took_cover = True          # la retraite a déjà été décidée
        enemy.ai_state = "cover"
        enemy.cover_target = (enemy.x + 1.5, enemy.y)
        start = (enemy.x, enemy.y)

        for _ in range(60):
            ai.update(1 / 60, player, level)
            if enemy.ai_state != "cover":
                break
        self.assertNotEqual((enemy.x, enemy.y), start)
        self.assertEqual(enemy.ai_state, "chase")   # abri atteint

    def test_gamepad_trigger_fires_once_until_released(self):
        """Consommer les actions ne doit pas recréer un front de gâchette."""
        pad = GamepadInput.__new__(GamepadInput)
        pad.controller = object()
        pad._buttons = {}
        pad._actions = []
        pad._fire_was_held = False
        held = {"value": True}
        with patch.object(GamepadInput, "connected", property(lambda _: True)), \
             patch.object(GamepadInput, "_button", lambda *_: False), \
             patch.object(GamepadInput, "fire_held",
                          property(lambda _: held["value"])):
            pad.update()
            self.assertEqual(pad.consume_actions(), ("fire",))
            pad.update()
            self.assertEqual(pad.consume_actions(), ())
            held["value"] = False
            pad.update()
            pad.consume_actions()
            held["value"] = True
            pad.update()
            self.assertEqual(pad.consume_actions(), ("fire",))


class RenderEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((640, 400))
        cls.screen = pygame.display.get_surface()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_layered_ray_stops_early_without_losing_a_wall(self):
        rng = random.Random(20260815)
        checks = 0
        for index, config in enumerate(list(LEVELS) + [SURVIVAL_LEVEL]):
            level = Level(min(index, 4), config=config)
            for position, door in enumerate(level.doors.values()):
                door["open"] = (position % 5) * 0.2   # couvre le cas 'D'
            heights = config.get("heights", {})
            max_height = max(1.0, max(heights.values(), default=1.0))
            free = _walkable(level)
            for _ in range(120):
                ox, oy = rng.choice(free)
                ox += rng.uniform(-0.4, 0.4)
                oy += rng.uniform(-0.4, 0.4)
                angle = rng.uniform(-10.0, 10.0)
                ray_cos = math.cos(rng.uniform(-0.6, 0.6))
                self.assertEqual(
                    cast_ray_layers(level, ox, oy, angle, heights, 913.0, 200,
                                    ray_cos, max_height=max_height),
                    _reference_layers(level, ox, oy, angle, heights, 913.0,
                                      200, ray_cos),
                )
                checks += 1
        self.assertGreaterEqual(checks, 700)

    def test_bounded_line_of_sight_matches_full_range_ray(self):
        rng = random.Random(4242)
        for index, config in enumerate(list(LEVELS) + [SURVIVAL_LEVEL]):
            level = Level(min(index, 4), config=config)
            free = _walkable(level)
            for _ in range(150):
                ox, oy = rng.choice(free)
                tx, ty = rng.choice(free)
                self.assertEqual(
                    has_line_of_sight(level, ox, oy, tx, ty),
                    _reference_line_of_sight(level, ox, oy, tx, ty),
                )

    def test_sprite_strips_merge_without_changing_the_frame(self):
        """Les colonnes voisines fusionnées doivent donner la même image."""
        level = Level(0)
        caster = Raycaster(self.screen.get_size(), level)
        player = Player(*level.player_spawn)
        enemies = [Soldier(x, y) for x, y, _kind in level.enemy_spawns[:8]]

        def per_column(screen, player_, sprites):
            """Rendu de référence : une tranche de 2 px par colonne."""
            for obj in sprites:
                projected = caster._project(player_, obj.x, obj.y)
                if projected is None:
                    continue
                proj_dist, delta = projected
                proj = caster.screen_dist / max(proj_dist,
                                                raycaster.MIN_SPRITE_DIST)
                sprite = obj.current_sprite(player_)
                ratio = sprite.get_width() / sprite.get_height()
                h = int(proj * obj.SPRITE_HEIGHT) & ~1
                w = max(2, int(h * ratio) & ~1)
                if h < 2 or h > caster.height * 4:
                    continue
                scaled = caster._scaled_sprite(sprite, w, h)
                screen_x = int((0.5 + delta / caster.fov) * caster.width) - w // 2
                bottom = caster.horizon + int(
                    proj * (0.5 - getattr(obj, "v_offset", 0.0)))
                top = bottom - h
                first = max(0, screen_x // raycaster.COLUMN_WIDTH)
                last = min(caster.num_rays - 1,
                           (screen_x + w) // raycaster.COLUMN_WIDTH)
                for ray in range(first, last + 1):
                    if caster.z_buffer[ray] < proj_dist:
                        continue
                    strip_x = max(screen_x, ray * raycaster.COLUMN_WIDTH)
                    strip_end = min(screen_x + w,
                                    (ray + 1) * raycaster.COLUMN_WIDTH)
                    if strip_end - strip_x <= 0:
                        continue
                    screen.blit(scaled, (strip_x, top),
                                (strip_x - screen_x, 0,
                                 strip_end - strip_x, h))

        merged = pygame.Surface(self.screen.get_size())
        column = pygame.Surface(self.screen.get_size())
        for frame in range(12):
            player.angle = frame * math.tau / 12
            caster._render_walls(merged, player, level)
            column.blit(merged, (0, 0))
            caster._render_sprites(merged, player, enemies)
            per_column(column, player, enemies)
            self.assertEqual(pygame.image.tostring(merged, "RGB"),
                             pygame.image.tostring(column, "RGB"))

    def test_rotate_zoom_covers_the_screen_and_reuses_its_buffer(self):
        self.screen.fill((20, 40, 60))
        first = raycaster.rotate_zoom_screen(self.screen, 16.0, 1.5)
        width, height = self.screen.get_size()
        self.assertGreaterEqual(first.get_width(), width)
        self.assertGreaterEqual(first.get_height(), height)
        second = raycaster.rotate_zoom_screen(self.screen, 16.0, 1.5)
        self.assertIs(first, second)      # tampon réutilisé, pas réalloué
        plain = raycaster.rotate_zoom_screen(self.screen, 0.0, 1.0)
        self.assertEqual(plain.get_size(), (width, height))


class HotPathCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((800, 600))
        cls.screen = pygame.display.get_surface()
        cls.settings = SimpleNamespace(
            keys=dict(DEFAULT_KEYS),
            invert_mouse=False,
            mouse_factor=lambda: 0.0022,
        )

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_sprite_bounds_are_measured_once_per_asset(self):
        """Chaque apparition scannait tous les pixels de deux PNG."""
        entities._visible_bounds_cache.clear()
        measured = []
        original = entities._visible_bounds

        def counting(sprite_name):
            if sprite_name not in entities._visible_bounds_cache:
                measured.append(sprite_name)
            return original(sprite_name)

        with patch.object(entities, "_visible_bounds", counting):
            soldiers = [Soldier(2.5 + index * 0.01, 2.5)
                        for index in range(12)]
        self.assertEqual(len(soldiers), 12)
        # Une seule mesure par PNG (pose de repos + cadavre), pas par ennemi.
        self.assertEqual(sorted(measured),
                         ["enemy_soldier_dead", "enemy_soldier_idle"])
        self.assertEqual(soldiers[0].SPRITE_HEIGHT, soldiers[-1].SPRITE_HEIGHT)

    def test_hud_counters_reuse_their_rendered_glyphs(self):
        hud = HUD((800, 600))
        game = Game(self.screen, self.settings, Mock(), level_index=0)
        counter = _CountingFont(hud.font)
        hud.font = counter
        hud._draw_status(self.screen, game.player, game.enemies,
                         None, game.stats)
        rendered = counter.calls
        self.assertGreater(rendered, 0)
        hud._draw_status(self.screen, game.player, game.enemies,
                         None, game.stats)
        self.assertEqual(counter.calls, rendered)   # tout vient du cache
        game.player.health -= 1
        hud._draw_status(self.screen, game.player, game.enemies,
                         None, game.stats)
        self.assertEqual(counter.calls, rendered + 1)

    def test_touch_overlay_is_composed_once_per_resolution(self):
        touch = TouchControls((800, 600), detected=True)
        static = touch._overlay
        counter = _CountingFont(touch._font)
        touch._font = counter
        touch.draw(self.screen)
        touch.fire_fingers.add(1)
        touch.draw(self.screen, paused=True)
        self.assertEqual(counter.calls, 0)          # libellés déjà composés
        self.assertIs(touch._overlay, static)
        touch.resize((1024, 768))
        self.assertIsNot(touch._overlay, static)
        self.assertEqual(touch._overlay.get_size(), (1024, 768))
        self.assertEqual(counter.calls, 0)          # nouvelle police au resize


if __name__ == "__main__":
    unittest.main()
