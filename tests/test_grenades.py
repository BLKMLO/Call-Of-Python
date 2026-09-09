import unittest

from grenades import Grenade, read_grenades


class GrenadeTests(unittest.TestCase):
    def test_fuse_and_bounce_are_deterministic(self):
        grenade = Grenade(0, 0, 1, 1)
        for _ in range(119):
            self.assertFalse(grenade.step(1 / 60, lambda x, y: x >= 2 or x <= 0))
            self.assertLess(grenade.x, 2)
        self.assertTrue(grenade.step(1 / 60, lambda x, y: x >= 2 or x <= 0))
        self.assertLessEqual(grenade.timer, 1e-9)

    def test_snapshot_rejects_malformed_or_excess_projectiles(self):
        row = [1, 0, 2, 3, 1.0]
        self.assertEqual(read_grenades([row])[0].snapshot(), row)
        for rows in ([row] * 9, [row, row], [[True, 0, 1, 1, 1]],
                     [[1, 0, 1, float("nan"), 1]], [[1, 0, 1, 1, 3]]):
            self.assertIsNone(read_grenades(rows))
