"""0.7.0 : difficulté adaptée, armes spécialisées, missions, contrats, thèmes."""

import math
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import menu as menu_module
import settings as settings_module
import ui_style
from ai import find_path
from difficulty import DIFFICULTIES, get_difficulty
from entities import ENEMY_TYPES
from game import Game
from level import LEVELS, Level
from menu import MainMenu
from settings import RESOLUTIONS, Settings
from sounds import SoundBank
from survival import (
    CONTRACTS,
    SurvivalGame,
    pick_contract,
    swarm_size,
    valid_contract,
    wave_composition,
    wave_traits,
)
from upgrades import CAPS, WEAPON_UPGRADES, SessionUpgrades
from weapons import (
    COOL_TIME_RATIO,
    HEAT_SHOTS_RATIO,
    SPIN_UP_TIME,
    WEAPON_SPECS,
    Weapon,
    shield_blocks,
    shot_damage,
)


class WeaponRulesTests(unittest.TestCase):
    def test_minigun_never_reloads_and_overheats(self):
        gun = Weapon(WEAPON_SPECS["minigun"])
        shots = 0
        while gun.fire():
            shots += 1
            gun.cooldown = 0.0
        # 0,7 × 100 = 70 tirs avant surchauffe, munitions intactes.
        self.assertEqual(shots, round(HEAT_SHOTS_RATIO * 100))
        self.assertTrue(gun.overheated)
        self.assertEqual(gun.ammo, gun.spec.magazine_size)
        gun.start_reload()
        self.assertEqual(gun.reloading, 0.0)
        # Refroidissement complet : 0,85 × 2,6 s = 2,21 s.
        cool = COOL_TIME_RATIO * gun.spec.reload_time
        gun.update(cool - 0.05)
        self.assertTrue(gun.overheated)
        gun.update(0.1)
        self.assertFalse(gun.overheated)
        self.assertTrue(gun.can_fire())

    def test_minigun_needs_spin_up_before_local_fire(self):
        gun = Weapon(WEAPON_SPECS["minigun"])
        self.assertFalse(gun.pull_trigger())
        for _ in range(int(SPIN_UP_TIME / 0.05) + 1):
            gun.pull_trigger()
            gun.update(0.05)
        self.assertTrue(gun.pull_trigger())
        self.assertTrue(Weapon(WEAPON_SPECS["pistol"]).pull_trigger())

    def test_damage_depends_on_weapon_and_target(self):
        heavy = ENEMY_TYPES["heavy"](0, 0)
        grunt = ENEMY_TYPES["grunt"](0, 0)
        minigun = Weapon(WEAPON_SPECS["minigun"])
        pistol = Weapon(WEAPON_SPECS["pistol"])
        shotgun = Weapon(WEAPON_SPECS["shotgun"])
        self.assertEqual(shot_damage(minigun, grunt, 3), 14)
        self.assertEqual(shot_damage(minigun, heavy, 3), round(14 * 0.6))
        self.assertEqual(shot_damage(pistol, heavy, 3), round(20 * 1.4))
        self.assertEqual(shot_damage(pistol, heavy, 3, ads=1.0), round(20 * 1.4 * 1.75))
        self.assertEqual(shot_damage(shotgun, grunt, 1.5), round(9 * 1.5))
        self.assertEqual(shot_damage(shotgun, grunt, 2.5), 9)
        # Possédé : le blindage d'origine compte toujours.
        heavy.set_possessed(True)
        self.assertEqual(shot_damage(minigun, heavy, 3), round(14 * 0.6))

    def test_front_shield_blocks_until_stunned(self):
        soldier = ENEMY_TYPES["soldier"](5, 5)
        soldier.shielded = True
        soldier.angle = 0.0                        # regarde vers +x
        self.assertTrue(shield_blocks(soldier, 0.0))      # tireur devant
        self.assertFalse(shield_blocks(soldier, math.pi))  # tireur derrière
        rifle = Weapon(WEAPON_SPECS["rifle"])
        self.assertEqual(shot_damage(rifle, soldier, 4, shooter_angle=0.0),
                         round(24 * 0.15))
        soldier.stun_timer = 0.5
        self.assertFalse(shield_blocks(soldier, 0.0))

    def test_weapon_cards_exist_and_cooling_reduces_heat(self):
        for key in ("pistol_explosive", "shotgun_heavy", "rifle_pierce", "minigun_cooling"):
            self.assertIn(key, WEAPON_UPGRADES)
            self.assertEqual(CAPS[key], 1)
        build = SessionUpgrades()
        build.levels["minigun_cooling"] = 1
        gun = Weapon(WEAPON_SPECS["minigun"])
        build.apply([gun])
        self.assertAlmostEqual(gun.heat_per_shot, 0.7 / 70)


