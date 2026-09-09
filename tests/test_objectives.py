"""Contrats déterministes du moteur d'objectifs."""

import unittest
from types import SimpleNamespace

from objectives import Mission


class ObjectiveTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(x=1.5, y=1.5, alive=True, rolling=False)
        self.rows = [dict(id="terminal", label="Terminal", kind="interact", x=1.5, y=1.5),
                     dict(id="hold", label="Tenir", kind="defend", x=4.5, y=1.5,
                          duration=1.0)]

    def test_interaction_requires_range_life_and_visibility(self):
        mission = Mission(self.rows)
        self.assertFalse(mission.interact(self.actor, lambda *args: False))
        self.actor.alive = False
        self.assertFalse(mission.interact(self.actor, lambda *args: True))
        self.actor.alive = True
        self.actor.x = 9
        self.assertFalse(mission.interact(self.actor, lambda *args: True))
        self.actor.x = 1.5
        self.assertTrue(mission.interact(self.actor, lambda *args: True))
        self.assertFalse(mission.interact(self.actor, lambda *args: True))

    def test_timer_uses_simulation_time_not_number_of_players(self):
        mission = Mission(self.rows)
        mission.advance()
        self.actor.x = 4.5
        for _ in range(59):
            mission.update(1 / 60, [self.actor] * 4, lambda *args: True, True)
        self.assertFalse(mission.complete)
        mission.update(1 / 60, [self.actor], lambda *args: True, True)
        self.assertTrue(mission.complete)

    def test_leaving_defense_resets_progress(self):
        mission = Mission(self.rows)
        mission.advance()
        self.actor.x = 4.5
        mission.update(0.25, [self.actor], lambda *args: True, True)
        self.assertEqual(mission.elapsed, 0.25)
        mission.update(0.25, [], lambda *args: True, True)
        self.assertEqual(mission.elapsed, 0)

    def test_snapshot_rejects_invalid_or_regressing_state(self):
        mission = Mission(self.rows)
        for row in (None, {}, [True, 0], [-1, 0], [3, 0], [1, float("nan")], [0, 1]):
            self.assertFalse(mission.apply_snapshot(row))
        self.assertTrue(mission.apply_snapshot([1, 0.5]))
        self.assertFalse(mission.apply_snapshot([0, 0]))
        self.assertEqual(mission.snapshot(), [1, 0.5])

    def test_definition_validation_and_legacy_empty_mission(self):
        self.assertFalse(Mission().complete)
        for rows in (self.rows * 10, [self.rows[0]] * 2,
                     [dict(self.rows[0], x=float("inf"))],
                     [dict(self.rows[0], kind="shell")]):
            with self.assertRaises(ValueError):
                Mission(rows)
