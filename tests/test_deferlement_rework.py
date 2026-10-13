"""Non-régressions de la refonte du Déferlement (octobre 2026)."""

import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools"))
import clean_sprites  # noqa: E402


class SpriteCleanupTests(unittest.TestCase):
    def test_enemy_sprites_have_no_edge_fragments_nor_offset(self):
        """Aucun débris de frame voisine ni silhouette décalée (sniper...)."""
        pygame.init()
        self.assertEqual(clean_sprites.clean(write=False), [])


if __name__ == "__main__":
    unittest.main()
