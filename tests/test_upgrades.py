import unittest

from upgrades import CHOICE_SECONDS, SessionUpgrades
from weapons import WEAPON_SPECS, Weapon


class UpgradeTests(unittest.TestCase):
    def test_choice_timer_seed_and_award_idempotence(self):
        left, right = SessionUpgrades(72), SessionUpgrades(72)
        for build in (left, right):
            self.assertTrue(build.award("manifest"))
            self.assertFalse(build.award("manifest"))
        self.assertEqual(left.offers, right.offers)
        for _ in range(int(CHOICE_SECONDS * 60) - 1):
            left.update(1 / 60)
        self.assertTrue(left.offers)
        left.update(1 / 60)
        right.choose(right.offer_id, 0)
        self.assertEqual(left.levels, right.levels)
        self.assertFalse(left.choose(1, 0))

    def test_caps_and_queued_rewards(self):
        build = SessionUpgrades()
        for token in range(10):
            build.award(token)
        for _ in range(6):
            self.assertTrue(build.choose(build.offer_id, 0))
        self.assertFalse(build.offers)
        self.assertEqual(sum(build.levels.values()), 6)
        self.assertLessEqual(max(build.levels.values()), 2)

    def test_apply_preserves_ammo_and_reload_progress(self):
        weapon = Weapon(WEAPON_SPECS["rifle"])
        weapon.ammo = 5
        weapon.start_reload()
        weapon.update(0.4)
        ratio = weapon.reload_progress
        build = SessionUpgrades()
        build.levels = {"reload": 2, "capacity": 1, "damage": 1}
        build.apply([weapon])
        self.assertAlmostEqual(weapon.reload_progress, ratio)
        self.assertEqual(weapon.ammo, 5)
        self.assertEqual(weapon.spec.magazine_size, 36)
        spec = weapon.spec
        build.apply([weapon])
        self.assertIs(weapon.spec, spec)

    def test_snapshot_is_atomic_and_rejects_malformed_choices(self):
        build = SessionUpgrades()
        for row in ([], [0, [], [], float("nan"), 0],
                    [1, [["damage", True]], [], 0, 0], [1, [], [{}] * 3, 0, 0]):
            self.assertFalse(build.apply_snapshot(row))
        original = SessionUpgrades()
        original.award("first")
        self.assertTrue(build.apply_snapshot(original.snapshot()))
        self.assertEqual(build.offers, original.offers)
