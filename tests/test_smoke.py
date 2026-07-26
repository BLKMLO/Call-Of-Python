"""Tests de fumée généraux — remplacent les smoke_test2..11.py historiques,
utilisés en session mais jamais commités (dette documentée dans llm.md).

Chaque test instancie les vrais objets du jeu avec des pilotes SDL factices
et simule des frames complètes (update/draw) : le but est de détecter un
crash de boot, une régression de rendu ou une impasse de la boucle, pas de
rejouer les non-régressions ciblées des deux autres fichiers.
"""

import os
import tempfile
import unittest
from collections import deque
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import settings as settings_module
from coop import CoopClientGame, CoopHostGame
from game import DEATH_CAM_TIME, Game
from menu import (EndScreen, LevelCompleteScreen, MainMenu, MultiplayerMenu,
                  SealBrokenScreen, SettingsMenu)
from settings import RESOLUTIONS, Settings
from sounds import MUSIC_KEYS, SoundBank
from survival import FINAL_WAVE, SurvivalGame

COOP_TEST_PORT = 15577        # ≠ port par défaut : ne gêne pas une vraie partie


def _run_frames(game, screen, count, dt=1 / 60):
    for _ in range(count):
        game.update(dt)
        game.draw(screen)


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        try:
            pygame.mixer.init(22050, -16, 2, 256)
        except pygame.error:
            pass  # pas de matériel audio : SoundBank doit quand même tourner
        pygame.display.set_mode(RESOLUTIONS[0])

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.settings_path = os.path.join(self._tmp.name, "settings.json")
        patcher = patch.object(settings_module, "SETTINGS_FILE",
                               self.settings_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.settings = Settings()
        self.sounds = SoundBank(self.settings)
        self.screen = pygame.display.get_surface()

    # ------------------------------------------------------------------
    def test_boot_settings_and_soundbank(self):
        self.assertEqual(self.settings.resolution,
                         RESOLUTIONS[self.settings.resolution_index])
        if pygame.mixer.get_init() is not None:
            self.assertTrue(self.sounds.enabled)
            self.assertIn("player_shot", self.sounds.sounds)
        else:  # sans mixer, la banque reste utilisable (no-op)
            self.assertFalse(self.sounds.enabled)
            self.sounds.play("player_shot")
            self.sounds.play_music("menu")

    def test_campaign_runs_and_death_reaches_end_screen(self):
        game = Game(self.screen, self.settings, self.sounds, 0)
        _run_frames(game, self.screen, 120)
        self.assertIsNone(game.outcome)

        game.player.shield = 0.0     # bouclier de spawn : invariant connu
        game.player.take_damage(9999)
        _run_frames(game, self.screen, 5)
        self.assertEqual(game.outcome, "dead")
        self.assertFalse(game.finished)            # la caméra de mort joue
        _run_frames(game, self.screen,
                    int(DEATH_CAM_TIME * 60) + 10)
        self.assertTrue(game.finished)

    def test_campaign_victory_when_all_enemies_down(self):
        game = Game(self.screen, self.settings, self.sounds, 0)
        for enemy in game.enemies:
            enemy.health = 0
        _run_frames(game, self.screen, 10)
        self.assertEqual(game.outcome, "victory")
        _run_frames(game, self.screen, 60)         # end_delay > 0.8 s
        self.assertTrue(game.finished)

    def test_survival_waves_start_and_queue_is_deque(self):
        game = SurvivalGame(self.screen, self.settings, self.sounds)
        self.assertIsInstance(game.spawn_queue, deque)
        # Laisse passer le répit initial (INTERMISSION = 4 s) + marge.
        _run_frames(game, self.screen, 60 * 6)
        self.assertGreaterEqual(game.wave, 1)
        info = game.survival_info()
        self.assertEqual(info["final"], FINAL_WAVE)
        self.assertGreaterEqual(info["remaining"], 0)

    def test_menus_draw_and_click_at_extreme_resolutions(self):
        menus = [
            MainMenu(self.sounds, self.settings),
            SettingsMenu(self.sounds, self.settings),
            MultiplayerMenu(self.sounds, self.settings),
            EndScreen(self.sounds, victory=True, survival=True,
                      subtitle="fin", stats=None),
            EndScreen(self.sounds, victory=False),
            SealBrokenScreen(self.sounds),
            LevelCompleteScreen(self.sounds, 0, "Métropole"),
        ]
        for size in (RESOLUTIONS[0], RESOLUTIONS[-1]):
            screen = pygame.Surface(size)
            for menu in menus:
                menu.draw(screen)
                # Un clic au centre de chaque bouton ne doit rien casser.
                for _ident, _label, rect, _split in menu._layout(screen):
                    menu.handle_event(pygame.event.Event(
                        pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center),
                        screen)

    def test_coop_loopback_syncs_and_closes_cleanly(self):
        host = CoopHostGame(self.screen, self.settings, self.sounds,
                            port=COOP_TEST_PORT)
        client = CoopClientGame(self.screen, self.settings, self.sounds,
                                "127.0.0.1", port=COOP_TEST_PORT)
        try:
            for _ in range(600):
                host.update(1 / 60)
                client.update(1 / 60)
                if client.synced:
                    break
            self.assertTrue(client.synced,
                            "aucun instantané reçu en 10 s de loopback")
            host.draw(self.screen)
            client.draw(self.screen)
        finally:
            host.close()
            client.close()
        # Les sockets sont fermées : rebinder le port doit réussir.
        from network import UdpPeer
        probe = UdpPeer(port=COOP_TEST_PORT)
        probe.close()

    def test_settings_round_trip_and_truncated_json(self):
        self.settings.volume = 0.33
        self.settings.best_wave = 12
        self.settings.save()
        reloaded = Settings()
        self.assertAlmostEqual(reloaded.volume, 0.33)
        self.assertEqual(reloaded.best_wave, 12)
        # Fichier tronqué en plein milieu : retour aux défauts, pas de crash.
        with open(self.settings_path, "r+b") as stream:
            stream.truncate(5)
        self.assertEqual(Settings().volume, 0.7)

    def test_all_sounds_and_music_play_without_error(self):
        if not self.sounds.enabled:
            self.skipTest("pas de mixer audio sur cette machine")
        for name in self.sounds.sounds:
            self.sounds.play(name)
        for key in MUSIC_KEYS:
            self.sounds.play_music(key)


if __name__ == "__main__":
    unittest.main()
