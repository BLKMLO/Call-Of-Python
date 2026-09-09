import unittest
from types import SimpleNamespace

from scoring import ScoreBook, valid_score


class ScoringTests(unittest.TestCase):
    def test_kills_objectives_and_victory_are_credited_once(self):
        book = ScoreBook(target=1100)
        enemy = SimpleNamespace(KIND="grunt", elite="", alive=False)
        for _ in range(100):
            book.observe([enemy], 1, {0: True}, "victory")
        self.assertEqual(book.total, 1100)
        self.assertEqual(book.grade, "S")

    def test_downed_penalty_and_revive_reward_are_bounded(self):
        book = ScoreBook()
        book.add(500)
        book.observe([], 0, {0: False}, None)
        book.observe([], 0, {0: False}, None)
        self.assertEqual(book.total, 350)
        for _ in range(20):
            book.rescue()
        self.assertEqual(book.total, 1350)
        self.assertEqual(book.revives, 4)
        self.assertTrue(valid_score(book.snapshot()))
        self.assertFalse(valid_score([True, 1, 1, 0, "S"]))

    def test_new_level_carries_total_but_grades_its_own_segment(self):
        book = ScoreBook(total=9000, target=1000)
        self.assertEqual(book.grade, "D")
        book.add(400)
        book.observe([], 0, {0: True}, "victory")
        self.assertEqual((book.total, book.grade), (9900, "S"))
