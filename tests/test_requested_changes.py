"""Régressions ciblées pour les corrections graphiques et le sniper."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import assets
from ai import EnemyAI, cover_adjusted_chance
from coop import CoopClientGame
from entities import PROP_SPECS, Sniper
from level import MAP_LAB


class RequestedChangesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_car_has_safe_padding_in_front(self):
        sprite = assets.get("prop_car")
        bounds = sprite.get_bounding_rect(min_alpha=8)
        self.assertGreater(bounds.x, 0)
        self.assertLess(bounds.right, sprite.get_width())

    def test_government_seat_is_single_seat_scale(self):
        sprite = assets.get("prop_bench")
        bounds = sprite.get_bounding_rect(min_alpha=8)
        self.assertLess(bounds.width, bounds.height)
        self.assertLessEqual(PROP_SPECS["bench"]["width"], 0.5)

    def test_lab_has_no_free_standing_door_near_boss_wing(self):
        self.assertEqual(MAP_LAB[14][23], "2")
        for y, row in enumerate(MAP_LAB):
            for x, tile in enumerate(row):
                if tile != "D":
                    continue
                horizontal = MAP_LAB[y][x - 1] != "." and MAP_LAB[y][x + 1] != "."
                vertical = MAP_LAB[y - 1][x] != "." and MAP_LAB[y + 1][x] != "."
                self.assertTrue(horizontal or vertical, (x, y))

    def test_cover_reduces_only_partial_exposure(self):
        self.assertAlmostEqual(cover_adjusted_chance(0.8, 1.0), 0.8)
        self.assertLess(cover_adjusted_chance(0.8, 0.5), 0.8 * 0.675)
        self.assertAlmostEqual(cover_adjusted_chance(0.8, 0.0), 0.224)

    def test_sniper_waits_125_seconds_before_firing(self):
        sniper = Sniper(1.5, 1.5)
        ai = EnemyAI(sniper)
        player = SimpleNamespace(
            x=8.5, y=1.5, RADIUS=0.25, alive=True, health=100,
            take_damage=lambda amount: None,
        )

        self.assertEqual(ai._try_shoot(player, None, 7.0), [])
        self.assertTrue(sniper.aiming)
        self.assertAlmostEqual(sniper.aim_timer, 1.25)
        sniper.update_timers(1.24)
        self.assertEqual(ai._try_shoot(player, None, 7.0), [])

        # Dépasse très légèrement le seuil pour éviter le bruit flottant de
        # 1.24 + 0.01 ; en jeu, le tir part à la première frame après 1,25 s.
        sniper.update_timers(0.02)
        with patch("ai.exposure_fraction", return_value=1.0), \
                patch("ai.random.random", return_value=1.0):
            events = ai._try_shoot(player, None, 7.0)
        self.assertEqual([event[0] for event in events], ["enemy_shot"])
        self.assertFalse(sniper.aiming)
        self.assertGreater(sniper.fire_cooldown, 0.0)

    def test_sniper_aim_pose_and_lost_sight_cancellation(self):
        sniper = Sniper(1.5, 1.5)
        ai = EnemyAI(sniper)
        player = SimpleNamespace(x=8.5, y=1.5, RADIUS=0.25, alive=True)
        ai._try_shoot(player, None, 7.0)
        self.assertIs(sniper.current_sprite(player), assets.get("enemy_sniper_aim"))

        with patch("ai.has_line_of_sight", return_value=False):
            self.assertEqual(ai._peek_and_shoot(0.1, player, None, 7.0), [])
        self.assertFalse(sniper.aiming)

    def test_sniper_does_not_change_scale_when_the_shot_fires(self):
        aim_bounds = assets.get("enemy_sniper_aim").get_bounding_rect(min_alpha=8)
        fire_bounds = assets.get("enemy_sniper_fire").get_bounding_rect(min_alpha=8)
        self.assertEqual(aim_bounds.size, fire_bounds.size)
        self.assertEqual(aim_bounds.bottom, fire_bounds.bottom)

    def test_coop_snapshot_accepts_old_format_and_syncs_aim_pose(self):
        client = CoopClientGame.__new__(CoopClientGame)
        client.ghosts = {}
        client.synced = False

        old_snapshot = [[7, "sniper", 2.5, 3.5, 0.0, 70, 0, 0]]
        client._apply_enemies(old_snapshot)
        self.assertFalse(client.ghosts[7].aiming)

        new_snapshot = [[7, "sniper", 2.5, 3.5, 0.0, 70, 0, 0, 1]]
        client._apply_enemies(new_snapshot)
        self.assertTrue(client.ghosts[7].aiming)


if __name__ == "__main__":
    unittest.main()
