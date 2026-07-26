"""Régressions ciblées pour les corrections graphiques et le sniper."""

import os
import unittest
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import assets
from ai import EnemyAI, cover_adjusted_chance
from coop import CoopClientGame
from entities import (PORTAL_FRAME_MS, PORTAL_FRAMES, PROP_SPECS, Grunt,
                      Player, Prop, Sniper, Soldier)
from game import Game
from level import LEVELS, MAP_LAB, MAP_MOON, SURVIVAL_LEVEL, Level
from raycaster import Raycaster, has_line_of_sight
from settings import DEFAULT_KEYS


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
        self.assertTrue(all(frame.get_at((0, 0)).a == 0 for frame in frames))
        self.assertGreater(portal.v_offset, 0.0)

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

        rolling_snapshot = [[8, "soldier", 4.5, 3.5, 0.0, 100,
                             0, 0, 0, 1, 0.8]]
        client._apply_enemies(rolling_snapshot)
        self.assertTrue(client.ghosts[8].rolling)
        self.assertAlmostEqual(client.ghosts[8].roll_timer, 0.8)

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

    def test_grunt_is_fifty_percent_faster_without_faster_fire(self):
        self.assertAlmostEqual(Grunt.SPEED, 1.7 * 1.5)
        self.assertAlmostEqual(Grunt.FIRE_DELAY, 1.3)

    def test_player_roll_has_fair_iframe_window_without_cooldown(self):
        level = Level(0)
        player = Player(*level.player_spawn)
        keys = defaultdict(bool)
        self.assertIn("roulade", DEFAULT_KEYS)
        self.assertNotIn("sprint", DEFAULT_KEYS)
        self.assertTrue(player.start_roll(keys, DEFAULT_KEYS))
        self.assertEqual(player.roll_sequence, 1)
        self.assertAlmostEqual(player.roll_dx, 1.0)
        health = player.health
        # L'amorce est lisible et vulnérable : la touche n'est pas un bouton
        # de parade instantanée lorsque la balle a déjà atteint le joueur.
        player.take_damage(20)
        self.assertEqual(player.health, health - 20)
        self.assertFalse(player.start_roll(keys, DEFAULT_KEYS))

        # Le cœur du mouvement protège pendant 0,30 s, puis la récupération
        # redevient vulnérable avant que le déplacement soit tout à fait fini.
        player.update(0.09)
        player.take_damage(20)
        self.assertEqual(player.health, health - 20)
        player.update(0.30)
        player.take_damage(20)
        self.assertEqual(player.health, health - 40)
        self.assertFalse(player.start_roll(keys, DEFAULT_KEYS))
        player.update(0.17)
        self.assertTrue(player.start_roll(keys, DEFAULT_KEYS))
        self.assertEqual(player.roll_sequence, 2)
        self.assertEqual(player.roll_cooldown, 0.0)

    def test_fast_roll_is_substepped_and_cannot_cross_a_wall(self):
        level = Level(0)
        level.grid = [list("111111"), list("1.1..1"), list("111111")]
        level.width, level.height = 6, 3
        level.prop_tiles = set()
        player = Player(1.5, 1.5)
        keys = defaultdict(bool)
        player.start_roll(keys, DEFAULT_KEYS)
        player.move(0.5, keys, DEFAULT_KEYS, level)
        self.assertLess(player.x, 1.8)

    def test_soldier_roll_has_three_frames_one_second_iframes_and_cooldown(self):
        soldier = Soldier(2.5, 2.5)
        self.assertTrue(soldier.start_roll(0.0, 1.0))
        health = soldier.health
        soldier.take_damage(30)
        self.assertEqual(soldier.health, health)
        frames = [assets.get(f"enemy_soldier_roll_{index}")
                  for index in range(3)]
        self.assertTrue(all(frame.get_size() == (64, 96) for frame in frames))
        self.assertEqual(len({pygame.image.tostring(frame, "RGBA")
                              for frame in frames}), 3)

        soldier.update_timers(1.01)
        soldier.take_damage(30)
        self.assertEqual(soldier.health, health - 30)
        self.assertFalse(soldier.start_roll(1.0, 0.0))
        soldier.update_timers(2.0)
        self.assertTrue(soldier.start_roll(1.0, 0.0))

    def test_soldier_ai_chooses_a_lateral_roll_and_suspends_fire(self):
        level = Level(0)
        level.grid = [["1" if x in (0, 9) or y in (0, 7) else "."
                       for x in range(10)] for y in range(8)]
        level.width, level.height = 10, 8
        level.prop_tiles = set()
        level.cover_circles = []
        soldier = Soldier(4.5, 4.5)
        ai = EnemyAI(soldier)
        soldier.roll_cooldown = 0.0
        player = Player(7.5, 4.5)
        self.assertTrue(ai._start_side_roll(player, level))
        old_position = (soldier.x, soldier.y)
        events = ai.update(0.1, player, level)
        self.assertEqual(events, [])
        self.assertNotEqual((soldier.x, soldier.y), old_position)
        self.assertAlmostEqual(soldier.x, old_position[0], places=5)

    def test_soldier_reacts_to_a_hit_on_next_ai_step_when_ready(self):
        level = Level(0)
        level.grid = [["1" if x in (0, 9) or y in (0, 7) else "."
                       for x in range(10)] for y in range(8)]
        level.width, level.height = 10, 8
        level.prop_tiles = set()
        level.cover_circles = []
        soldier = Soldier(4.5, 4.5)
        ai = EnemyAI(soldier)
        # Le délai aléatoire de roulade proactive ne doit pas empêcher la
        # toute première réaction défensive à une balle.
        self.assertEqual(soldier.roll_cooldown, 0.0)
        self.assertGreater(ai.proactive_roll_delay, 0.0)
        soldier.hit_roll_request = (7.5, 4.5)
        player = Player(7.5, 4.5)

        ai.update(0.01, player, level)

        self.assertIsNone(soldier.hit_roll_request)
        self.assertTrue(soldier.rolling)
        self.assertEqual(soldier.ai_state, "chase")
        self.assertAlmostEqual(soldier.roll_dx, 0.0, places=5)
        self.assertAlmostEqual(abs(soldier.roll_dy), 1.0, places=5)

    def test_hit_reaction_waits_until_all_pellets_are_resolved(self):
        soldier = Soldier(4.5, 4.5)
        soldier.roll_cooldown = 0.0
        game = Game.__new__(Game)
        game.level = SimpleNamespace(
            first_cover_hit=lambda *_args: 20.0,
            config={"theme": {"1": "wall_stone"}},
        )
        game.enemies = [soldier]
        game.particles = SimpleNamespace(
            spawn_wall_dust=lambda *_args: None,
            spawn_death=lambda *_args: None,
            spawn_blood=lambda *_args: None,
        )
        game.sounds = SimpleNamespace(play=lambda *_args, **_kwargs: None)
        game.player = Player(2.5, 4.5)

        # Deux projectiles du même coup touchent avant le prochain pas d'IA.
        with patch("game.cast_ray", return_value=(20.0, "1", 0, 0)):
            self.assertEqual(game._hitscan(2.5, 4.5, 0.0, 10), "hit")
            self.assertEqual(game._hitscan(2.5, 4.5, 0.0, 10), "hit")

        self.assertEqual(soldier.health, soldier.max_health - 20)
        self.assertEqual(soldier.hit_roll_request, (2.5, 4.5))
        self.assertFalse(soldier.rolling)

    def test_lunar_crystals_replace_fissures_and_block_sight(self):
        self.assertNotIn("V", "".join(MAP_MOON))
        self.assertGreater("".join(MAP_MOON).count("k"), 0)
        moon = Level(4, config=SURVIVAL_LEVEL)
        self.assertTrue(moon.cover_circles)
        cx, cy, _radius = moon.cover_circles[0]
        self.assertFalse(has_line_of_sight(moon, cx - 1.2, cy,
                                          cx + 1.2, cy))
        self.assertEqual(assets.get("prop_alien_crystal").get_size(), (96, 112))
        self.assertTrue(SURVIVAL_LEVEL["moon_ground"])

    def test_menu_background_is_lunar_widescreen_art(self):
        self.assertEqual(assets.get("menu_background").get_size(), (1280, 720))


if __name__ == "__main__":
    unittest.main()