class DifficultyTests(unittest.TestCase):
    def test_soldier_keeps_historic_values(self):
        soldier = get_difficulty("soldier")
        self.assertEqual((soldier.clear_heal, soldier.level_heal, soldier.spawn_shield,
                          soldier.lifepack_every, soldier.enemy_count, soldier.boss_tempo),
                         (12, 40, 3.0, 2, 1.0, 1.0))

    def test_profiles_are_ordered_from_easy_to_hard(self):
        recruit, soldier, veteran = (DIFFICULTIES[k] for k in ("recruit", "soldier", "veteran"))
        self.assertGreater(recruit.clear_heal, soldier.clear_heal)
        self.assertGreater(soldier.clear_heal, veteran.clear_heal)
        self.assertLess(recruit.enemy_count, veteran.enemy_count)
        self.assertGreater(recruit.boss_tempo, veteran.boss_tempo)
        self.assertGreater(recruit.countdown_mult, veteran.countdown_mult)

    def test_wave_size_follows_difficulty(self):
        # Soldat : 4 + ceil(0,6 × 5) = 7 ennemis à la vague 5.
        self.assertEqual(len(wave_composition(5)), 7)
        self.assertEqual(len(wave_composition(5, 0.8)), round(7 * 0.8))
        self.assertEqual(len(wave_composition(5, 1.25)), round(7 * 1.25))

    def test_swarms_and_shields(self):
        self.assertEqual(swarm_size(7), 0)
        self.assertEqual(swarm_size(8), 4)
        self.assertEqual(swarm_size(20), 0)      # vague du Colosse
        self.assertEqual(swarm_size(28), 7)
        kinds = ["soldier"] * 6
        self.assertEqual(wave_traits(kinds, 6), [""] * 6)
        self.assertEqual(wave_traits(kinds, 7).count("shield"), 2)

    def test_contracts_are_deterministic_and_valid(self):
        self.assertIsNone(pick_contract(1, ["grunt"], [""]))
        self.assertIsNone(pick_contract(3, ["grunt"], [""]))
        first = pick_contract(5, ["grunt", "heavy"], ["", ""])
        self.assertEqual(first, pick_contract(5, ["grunt", "heavy"], ["", ""]))
        self.assertIn(first["key"], CONTRACTS)
        row = [first["key"], 0, first["goal"], 0]
        self.assertTrue(valid_contract(row))
        self.assertFalse(valid_contract([first["key"], 9, 1, 0]))
        self.assertFalse(valid_contract(["inconnu", 0, 1, 0]))


class GameplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode(RESOLUTIONS[0])

    @classmethod
    def tearDownClass(cls):
        menu_module._FONT_CACHE.clear()
        ui_style.STYLE_CACHE.clear()
        pygame.quit()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = patch.object(settings_module, "SETTINGS_FILE",
                               os.path.join(tmp.name, "settings.json"))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.settings = Settings()
        self.screen = pygame.display.get_surface()
        self.sounds = SoundBank(self.settings)

    def game(self, level):
        game = Game(self.screen, self.settings, self.sounds, level)
        self.addCleanup(game.close)
        game.player.shield = 0.0
        return game

    def test_spawn_shield_follows_difficulty(self):
        for key in ("recruit", "veteran"):
            self.settings.difficulty = key
            game = Game(self.screen, self.settings, self.sounds, 0)
            self.addCleanup(game.close)
            self.assertEqual(game.player.shield, DIFFICULTIES[key].spawn_shield)

    def test_every_objective_is_reachable_from_spawn(self):
        for index, config in enumerate(LEVELS):
            level = Level(index)
            sx, sy = level.player_spawn
            for step in config.get("objectives", ()):
                path = find_path(level, sx, sy, step["x"], step["y"])
                self.assertTrue(path or math.hypot(step["x"] - sx, step["y"] - sy) < 1,
                                f"{config['name']} : {step['id']} injoignable")

    def test_colossus_is_sealed_until_generators_are_cut(self):
        game = self.game(4)
        game.update(1 / 60)
        boss = next(e for e in game.enemies if e.IS_BOSS)
        self.assertTrue(boss.invulnerable)
        self.assertFalse(boss.take_damage(500))
        game.mission.index = 3       # trois générateurs coupés
        game.update(1 / 60)
        self.assertFalse(boss.invulnerable)
        before = boss.health
        boss.take_damage(50)
        self.assertLess(boss.health, before)

    def test_military_base_countdown_fails_mission(self):
        game = self.game(3)
        game.mission_director.countdown = 0.01
        game.update(1 / 60)
        game.update(1 / 60)
        self.assertEqual(game.outcome, "failed")
        self.assertTrue(game.failure_reason)
        for _ in range(60):
            game.update(1 / 60)
        self.assertTrue(game.finished)

    def test_sabotage_triggers_reinforcements_within_budget(self):
        game = self.game(3)
        alive = len(game.enemies)
        game.player.x, game.player.y = 10.5, 6.5
        self.assertTrue(game._interact())
        game.update(1 / 60)
        self.assertEqual(len(game.enemies), alive + 3)
        self.assertLessEqual(game.mission_director.reinforcements_sent,
                             game.mission_director.reinforcement_budget)

    def test_city_hold_spawns_reinforcements(self):
        game = self.game(1)
        game.mission.index = 1                       # étape « tenir »
        game.mission_director._last_index = 1
        before = len(game.enemies)
        for _ in range(int(6.2 * 60)):
            game.mission_director.update(1 / 60)
        self.assertEqual(len(game.enemies), before + 2)

    def test_hostage_follows_is_targeted_and_escort_completes(self):
        game = self.game(2)
        game.mission.index = 4                       # otage libéré
        game.mission_director.update(1 / 60)
        hostage = game.mission_director.hostage
        self.assertIsNotNone(hostage)
        game.player.x, game.player.y = 15.5, 15.5
        for _ in range(120):
            game.mission_director.update(1 / 60)
        self.assertLess(math.hypot(hostage.x - game.player.x, hostage.y - game.player.y), 2.0)
        enemy = game.enemies[0]
        enemy.x, enemy.y = hostage.x + 0.6, hostage.y
        self.assertIs(game._ai_target(enemy), hostage)
        hostage.x, hostage.y = 13.5, 24.5            # zone d'extraction
        hostage.following = False
        game.mission_director.update(1 / 60)
        self.assertTrue(game.mission.complete)

    def test_hostage_death_fails_mission(self):
        game = self.game(2)
        game.mission.index = 4
        game.mission_director.update(1 / 60)
        game.mission_director.hostage.take_damage(10 ** 6)
        game.update(1 / 60)
        self.assertEqual(game.outcome, "failed")

    def test_shotgun_stuns_and_pushes_back(self):
        game = self.game(1)
        enemy = game.enemies[0]
        x0 = enemy.x
        game._shotgun_impact(enemy.x - 1.0, enemy.y, [(enemy, False)])
        self.assertGreater(enemy.stun_timer, 0.0)
        self.assertGreaterEqual(enemy.x, x0)

    def test_overheated_minigun_shows_message_in_game(self):
        game = self.game(0)
        gun = Weapon(WEAPON_SPECS["minigun"])
        gun.spin = 1.0
        gun.heat = 0.999
        game.player.weapons = [gun]
        game.player.weapon_index = 0
        game._player_fire()
        self.assertTrue(gun.overheated)
        self.assertIn("SURCHAUFFE", game.hud.message)


