"""Non-régressions des animations de recharge et musiques contextuelles."""

import hashlib
import os
import struct
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import assets
from entities import Player
from hud import HUD, RELOAD_KEYFRAMES, reload_frames, reload_pose
from sounds import MUSIC_PROFILES, _music_loop
from weapons import WEAPON_ORDER, WEAPON_SPECS, Weapon


class ReloadAndMusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((800, 600))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_reload_progress_is_normalized_and_resets_after_completion(self):
        weapon = Weapon(WEAPON_SPECS["rifle"])
        weapon.ammo -= 1
        weapon.start_reload()
        self.assertEqual(weapon.reload_progress, 0.0)

        weapon.update(weapon.spec.reload_time / 2)
        self.assertAlmostEqual(weapon.reload_progress, 0.5)

        weapon.update(weapon.spec.reload_time)
        self.assertEqual(weapon.reload_progress, 0.0)
        self.assertEqual(weapon.ammo, weapon.spec.magazine_size)

    def test_every_weapon_has_four_valid_transparent_reload_keyframes(self):
        asset_dir = Path(assets.ASSET_DIR)
        for weapon_id in WEAPON_ORDER:
            for suffix in ("_reload_1", "_reload_2",
                           "_reload", "_reload_3"):
                path = asset_dir / f"fp_{weapon_id}{suffix}.png"
                self.assertTrue(path.is_file(), path)
                surface = pygame.image.load(path)
                self.assertEqual(surface.get_size(), (192, 144))
                self.assertGreater(
                    surface.get_bounding_rect(min_alpha=12).width, 100,
                )
                for point in ((0, 0), (191, 0), (0, 143), (191, 143)):
                    self.assertEqual(surface.get_at(point).a, 0)

    def test_reload_sequence_uses_five_distinct_transitions(self):
        self.assertEqual(len(RELOAD_KEYFRAMES), 6)
        self.assertEqual(reload_frames(0.0), (None, None, 0.0))
        self.assertEqual(reload_frames(1.0), (None, None, 0.0))
        stages = [
            reload_frames(progress)[:2]
            for progress in (0.08, 0.25, 0.47, 0.68, 0.89)
        ]
        self.assertEqual(len(set(stages)), 5)

    def test_reload_motion_is_distinct_and_returns_to_idle_pose(self):
        poses = {weapon_id: reload_pose(weapon_id, 0.5)
                 for weapon_id in WEAPON_ORDER}
        self.assertEqual(len(set(poses.values())), len(WEAPON_ORDER))
        for weapon_id in WEAPON_ORDER:
            self.assertEqual(reload_pose(weapon_id, 0.0), (0.0, 0.0, 0.0))
            self.assertEqual(reload_pose(weapon_id, 1.0), (0.0, 0.0, 0.0))
            self.assertEqual(poses[weapon_id][0], 1.0)

    def test_hud_uses_a_visibly_different_frame_during_each_reload(self):
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        player = Player(2.0, 2.0)
        hud = HUD(screen.get_size())

        for weapon_id in WEAPON_ORDER:
            weapon = Weapon(WEAPON_SPECS[weapon_id])
            weapon.ammo -= 1
            player.weapons = [weapon]
            player.weapon_index = 0

            screen.fill((0, 0, 0, 0))
            hud.lower = 0.0
            hud._draw_weapon(screen, player)
            idle_hash = hashlib.sha256(
                pygame.image.tobytes(screen, "RGBA"),
            ).digest()

            weapon.start_reload()
            weapon.update(weapon.spec.reload_time / 2)
            screen.fill((0, 0, 0, 0))
            hud.lower = 0.0
            hud._draw_weapon(screen, player)
            reload_hash = hashlib.sha256(
                pygame.image.tobytes(screen, "RGBA"),
            ).digest()
            self.assertNotEqual(idle_hash, reload_hash, weapon_id)

    def test_hud_renders_multiple_distinct_mechanical_reload_stages(self):
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        player = Player(2.0, 2.0)
        hud = HUD(screen.get_size())

        for weapon_id in WEAPON_ORDER:
            weapon = Weapon(WEAPON_SPECS[weapon_id])
            weapon.ammo -= 1
            weapon.start_reload()
            player.weapons = [weapon]
            player.weapon_index = 0
            hashes = set()
            for progress in (0.16, 0.36, 0.58, 0.78):
                weapon.reloading = weapon.spec.reload_time * (1.0 - progress)
                screen.fill((0, 0, 0, 0))
                hud.lower = 0.0
                hud._draw_weapon(screen, player)
                hashes.add(hashlib.sha256(
                    pygame.image.tobytes(screen, "RGBA"),
                ).digest())
            self.assertEqual(len(hashes), 4, weapon_id)

    def test_music_profiles_cover_every_context_with_unique_identities(self):
        expected = {"menu", "level0", "level1", "level2", "level3",
                    "level4", "survival"}
        self.assertEqual(set(MUSIC_PROFILES), expected)
        self.assertEqual(
            len({profile.style for profile in MUSIC_PROFILES.values()}),
            len(MUSIC_PROFILES),
        )
        self.assertEqual(
            len({profile.title for profile in MUSIC_PROFILES.values()}),
            len(MUSIC_PROFILES),
        )

    def test_music_generation_is_deterministic_distinct_and_loopable(self):
        buffers = {
            key: _music_loop(key, duration=0.25)
            for key in MUSIC_PROFILES
        }
        self.assertEqual(buffers["level0"],
                         _music_loop("level0", duration=0.25))
        self.assertEqual(
            len({hashlib.sha256(data).digest() for data in buffers.values()}),
            len(MUSIC_PROFILES),
        )
        for key, data in buffers.items():
            first = struct.unpack_from("<h", data, 0)[0]
            last = struct.unpack_from("<h", data, len(data) - 4)[0]
            self.assertLess(abs(first - last), 700, key)


if __name__ == "__main__":
    unittest.main()
