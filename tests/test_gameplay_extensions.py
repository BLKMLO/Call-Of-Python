"""Non-régressions du Colosse, du Déferlement, des décors et du tactile."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import assets
from coop import CoopClientGame
from entities import Boss, Grunt, Pickup, Player, Soldier
from game import Game
from level import LEVELS, SURVIVAL_LEVEL, Level
from raycaster import MOON_CRATER_MIN, MOON_CRATER_SPACING
from settings import DEFAULT_KEYS
from survival import SurvivalGame
from touch_controls import TouchControls


class GameplayExtensionsTests(unittest.TestCase):
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

    def test_possessed_survival_enemies_have_cached_visuals_and_rules(self):
        game = SurvivalGame(self.screen, self.settings, Mock())
        soldier = game.spawn_enemy("soldier", 10.5, 10.5)
        grunt = game.spawn_enemy("grunt", 11.5, 10.5)

        self.assertTrue(soldier.possessed)
        self.assertFalse(soldier.CAN_ROLL)
        self.assertLess(soldier.SPEED, Soldier.SPEED)
        self.assertLess(grunt.SPEED, Grunt.SPEED)
        self.assertFalse(soldier.start_roll(1.0, 0.0))

        base = assets.get("enemy_soldier_idle")
        possessed = soldier.current_sprite(game.player)
        self.assertEqual(possessed.get_size(), base.get_size())
        self.assertNotEqual(
            pygame.image.tostring(possessed, "RGBA"),
            pygame.image.tostring(base, "RGBA"),
        )
        bright_green = any(
            color.g >= 245 and color.g > color.r * 1.5
            for row in range(possessed.get_height())
            for color in (possessed.get_at((possessed.get_width() // 2, row)),)
        )
        self.assertTrue(bright_green)
        self.assertIs(possessed, soldier.current_sprite(game.player))

    def test_colossus_has_three_phases_and_releases_two_lifepacks(self):
        game = Game(self.screen, self.settings, Mock(), level_index=4)
        boss = next(enemy for enemy in game.enemies if isinstance(enemy, Boss))
        initial_pickups = len(game.pickups)

        self.assertEqual(boss.phase, 1)
        self.assertAlmostEqual(boss.FIRE_DELAY, Boss.PHASE_FIRE_DELAYS[0])
        boss.take_damage(boss.max_health * 0.34)
        game._handle_boss_phase_events(boss)
        self.assertEqual(boss.phase, 2)
        self.assertAlmostEqual(boss.SPEED, Boss.PHASE_SPEEDS[1])

        boss.take_damage(boss.max_health * 0.34)
        game._handle_boss_phase_events(boss)
        self.assertEqual(boss.phase, 3)
        self.assertAlmostEqual(boss.FIRE_DELAY, Boss.PHASE_FIRE_DELAYS[2])

        dynamic = [pickup for pickup in game.pickups if pickup.dynamic]
        self.assertEqual(len(game.pickups), initial_pickups + 2)
        self.assertEqual(len(dynamic), 2)
        self.assertEqual({pickup.kind for pickup in dynamic}, {"lifepack"})
        self.assertEqual(len({pickup.net_id for pickup in dynamic}), 2)
        self.assertTrue(all(not pickup.hidden for pickup in dynamic))
        self.assertTrue(all(
            game.level.can_stand(pickup.x, pickup.y, 0.22)
            for pickup in dynamic
        ))

    def test_coop_accepts_possessed_enemy_and_dynamic_pickup_extension(self):
        client = CoopClientGame.__new__(CoopClientGame)
        client.level = Level(4, config=SURVIVAL_LEVEL)
        client.level_index = 4
        client.player = Player(*client.level.player_spawn)
        client.ghosts = {}
        client.synced = False
        client.particles = Mock()
        client.sounds = Mock()
        client.pickups = [
            Pickup(x, y, kind, 1)
            for x, y, kind in client.level.pickup_spawns
        ]
        client.base_pickup_count = len(client.pickups)
        client.dynamic_pickups = {}

        client._apply_enemies([[
            7, "boss", 15.5, 12.5, 0.0, 2100, 1, 0, 0, 0, 0,
            2200, 1,
        ]])
        ghost = client.ghosts[7]
        self.assertTrue(ghost.possessed)
        self.assertEqual(ghost.max_health, 2200)
        self.assertEqual(ghost.health, 2100)

        rows = [0] * client.base_pickup_count
        rows.append([3, 13.5, 12.5, "lifepack", 0])
        client._apply_pickups(rows)
        pickup = client.dynamic_pickups[3]
        self.assertIn(pickup, client.pickups)
        self.assertTrue(pickup.dynamic)
        self.assertFalse(pickup.hidden)

        client.pickups[0].taken = True
        malformed = [float("nan")] + [0] * (client.base_pickup_count - 1)
        malformed.extend([
            [3, 13.5, 12.5, "lifepack", 0],
            [4, 13.5, 12.5, "lifepack", float("nan")],
        ])
        client._apply_pickups(malformed)
        self.assertTrue(client.pickups[0].taken)
        self.assertIn(3, client.dynamic_pickups)
        self.assertNotIn(4, client.dynamic_pickups)

    def test_laboratory_floor_is_white_and_only_boss_walls_are_high(self):
        lab = LEVELS[4]
        for color in lab["floor"]:
            self.assertGreater(sum(color) / 3, 175)
        heights = lab["heights"]
        self.assertEqual(heights.get("1", 1.0), 1.0)
        self.assertEqual(heights.get("2", 1.0), 1.0)
        self.assertEqual(heights.get("4", 1.0), 1.0)
        self.assertGreater(heights["3"], 1.4)

    def test_moon_crater_texture_uses_dense_precalculated_population(self):
        self.assertGreaterEqual(MOON_CRATER_MIN, 30)
        self.assertLessEqual(MOON_CRATER_SPACING, 40)

    def test_touch_controls_enable_on_first_finger_and_track_multitouch(self):
        touch = TouchControls((800, 600), detected=False)
        move_down = pygame.event.Event(
            pygame.FINGERDOWN, finger_id=1, x=0.16, y=0.61,
        )
        self.assertEqual(touch.handle_event(move_down), ())
        self.assertTrue(touch.enabled)
        forward, strafe = touch.movement_axes()
        self.assertGreater(forward, 0.8)
        self.assertAlmostEqual(strafe, 0.0)

        look_down = pygame.event.Event(
            pygame.FINGERDOWN, finger_id=2, x=0.52, y=0.40,
        )
        look_move = pygame.event.Event(
            pygame.FINGERMOTION, finger_id=2, x=0.62, y=0.46,
        )
        touch.handle_event(look_down)
        touch.handle_event(look_move)
        look_x, look_y = touch.consume_look()
        self.assertGreater(look_x, 60)
        self.assertGreater(look_y, 20)

        fire_down = pygame.event.Event(
            pygame.FINGERDOWN, finger_id=3, x=0.88, y=0.77,
        )
        self.assertEqual(touch.handle_event(fire_down), ("fire_down",))
        self.assertTrue(touch.fire_held)
        fire_up = pygame.event.Event(
            pygame.FINGERUP, finger_id=3, x=0.88, y=0.77,
        )
        self.assertEqual(touch.handle_event(fire_up), ("fire_up",))
        self.assertFalse(touch.fire_held)

        screen = pygame.Surface((800, 600))
        touch.draw(screen)
        self.assertNotEqual(screen.get_at((704, 462))[:3], (0, 0, 0))

    def test_game_maps_touch_buttons_and_ignores_emulated_mouse_click(self):
        game = Game(self.screen, self.settings, Mock(), level_index=0)
        game.touch.enabled = True
        ammo = game.player.weapon.ammo

        game.handle_event(pygame.event.Event(
            pygame.FINGERDOWN, finger_id=10, x=0.88, y=0.77,
        ))
        self.assertEqual(game.player.weapon.ammo, ammo - 1)
        game.handle_event(pygame.event.Event(
            pygame.FINGERUP, finger_id=10, x=0.88, y=0.77,
        ))
        after_touch = game.player.weapon.ammo

        game.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=(704, 462), touch=True,
        ))
        self.assertEqual(game.player.weapon.ammo, after_touch)

        game.handle_event(pygame.event.Event(
            pygame.FINGERDOWN, finger_id=11, x=0.69, y=0.75,
        ))
        self.assertTrue(game.player.rolling)


if __name__ == "__main__":
    unittest.main()
