import unittest
from types import SimpleNamespace

from coop_support import Pings, Rescue, validated_rows


class SupportTests(unittest.TestCase):
    def players(self):
        return {0: SimpleNamespace(x=1.5, y=1.5, health=100, alive=True, rolling=False),
                1: SimpleNamespace(x=2.0, y=1.5, health=0, alive=False, rolling=False)}

    def test_revive_duration_and_no_acceleration_by_helpers(self):
        players, rescue = self.players(), Rescue()
        rescue.update(0, players, lambda *p: True)
        rescue.request(0, players, lambda *p: True)
        for _ in range(179):
            self.assertFalse(rescue.update(1 / 60, players, lambda *p: True))
        self.assertEqual(rescue.update(1 / 60, players, lambda *p: True), [(1, True)])

    def test_damage_wall_roll_and_distance_interrupt(self):
        for change in ("damage", "wall", "roll", "distance"):
            players, rescue = self.players(), Rescue()
            rescue.update(0, players, lambda *p: True)
            rescue.request(0, players, lambda *p: True)
            rescue.update(.25, players, lambda *p: True)
            if change == "damage":
                players[0].health -= 1
            if change == "roll":
                players[0].rolling = True
            if change == "distance":
                players[0].x = 5
            rescue.update(.25, players, lambda *p, mode=change: mode != "wall")
            self.assertEqual(rescue.downed[1][1], 0)
            self.assertFalse(rescue.requests)

    def test_respawn_after_twenty_plus_six_seconds(self):
        players, rescue = self.players(), Rescue()
        for _ in range(1559):
            self.assertFalse(rescue.update(1 / 60, players, lambda *p: True))
        self.assertEqual(rescue.update(1 / 60, players, lambda *p: True), [(1, False)])

    def test_ping_rate_ttl_and_network_rows(self):
        pings = Pings()
        self.assertTrue(pings.add(0, 2, 3))
        self.assertFalse(pings.add(0, 4, 5))
        for _ in range(300):
            pings.update(1 / 60)
        self.assertFalse(pings.markers)
        for rows in ([[True, 1, 2, 3]], [[0, float("nan"), 1, 1]], [[0, 1, 2, 6]], [{}]):
            self.assertIsNone(validated_rows(rows))
