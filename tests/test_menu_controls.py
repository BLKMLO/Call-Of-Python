"""Navigation réelle des menus et transitions d'entrée solo/coop, sans matériel."""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import main
import menu as menu_module
import settings as settings_module
from coop import CoopClientGame
from game import DEATH_SKIP_LOCK, Game
from gamepad import GamepadInput
from menu import EndScreen, MainMenu, MultiplayerMenu, SettingsMenu
from settings import Settings


def key(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code, unicode="", scancode=0)


def button(code):
    return pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, button=code)


class Controller:
    def __init__(self):
        self.buttons = set()
        self.axes = {}

    def attached(self):
        return True

    def get_button(self, value):
        return value in self.buttons

    def get_axis(self, value):
        return self.axes.get(value, 0)

    def quit(self):
        pass


class MenuControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        menu_module._FONT_CACHE.clear()
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        # SDL Font objects must not outlive the font subsystem across suites.
        menu_module._FONT_CACHE.clear()
        pygame.quit()

    def setUp(self):
        self.screen = pygame.display.set_mode((800, 600))
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        setting_patch = patch.object(settings_module, "SETTINGS_FILE",
                                     os.path.join(directory.name, "settings.json"))
        setting_patch.start()
        self.addCleanup(setting_patch.stop)
        self.settings = Settings()
        self.sounds = Mock()

    def pad(self):
        with patch.object(GamepadInput, "_open_first"):
            pad = GamepadInput()
        pad.controller = Controller()
        pad.update()  # A neutral tick arms inputs.
        return pad

    def game(self, cls=Game):
        if cls is Game:
            game = Game(self.screen, self.settings, self.sounds)
        else:
            game = CoopClientGame(self.screen, self.settings, self.sounds,
                                  "127.0.0.1", port=9)
        self.addCleanup(game.close)
        game.gamepad.close()
        game.gamepad = self.pad()
        return game

    def test_keyboard_select_activate_wrap_and_skip_separator(self):
        menu = SettingsMenu(self.sounds, self.settings)
        ids = [ident for ident, _ in menu.items() if ident is not None]
        menu.handle_event(key(pygame.K_UP), self.screen)
        self.assertEqual(menu.selected, "back")
        self.assertEqual(menu.handle_event(key(pygame.K_RETURN), self.screen), "back")
        for ident in ids:
            menu.handle_event(key(pygame.K_DOWN), self.screen)
            self.assertEqual(menu.selected, ident)

    def test_controller_can_start_campaign_and_return_from_end(self):
        menu = MainMenu(self.sounds, self.settings)
        self.assertEqual(menu.handle_event(button(pygame.CONTROLLER_BUTTON_A),
                                           self.screen), "play")
        end = EndScreen(self.sounds, victory=False)
        self.assertEqual(end.handle_event(button(pygame.CONTROLLER_BUTTON_B),
                                          self.screen), "menu")
        # B on the main menu must never quit the application.
        self.assertIsNone(menu.handle_event(button(pygame.CONTROLLER_BUTTON_B), self.screen))

    def test_controller_adjusts_settings_in_both_directions(self):
        menu = SettingsMenu(self.sounds, self.settings)
        menu.selected = "sound_volume"
        self.settings.sound_volume = 0.5
        menu.handle_event(button(pygame.CONTROLLER_BUTTON_DPAD_LEFT), self.screen)
        self.assertEqual(self.settings.sound_volume, 0.4)
        menu.handle_event(button(pygame.CONTROLLER_BUTTON_DPAD_RIGHT), self.screen)
        self.assertEqual(self.settings.sound_volume, 0.5)
        menu.selected = "back"
        self.assertIsNone(menu.handle_event(key(pygame.K_LEFT), self.screen))

    def test_controller_does_not_bind_keyboard_keys_during_capture(self):
        menu = SettingsMenu(self.sounds, self.settings)
        menu.waiting_action = "recharger"
        before = dict(self.settings.keys)
        menu.handle_event(button(pygame.CONTROLLER_BUTTON_A), self.screen)
        self.assertEqual(menu.waiting_action, "recharger")
        menu.handle_event(button(pygame.CONTROLLER_BUTTON_B), self.screen)
        self.assertIsNone(menu.waiting_action)
        self.assertEqual(self.settings.keys, before)

    def test_ip_edit_accept_cancel_and_validation_with_controller(self):
        menu = MultiplayerMenu(self.sounds, self.settings)
        menu.editing = True
        self.settings.last_ip = "999.0.0.1"
        menu.handle_event(button(pygame.CONTROLLER_BUTTON_A), self.screen)
        self.assertTrue(menu.editing)
        self.assertTrue(menu.error)
        menu.handle_event(button(pygame.CONTROLLER_BUTTON_B), self.screen)
        self.assertFalse(menu.editing)
        menu.editing = True
        self.settings.last_ip = "127.0.0.1"
        menu.handle_event(button(pygame.CONTROLLER_BUTTON_A), self.screen)
        self.assertFalse(menu.editing)

    def test_mouse_takes_focus_back_without_changing_polygon_collision(self):
        menu = MainMenu(self.sounds, self.settings)
        menu.handle_event(key(pygame.K_DOWN), self.screen)
        self.assertTrue(menu.keyboard_focus)
        menu.handle_event(pygame.event.Event(pygame.MOUSEMOTION, rel=(2, 0)), self.screen)
        self.assertFalse(menu.keyboard_focus)
        ident, _, rect, _ = menu._layout(self.screen)[0]
        self.assertIsNone(menu.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=rect.topleft), self.screen))
        self.assertEqual(menu.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center), self.screen), ident)

    def test_settings_rows_stay_above_footer_at_supported_small_sizes(self):
        menu = SettingsMenu(self.sounds, self.settings)
        for width, height in ((800, 600), (1280, 720)):
            screen = pygame.Surface((width, height))
            for _, label, rect, _ in menu._layout(screen):
                self.assertLess(rect.bottom, height - max(42, height // 11))
                font = menu._row_font(height, label, rect, True)
                self.assertLessEqual(menu._button_text_left(rect) + font.size(label)[0],
                                     rect.right)
            menu.draw(screen)

    def test_held_triggers_require_release_after_reset_and_remain_semi_auto(self):
        pad = self.pad()
        pad.controller.axes[pygame.CONTROLLER_AXIS_TRIGGERRIGHT] = 32767
        pad.controller.axes[pygame.CONTROLLER_AXIS_TRIGGERLEFT] = 32767
        pad.reset_controls()
        for _ in range(4):
            pad.update()
            self.assertFalse(pad.fire_held)
            self.assertFalse(pad.aim_held)
            self.assertNotIn("fire", pad.consume_actions())
        pad.controller.axes.clear()
        pad.update()
        pad.controller.axes[pygame.CONTROLLER_AXIS_TRIGGERRIGHT] = 32767
        pad.update()
        self.assertIn("fire", pad.consume_actions())
        pad.update()
        self.assertNotIn("fire", pad.consume_actions())
        self.assertTrue(pad.fire_held)

    def test_campaign_pause_purges_all_inputs_and_preserves_render_fps(self):
        game = self.game()
        game._mouse_fire_held = game._mouse_aim_held = True
        game.player.aiming = True
        game.gamepad.controller.buttons.add(pygame.CONTROLLER_BUTTON_START)
        game.fps = 117.0
        game.update(1 / 60)
        self.assertTrue(game.paused)
        self.assertFalse(game._mouse_fire_held or game._mouse_aim_held or game.player.aiming)
        self.assertEqual(game.fps, 117.0)
        self.assertEqual(game.handle_event(button(pygame.CONTROLLER_BUTTON_B)), "menu")

    def test_focus_loss_purges_inputs_and_pauses_solo_and_client(self):
        for cls in (Game, CoopClientGame):
            game = self.game(cls)
            game._mouse_fire_held = game._mouse_aim_held = True
            game.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
            self.assertTrue(game.paused)
            self.assertFalse(game._mouse_fire_held or game._mouse_aim_held)

    def test_host_resume_purges_actions_pressed_while_paused(self):
        game = self.game(CoopClientGame)
        game._set_host_paused(True)
        game.pending_fires.append(["pistol", [0]])
        game.gamepad.controller.axes[pygame.CONTROLLER_AXIS_TRIGGERRIGHT] = 32767
        game._set_host_paused(False)
        game.gamepad.update()
        self.assertFalse(game.pending_fires)
        self.assertFalse(game.gamepad.fire_held)
        game._set_host_paused(True)
        game._handle_touch_action("pause")
        game.handle_event(key(pygame.K_ESCAPE))
        self.assertTrue(game.controls_paused)
        game.draw(self.screen)

    def test_controller_respects_death_skip_lock(self):
        game = self.game()
        game.outcome = "dead"
        game.death_time = DEATH_SKIP_LOCK - 0.01
        game.handle_event(button(pygame.CONTROLLER_BUTTON_A))
        self.assertLess(game.death_time, DEATH_SKIP_LOCK)
        game.death_time = DEATH_SKIP_LOCK
        game.handle_event(button(pygame.CONTROLLER_BUTTON_A))
        self.assertGreater(game.death_time, DEATH_SKIP_LOCK)

    def test_main_uses_render_clock_fps_and_releases_controllers(self):
        pad = Mock(connected=True)
        game = SimpleNamespace(gamepad=Mock(), update=Mock(), draw=Mock(), close=Mock(),
                               finished=False, disconnected=False, fps=0.0)
        clock = Mock()
        clock.tick.return_value = 17
        clock.get_fps.return_value = 113.5
        with (patch.object(main, "Game", return_value=game),
              patch.object(main, "GamepadInput", return_value=pad),
              patch.object(main, "SoundBank", return_value=self.sounds),
              patch.object(main.pygame, "quit"),
              patch.object(main.pygame.time, "Clock", return_value=clock),
              patch.object(main.pygame.event, "get", side_effect=[
                  [button(pygame.CONTROLLER_BUTTON_A)],
                  [pygame.event.Event(pygame.QUIT)]])):
            with self.assertRaises(SystemExit) as exit_result:
                main.main()
        self.assertEqual(exit_result.exception.code, 0)
        self.assertEqual(game.fps, 113.5)
        game.close.assert_called_once()
        self.assertGreaterEqual(pad.close.call_count, 2)
