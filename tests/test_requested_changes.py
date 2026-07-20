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
from entities import PORTAL_FRAME_MS, PORTAL_FRAMES, PROP_SPECS, Prop, Sniper
from level import LEVELS, MAP_LAB, SURVIVAL_LEVEL, Level
from raycaster import Raycaster


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

    def test_colossus_seal_is_visible_on_the_wall_behind_the_boss(self):
        self.assertEqual(MAP_LAB[19][25], "B")
        # Une case au-dessus de l'axe exact : derrière son épaule, donc visible
        # au lieu d'être entièrement occulté par le billboard du Colosse.
        self.assertEqual(MAP_LAB[18][28], "4")
        self.assertEqual(MAP_LAB[19][28], "3")
        self.assertEqual(LEVELS[4]["theme"]["4"], "wall_sealed_portal")
        self.assertEqual(assets.get("wall_sealed_portal").get_size(), (64, 64))

    def test_lunar_portal_cycles_prebuilt_equal_sized_frames(self):
        portal = Prop(15.5, 12.5, "portal")
        frames = [assets.get(name) for name in PORTAL_FRAMES]
        self.assertTrue(all(frame.get_size() == frames[0].get_size()
                            for frame in frames))
        pixels = {pygame.image.tostring(frame, "RGBA") for frame in frames}
        self.assertEqual(len(pixels), len(frames))
        with patch("entities.pygame.time.get_ticks", return_value=0):
            self.assertIs(portal.current_sprite(), frames[0])
        with patch("entities.pygame.time.get_ticks", return_value=PORTAL_FRAME_MS):
            self.assertIs(portal.current_sprite(), frames[1])

    def test_cover_reduces_only_partial_exposure(self):
        self.assertAlmostEqual(cover_adjusted_chance(0.8, 1.0), 0.8)
        self.assertLess(cover_adjusted_chance(0.8, 0.5), 0.8 * 0.675)
        self.assertAlmostEqual(cover_adjusted_chance(0.8, 0.0), 0.224)

    def test_sniper_waits_075_seconds_before_firing(self):
        sniper = Sniper(1.5, 1.5)
        ai = EnemyAI(sniper)
        player = SimpleNamespace(
            x=8.5, y=1.5, RADIUS=0.25, alive=True, health=100,
            take_damage=lambda amount: None,
        )

        self.assertEqual(ai._try_shoot(player, None, 7.0), [])
        self.assertTrue(sniper.aiming)
        self.assertAlmostEqual(sniper.aim_timer, 0.75)
        sniper.update_timers(0.74)
        self.assertEqual(ai._try_shoot(player, None, 7.0), [])

        # Dépasse très légèrement le seuil pour éviter le bruit flottant de
        # 0.74 + 0.01 ; en jeu, le tir part à la première frame après 0,75 s.
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

    def test_other_ranged_fire_sprites_keep_their_idle_scale(self):
        # Le sniper est contrôlé séparément entre sa pose de visée accroupie
        # et son tir. Ici, on verrouille les cinq personnages qui tirent debout.
        for kind in ("grunt", "soldier", "heavy", "boss", "ally"):
            idle = assets.get(f"enemy_{kind}_idle").get_bounding_rect(min_alpha=8)
            fire = assets.get(f"enemy_{kind}_fire").get_bounding_rect(min_alpha=8)
            self.assertLessEqual(abs(fire.height - idle.height), 6, kind)
            self.assertEqual(fire.bottom, idle.bottom, kind)

    def test_laboratory_uses_dedicated_white_walls(self):
        lab_theme = LEVELS[4]["theme"]
        self.assertEqual(lab_theme["1"], "wall_lab_tech")
        self.assertEqual(lab_theme["2"], "wall_lab_metal")
        self.assertEqual(lab_theme["3"], "wall_lab_reinforced")
        for name in (lab_theme["1"], lab_theme["2"], lab_theme["3"]):
            color = pygame.transform.average_color(assets.get(name))[:3]
            self.assertGreater(sum(color) / 3, 175, name)

    def test_clouds_exist_in_campaign_but_not_on_the_moon(self):
        campaign = Raycaster((320, 240), Level(0))
        moon = Raycaster((320, 240), Level(4, config=SURVIVAL_LEVEL))
        self.assertIsNotNone(campaign.cloud_panorama)
        self.assertGreater(campaign.cloud_panorama.get_bounding_rect().height, 0)
        self.assertIsNone(moon.cloud_panorama)


if __name__ == "__main__":
    unittest.main()