class SurvivalContractTests(unittest.TestCase):
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

    def test_contract_completion_awards_a_card(self):
        game = self.game
        game.wave = 5
        game.contract = {"key": "pistol_any", "goal": 2, "progress": 0, "done": False}
        grunt = ENEMY_TYPES["grunt"](3, 3)
        credits = game.upgrades.credits + len(game.upgrades.offers)
        game._credit_kill(grunt, "rifle")            # mauvaise arme
        self.assertEqual(game.contract["progress"], 0)
        game._credit_kill(grunt, "pistol")
        game._credit_kill(grunt, "pistol")
        self.assertTrue(game.contract["done"])
        self.assertGreater(game.upgrades.credits + len(game.upgrades.offers), credits)
        self.assertTrue(valid_contract(game.survival_info()["contract"]))

    def test_lifepack_and_clear_heal_follow_difficulty(self):
        game = self.game
        game.difficulty = get_difficulty("veteran")
        lifepack = next(p for p in game.pickups if p.kind == "lifepack")
        lifepack.taken = True
        game._refresh_pickups(2)
        self.assertTrue(lifepack.taken)             # Vétéran : toutes les 3 vagues
        game._refresh_pickups(3)
        self.assertFalse(lifepack.taken)


class MenuThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode(RESOLUTIONS[0])

    @classmethod
    def tearDownClass(cls):
        menu_module._FONT_CACHE.clear()
        ui_style.STYLE_CACHE.clear()
        pygame.quit()

    def test_difficulty_row_cycles_and_changes_theme(self):
        settings = Mock()
        settings.difficulty = "soldier"
        settings.survival_unlocked = False
        settings.best_level = settings.best_wave = 0

        def cycle(direction):
            order = ("recruit", "soldier", "veteran")
            settings.difficulty = order[(order.index(settings.difficulty) + direction) % 3]

        settings.cycle_difficulty.side_effect = cycle
        menu = MainMenu(Mock(), settings)
        screen = pygame.Surface((1280, 720))
        row = next(r for r in menu._layout(screen) if r[0] == "difficulty")
        right = (row[2].right - 30, row[2].centery)
        self.assertIsNone(menu.on_click("difficulty", right, row[2], row[3]))
        self.assertEqual(settings.difficulty, "veteran")
        menu.draw(screen)
        self.assertEqual(menu_module.theme("chevrons"), 3)
        red = menu_module.theme("accent")
        menu_module.set_theme("recruit")
        self.assertNotEqual(red, menu_module.theme("accent"))


if __name__ == "__main__":
    unittest.main()
