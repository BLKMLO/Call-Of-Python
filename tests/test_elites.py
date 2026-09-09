import unittest
from types import SimpleNamespace

from elites import apply_elite, update_command


def enemy(kind="grunt", x=1):
    return SimpleNamespace(KIND=kind, IS_BOSS=kind == "boss", x=x, y=1,
                           alive=True, elite="", SPEED=2, _base_speed=2,
                           max_health=100, health=100, commanded=False)


class EliteTests(unittest.TestCase):
    def test_elite_is_applied_once_and_boss_is_unchanged(self):
        target = enemy()
        apply_elite(target, "bulwark")
        apply_elite(target, "hunter")
        self.assertEqual((target.max_health, target.SPEED), (135, 1.8))
        boss = enemy("boss")
        apply_elite(boss, "bulwark")
        self.assertEqual(boss.health, 100)

    def test_command_requires_live_source_range_and_visibility(self):
        commander, grunt, boss = enemy("commander"), enemy(), enemy("boss")
        enemies = [commander, grunt, boss]
        update_command(enemies, lambda *p: True)
        self.assertTrue(grunt.commanded)
        self.assertFalse(boss.commanded)
        commander.alive = False
        update_command(enemies, lambda *p: True)
        self.assertFalse(grunt.commanded)
        commander.alive = True
        update_command(enemies, lambda *p: False)
        self.assertFalse(grunt.commanded)
