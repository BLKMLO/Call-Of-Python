import unittest
from types import SimpleNamespace

from boss_patterns import BossPattern


class BossPatternTests(unittest.TestCase):
    def test_warning_locks_target_and_has_exact_duration(self):
        boss = SimpleNamespace(x=1, y=1, alive=True, phase=2)
        target = SimpleNamespace(x=4, y=1, alive=True)
        pattern = BossPattern()
        pattern.timer, pattern.cycle = 0, 1
        self.assertEqual(pattern.step(0, boss, target, lambda *p: True), (True, ["warn"]))
        target.x = 9
        for _ in range(71):
            self.assertEqual(pattern.step(1 / 60, boss, target, lambda *p: True), (True, []))
        self.assertEqual(pattern.step(1 / 60, boss, target, lambda *p: True), (True, ["slam"]))
        self.assertEqual(pattern.x, 4)
        self.assertEqual(pattern.state, "recover")

    def test_visibility_and_death_cancel_patterns(self):
        boss = SimpleNamespace(x=1, y=1, alive=True, phase=1)
        target = SimpleNamespace(x=4, y=1, alive=True)
        pattern = BossPattern()
        pattern.timer = 0
        self.assertEqual(pattern.step(0, boss, target, lambda *p: False), (False, []))
        pattern.step(0, boss, target, lambda *p: True)
        boss.alive = False
        self.assertEqual(pattern.step(.25, boss, target, lambda *p: True), (False, []))

    def test_network_pattern_rejects_invalid_timers_and_types(self):
        pattern = BossPattern()
        for row in ([], ["warn", "slam", 1, 1, float("nan")], ["shell", "slam", 1, 1, 1]):
            self.assertFalse(pattern.apply_snapshot(row))
        self.assertTrue(pattern.apply_snapshot(["warn", "slam", 4, 5, 1.2]))
        self.assertEqual(pattern.snapshot(), ["warn", "slam", 4, 5, 1.2])
