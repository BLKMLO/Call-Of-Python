"""Non-régressions de la refonte du Déferlement (octobre 2026)."""

import math
import os
import sys
import tempfile
import unittest
from collections import defaultdict
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import settings as settings_module
import survival
from entities import ENEMY_TYPES, Player
from level import Level
from settings import DEFAULT_KEYS, RESOLUTIONS, Settings
from sounds import SoundBank
from survival import (
    BOSS_EXTRA_TIME,
    CLEAR_INTERMISSION,
    EMERGE_TIME,
    SPAWN_MAX_DISTANCE,
    SurvivalGame,
    wave_floor,
    wave_timeout,
)
from upgrade_ui import choice_event, choice_rects
from upgrades import (
    BASE_GRENADES,
    CAPS,
    PERKS,
    UPGRADES,
    WEAPON_UPGRADES,
    SessionUpgrades,
)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))
import clean_sprites  # noqa: E402


class SpriteCleanupTests(unittest.TestCase):
    def test_enemy_sprites_have_no_edge_fragments_nor_offset(self):
        """Aucun débris de frame voisine ni silhouette décalée (sniper...)."""
        pygame.init()
        self.assertEqual(clean_sprites.clean(write=False), [])


class WaveTimingTests(unittest.TestCase):
    def test_timeout_decays_but_respects_floor_per_ten_waves(self):
        self.assertAlmostEqual(wave_timeout(1), 30.0)
        for wave in range(2, 31):
            self.assertLessEqual(wave_timeout(wave), wave_timeout(wave - 1) + 1e-9)
        for first, floor in ((1, 8.0), (11, 6.0), (21, 4.0)):
            for wave in range(first, first + 10):
                self.assertEqual(wave_floor(wave), floor)
                self.assertGreaterEqual(wave_timeout(wave), floor)
        # -3 % par vague : 30 × 0,97^(n-1), soit ~12,4 s à la 30e (planchers
        # non atteints).
        self.assertAlmostEqual(wave_timeout(2), 29.1)
        self.assertAlmostEqual(wave_timeout(30), 30.0 * 0.97 ** 29)
        self.assertGreater(wave_timeout(30), 12.0)


class SurvivalGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode(RESOLUTIONS[0])

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(settings_module, "SETTINGS_FILE",
                               os.path.join(tmp.name, "settings.json"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.settings = Settings()
        self.game = SurvivalGame(pygame.display.get_surface(), self.settings,
                                 SoundBank(self.settings))
        self.addCleanup(self.game.close)

    def test_cleared_wave_gives_fixed_seven_second_break(self):
        game = self.game
        for timer in (1.0, 20.0):
            game.intermission = 0.0
            game.wave = 3
            game.wave_timer = timer
            game.spawn_queue.clear()
            game._update_waves(0.0)
            self.assertEqual(game.intermission, CLEAR_INTERMISSION)
        self.assertEqual(CLEAR_INTERMISSION, 7.0)

    def test_unfinished_wave_is_overrun_by_the_next_one(self):
        game = self.game
        game.intermission = 0.0
        game.spawn_queue.clear()
        game._start_wave(2)
        queued = len(game.spawn_queue)
        game._update_waves(wave_timeout(2) + 0.01)
        self.assertEqual(game.wave, 3)
        self.assertEqual(game.intermission, 0.0)
        self.assertGreater(len(game.spawn_queue), queued)

    def test_colossus_wave_gets_ten_extra_seconds(self):
        game = self.game
        game.intermission = 0.0
        self.assertEqual(BOSS_EXTRA_TIME, 10.0)
        game._start_wave(10)
        self.assertIn("boss", [k for k, *_ in game.spawn_queue])
        game.spawn_queue.append(("grunt", 10, "", ""))  # vague non nettoyée
        game._update_waves(wave_timeout(10) + 0.01)
        self.assertEqual(game.wave, 10)
        game._update_waves(BOSS_EXTRA_TIME)
        self.assertEqual(game.wave, 11)
        self.assertAlmostEqual(game.wave_limit, wave_timeout(11))

    def test_enemies_spawn_at_the_portal_then_move_away(self):
        game = self.game
        cx, cy = game.level.config["portal"]
        for kind in ENEMY_TYPES:
            for _ in range(40):
                x, y, _angle = game._pick_spawn_point(ENEMY_TYPES[kind].RADIUS)
                self.assertLess(math.hypot(x - cx, y - cy), SPAWN_MAX_DISTANCE)
                self.assertTrue(game.level.can_stand(x, y, ENEMY_TYPES[kind].RADIUS))
        game.spawn_queue.extend([("grunt", 1, "", "")] * 3)
        game._process_spawn_queue(1.0)
        enemy = game.enemies[-1]
        start = math.hypot(enemy.x - cx, enemy.y - cy)
        self.assertLess(start, SPAWN_MAX_DISTANCE)
        game._update_emergence(EMERGE_TIME)
        self.assertGreater(math.hypot(enemy.x - cx, enemy.y - cy), start + 1.0)
        self.assertIsNone(enemy.emerge)

    def test_spawn_avoids_a_player_camping_at_the_portal(self):
        game = self.game
        cx, cy = game.level.config["portal"]
        game.player.x, game.player.y = cx + 0.9, cy
        for _ in range(60):
            x, y, _angle = game._pick_spawn_point(0.3)
            self.assertGreaterEqual(math.hypot(x - game.player.x, y - game.player.y), 1.2)
            self.assertLess(math.hypot(x - cx, y - cy), SPAWN_MAX_DISTANCE)

    def test_firing_is_allowed_while_sliding(self):
        game = self.game
        game.player.start_roll(defaultdict(bool), DEFAULT_KEYS)
        self.assertTrue(game.player.rolling)
        shots = game.stats["shots"]
        game._player_fire()
        self.assertEqual(game.stats["shots"], shots + 1)

    def test_grenade_card_raises_capacity_and_refills(self):
        game = self.game
        game.grenade_ammo = 0
        game.upgrades.levels["grenade"] = 1
        game._apply_upgrades()
        self.assertEqual(game.upgrades.grenade_capacity, BASE_GRENADES + 1)
        self.assertEqual(game.grenade_ammo, BASE_GRENADES + 1)
        game.grenade_ammo = 1
        game._apply_upgrades()          # idempotent : pas de nouveau plein
        self.assertEqual(game.grenade_ammo, 1)


class SlideTests(unittest.TestCase):
    @staticmethod
    def _open_level():
        level = Level(0)
        level.grid = [list("1" * 12)] + [list("1" + "." * 10 + "1")] + [list("1" * 12)]
        level.width, level.height = 12, 3
        level.prop_tiles = set()
        return level

    def _slide_distance(self, player):
        level = self._open_level()
        keys = defaultdict(bool)
        self.assertTrue(player.start_roll(keys, DEFAULT_KEYS))
        start = player.x
        while player.rolling:
            player.move(1 / 60, keys, DEFAULT_KEYS, level)
            player.update(1 / 60)
        return player.x - start

    def test_slide_goes_farther_than_the_old_roll(self):
        # Formule : 7,5 × 0,8 × (1 - 0,5 / 2) = 4,5 cases (ancienne roulade 2,5).
        distance = self._slide_distance(Player(1.5, 1.5))
        self.assertAlmostEqual(distance, 4.5, delta=0.1)

    def test_momentum_and_ghost_cards(self):
        build = SessionUpgrades()
        build.levels = {"momentum": 2, "ghost_slide": 1, "vitality": 2}
        player = Player(1.5, 1.5)
        player.health = 50
        self.assertEqual(build.apply_player(player), 0)
        self.assertEqual(player.max_health, 140)
        self.assertEqual(player.health, 90)
        build.apply_player(player)      # idempotent
        self.assertEqual(player.health, 90)
        self.assertAlmostEqual(self._slide_distance(player), 4.5 * 1.5, delta=0.15)
        player.start_roll(defaultdict(bool), DEFAULT_KEYS)
        player.update(0.01)             # avant l'ancienne fenêtre d'i-frames
        self.assertFalse(player.take_damage(10))
        player.update(Player.ROLL_DURATION - 0.05)
        self.assertFalse(player.take_damage(10))
        self.assertEqual(player.health, 90)


class CardTests(unittest.TestCase):
    def test_no_reward_limit_and_fourth_card_is_a_perk(self):
        build = SessionUpgrades(7)
        for token in range(30):
            self.assertTrue(build.award(token))
        self.assertEqual(build.credits, 29)
        for _ in range(30):
            offers = build.offers
            perks_left = any(build.levels.get(key, 0) < CAPS[key] for key in PERKS)
            weapons = offers[:-1] if perks_left else offers
            self.assertTrue(all(key in WEAPON_UPGRADES for key in weapons))
            if perks_left:          # une catégorie au plafond n'est plus proposée
                self.assertIn(offers[-1], PERKS)
            self.assertLessEqual(len(offers), 4)
            self.assertTrue(build.choose(build.offer_id, len(offers) - 1
                                         if build.offer_id % 2 else 0))
        self.assertEqual(sum(build.levels.values()), 30)

    def test_offers_stop_when_everything_is_maxed(self):
        build = SessionUpgrades()
        build.levels = dict(CAPS)
        self.assertTrue(build.award("late"))
        self.assertEqual(build.offers, [])
        self.assertEqual(build.credits, 0)
        build.levels = {key: cap for key, cap in CAPS.items() if key in WEAPON_UPGRADES}
        build.award("perks-only")
        self.assertEqual(len(build.offers), 1)
        self.assertIn(build.offers[0], PERKS)

    def test_snapshot_accepts_four_cards_and_rejects_misplaced_perk(self):
        source = SessionUpgrades()
        source.award("first")
        self.assertEqual(len(source.offers), 4)
        replica = SessionUpgrades()
        self.assertTrue(replica.apply_snapshot(source.snapshot()))
        self.assertEqual(replica.offers, source.offers)
        bad = source.snapshot()
        bad[2] = [bad[2][-1]] + bad[2][:-1]
        self.assertFalse(SessionUpgrades().apply_snapshot(bad))
        too_high = source.snapshot()
        too_high[1] = [["ghost_slide", 2]]
        self.assertFalse(SessionUpgrades().apply_snapshot(too_high))

    def test_fourth_card_reachable_by_f8_dpad_down_and_click(self):
        build = SessionUpgrades()
        build.award("first")
        size = (800, 600)
        events = [
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F8),
            pygame.event.Event(pygame.CONTROLLERBUTTONDOWN,
                               button=pygame.CONTROLLER_BUTTON_DPAD_DOWN),
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                               pos=choice_rects(size)[3].center),
        ]
        for event in events:
            self.assertEqual(choice_event(event, size, build), 3)
        self.assertEqual(len(choice_rects(size)), 4)
        self.assertTrue(set(UPGRADES) == set(WEAPON_UPGRADES) | set(PERKS))
        self.assertIn(pygame.K_F8, settings_module.RESERVED_KEYS)


class BossPlanTests(unittest.TestCase):
    def test_final_boss_is_documented_but_not_coded(self):
        self.assertFalse(hasattr(survival, "FinalBoss"))
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "docs", "boss-final-deferlement.md")
        self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
