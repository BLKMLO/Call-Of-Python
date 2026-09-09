import random
import unittest
from types import SimpleNamespace

from mutators import MUTATORS, apply_mutator, composition, mutator_for_wave


class MutatorTests(unittest.TestCase):
    def test_rotation_is_stable_and_boss_waves_are_neutral(self):
        first = [mutator_for_wave(wave) for wave in range(1, 31)]
        random.seed(8765)
        for _ in range(100):
            random.random()
        self.assertEqual(first, [mutator_for_wave(wave) for wave in range(1, 31)])
        self.assertEqual(first[:3], [""] * 3)
        self.assertTrue(all(first[w - 1] == "" for w in (10, 20, 30)))
        self.assertEqual(set(first) - {""}, set(MUTATORS))

    def test_effect_is_idempotent_and_preserves_damage_and_count(self):
        enemy = SimpleNamespace(KIND="grunt", max_health=100, health=100,
                                _base_speed=2.0, SPEED=2.0, DAMAGE=12)
        apply_mutator(enemy, "armored")
        apply_mutator(enemy, "armored")
        self.assertEqual(enemy.max_health, 120)
        self.assertEqual(enemy.SPEED, 1.8)
        self.assertEqual(enemy.DAMAGE, 12)
        source = ["grunt"] * 8 + ["boss"]
        result = composition(source, "crossfire")
        self.assertEqual(len(result), len(source))
        self.assertEqual(result.count("soldier"), 2)
        self.assertEqual(result[-1], "boss")
