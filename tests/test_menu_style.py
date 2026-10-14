"""Habillage « jeu vidéo » des menus et du HUD (cartes, polices, bandeaux)."""

import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import menu as menu_module
import ui_style
from hud import ANNOUNCE_SLAM, HUD
from menu import EndScreen, MultiplayerMenu, SettingsMenu, stat_cards
from settings import Settings


class MenuStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        menu_module._FONT_CACHE.clear()
        ui_style.STYLE_CACHE.clear()
        pygame.quit()

    def test_stat_cards_split_the_summary(self):
        stats = {"kills": 87, "hits": 400, "shots": 900, "time": 754,
                 "score": 12000, "grade": "B"}
        cards = stat_cards(stats)
        self.assertEqual([label for label, _value, _color in cards],
                         ["SCORE", "GRADE", "ÉLIM.", "PRÉCISION", "TEMPS"])
        self.assertEqual(cards[4][1], "12:34")
        self.assertEqual(cards[3][1], "44 %")
        self.assertIsNone(stat_cards(None))
        stats.pop("score")
        self.assertEqual(len(stat_cards(stats)), 3)

    def test_every_row_of_a_menu_uses_one_font_size(self):
        menus = (SettingsMenu(Mock(), Settings()), MultiplayerMenu(Mock(), Settings()))
        for size in ((800, 600), (1280, 720)):
            screen = pygame.Surface(size)
            for menu in menus:
                rows = menu._layout(screen)
                font = menu._shared_font(size[1], rows, len(rows) > 8)
                for _ident, label, rect, _split in rows:
                    self.assertLessEqual(
                        menu._button_text_left(rect) + font.size(label.upper())[0],
                        rect.right)

    def test_end_screen_colors_follow_outcome(self):
        defeat = EndScreen(Mock(), victory=False)
        victory = EndScreen(Mock(), victory=True)
        self.assertEqual(defeat.glow_color, menu_module.DANGER_COLOR)
        self.assertEqual(victory.glow_color, menu_module.GOLD_COLOR)

    def test_styled_text_is_cached_by_font_object(self):
        font = pygame.font.SysFont("dejavusans", 20)
        first = ui_style.styled_text(font, "VAGUE", (255, 255, 255), 2)
        self.assertIs(first, ui_style.styled_text(font, "VAGUE", (255, 255, 255), 2))
        glowing = ui_style.styled_text(font, "VAGUE", (255, 255, 255), 2,
                                       glow=(200, 100, 50))
        self.assertGreater(glowing.get_width(), first.get_width())

    def test_announce_banner_never_mutates_the_cached_surface(self):
        screen = pygame.Surface((800, 600))
        hud = HUD((800, 600))
        hud.announce("VAGUE 3")
        hud.update(ANNOUNCE_SLAM / 2, False)
        hud._draw_announce(screen)
        hud.update(1.8, False)          # phase d'effacement
        hud._draw_announce(screen)
        cached = next(iter(hud._banner_cache.values()))
        self.assertIn(cached.get_alpha(), (None, 255))
        hud.draw_pause(screen, host_paused=True)


if __name__ == "__main__":
    unittest.main()
