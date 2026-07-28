"""Non-régressions des impacts typés et des volumes audio séparés."""

import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import settings as settings_module
from coop import CoopClientGame, CoopHostGame
from entities import Boss, Grunt, Heavy, Kamikaze, Player, Sniper, Soldier
from menu import SettingsMenu
from particles import IMPACT_PALETTES, ParticleSystem
from settings import Settings
from sounds import MUSIC_VOLUME, SoundBank


class ImpactAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_enemy_material_and_possessed_priority(self):
        for enemy_type in (Grunt, Soldier, Sniper, Kamikaze):
            self.assertEqual(enemy_type(2.0, 2.0).impact_type, "flesh")
        for enemy_type in (Heavy, Boss):
            enemy = enemy_type(2.0, 2.0)
            self.assertEqual(enemy.impact_type, "armor")
            enemy.set_possessed()
            self.assertEqual(enemy.impact_type, "possessed")

    def test_particle_bursts_never_mix_material_palettes(self):
        for impact_type in ("flesh", "armor", "possessed"):
            particles = ParticleSystem()
            particles.spawn_impact(3.0, 4.0, impact_type)
            self.assertEqual(len(particles.items), 12)
            self.assertTrue(all(
                particle.color in IMPACT_PALETTES[impact_type]
                for particle in particles.items
            ))
            particles.spawn_impact(3.0, 4.0, impact_type, fatal=True)
            self.assertEqual(len(particles.items), 40)

    def test_legacy_volume_migrates_then_independent_volumes_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({"volume": 0.4}, stream)
            with patch.object(settings_module, "SETTINGS_FILE", path):
                migrated = Settings()
                self.assertEqual(migrated.sound_volume, 0.4)
                self.assertEqual(migrated.music_volume, 0.4)
                migrated.sound_volume = 0.2
                migrated.music_volume = 0.8
                migrated.save()
                reloaded = Settings()
            self.assertEqual(reloaded.sound_volume, 0.2)
            self.assertEqual(reloaded.music_volume, 0.8)
            self.assertEqual(reloaded.volume, 0.2)

    def test_soundbank_applies_effect_and_music_volumes_independently(self):
        effect_channel = Mock()
        effect = Mock()
        effect.play.return_value = effect_channel
        music_channel = Mock()
        bank = SoundBank.__new__(SoundBank)
        bank.settings = SimpleNamespace(sound_volume=0.25, music_volume=0.8)
        bank.enabled = True
        bank.sounds = {"flesh_hit": effect}
        bank.music_channel = music_channel
        bank._last_music_volume = None

        bank.play("flesh_hit", volume_scale=0.5)
        effect_channel.set_volume.assert_called_once_with(0.125, 0.125)
        bank.refresh_music_volume()
        music_channel.set_volume.assert_called_once_with(
            0.8 * MUSIC_VOLUME, 0.8 * MUSIC_VOLUME,
        )

    def test_settings_menu_exposes_two_independent_audio_rows(self):
        settings = SimpleNamespace(
            resolution=(1280, 720),
            sound_volume=0.5,
            music_volume=0.7,
            sensitivity=0.5,
            invert_mouse=False,
            key_name=lambda _action: "A",
            save=Mock(),
            reset_keys=Mock(),
        )
        menu = SettingsMenu(Mock(), settings)
        identifiers = [identifier for identifier, _label in menu.items()]
        self.assertIn("sound_volume", identifiers)
        self.assertIn("music_volume", identifiers)

        rect = pygame.Rect(0, 0, 100, 30)
        menu.on_click("sound_volume", (75, 15), rect, split_x=50)
        self.assertEqual(settings.sound_volume, 0.6)
        self.assertEqual(settings.music_volume, 0.7)
        menu.on_click("music_volume", (25, 15), rect, split_x=50)
        self.assertEqual(settings.sound_volume, 0.6)
        self.assertEqual(settings.music_volume, 0.6)

    def test_host_replicates_every_impact_and_client_uses_enemy_material(self):
        host = CoopHostGame.__new__(CoopHostGame)
        host.particles = Mock()
        host.sounds = Mock()
        host.player = Player(1.0, 1.0)
        host.net_events = []
        enemy = Heavy(3.0, 3.0)
        enemy.net_id = 17

        host._on_enemy_impact(enemy)
        host._on_enemy_impact(enemy, fatal=True)
        self.assertEqual(host.net_events, [["ei", 17, 0], ["ei", 17, 1]])
        host.particles.spawn_impact.assert_any_call(
            3.0, 3.0, "armor", fatal=False,
        )
        host.particles.spawn_impact.assert_any_call(
            3.0, 3.0, "armor", fatal=True,
        )
        self.assertEqual(
            [call.args[0] for call in host.sounds.play.call_args_list],
            ["armor_hit", "armor_hit"],
        )

        client = CoopClientGame.__new__(CoopClientGame)
        client.particles = Mock()
        client.sounds = Mock()
        client.player = Player(1.0, 1.0)
        enemy.set_possessed()
        client.ghosts = {17: enemy}
        client._apply_event(["ei", 17, 0])
        client._apply_event(["ei", 17, 1])
        self.assertEqual(client.particles.spawn_impact.call_count, 2)
        client.particles.spawn_impact.assert_any_call(
            3.0, 3.0, "possessed", fatal=False,
        )
        client.particles.spawn_impact.assert_any_call(
            3.0, 3.0, "possessed", fatal=True,
        )
        self.assertEqual(client.sounds.play.call_count, 2)

    def test_client_rejects_malformed_impact_events(self):
        client = CoopClientGame.__new__(CoopClientGame)
        client.particles = Mock()
        client.sounds = Mock()
        client.player = Player(1.0, 1.0)
        client.ghosts = {1: Soldier(2.0, 2.0)}
        for event in (
            ["ei", True, 0],
            ["ei", 1, 2],
            ["ei", "1", 0],
            ["ei", 1],
        ):
            client._apply_event(event)
        client.particles.spawn_impact.assert_not_called()


if __name__ == "__main__":
    unittest.main()
