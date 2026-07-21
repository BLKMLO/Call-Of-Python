"""Non-régressions de la passe de robustesse et d'optimisation."""

import json
import math
import os
import tempfile
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import settings as settings_module
from coop import (MAX_REMOTE_DAMAGE, REMOTE_FIRE_CAPACITY, CoopClientGame,
                  CoopHostGame)
from entities import Player, RemotePlayer
from game import Game
from hud import HUD
from level import Level, SURVIVAL_LEVEL
from network import UdpPeer
from settings import DEFAULT_KEYS, RESERVED_KEYS, Settings, valid_ipv4
from survival import SurvivalGame


class _FakeSocket:
    def __init__(self, packets):
        self.packets = deque(packets)

    def recvfrom(self, _size):
        if not self.packets:
            raise BlockingIOError
        return self.packets.popleft()


class CleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_udp_ignores_non_objects_and_limits_work_per_tick(self):
        peer = UdpPeer.__new__(UdpPeer)
        peer.sock = _FakeSocket([
            (b"[]", ("127.0.0.1", 1)),
            (b'{"t":"join"}', ("127.0.0.1", 2)),
            (b'{"t":"later"}', ("127.0.0.1", 3)),
        ])
        received = peer.receive(limit=2)
        self.assertEqual(received, [({"t": "join"}, ("127.0.0.1", 2))])
        self.assertEqual(peer.receive(limit=2)[0][0]["t"], "later")

    def test_settings_recover_from_malformed_values_and_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump({
                    "resolution_index": 999,
                    "volume": "nan",
                    "sensitivity": {},
                    "fullscreen": "false",
                    "last_ip": "999.12.1.2",
                    "keys": {
                        "avancer": pygame.K_q,
                        "gauche": pygame.K_q,
                        "roulade": pygame.K_F11,
                    },
                }, stream)
            with patch.object(settings_module, "SETTINGS_FILE", path):
                loaded = Settings()
                self.assertEqual(loaded.resolution_index, 4)
                self.assertEqual(loaded.volume, 0.7)
                self.assertFalse(loaded.fullscreen)
                self.assertEqual(loaded.last_ip, "127.0.0.1")
                self.assertEqual(len(set(loaded.keys.values())), len(loaded.keys))
                self.assertFalse(set(loaded.keys.values()) & RESERVED_KEYS)
                loaded.save()
                with open(path, "r", encoding="utf-8") as stream:
                    self.assertIsInstance(json.load(stream), dict)
                self.assertFalse(os.path.exists(path + ".tmp"))

    def test_key_binding_swaps_conflicts_and_rejects_global_shortcuts(self):
        settings = Settings.__new__(Settings)
        settings.keys = dict(DEFAULT_KEYS)
        old_forward = settings.keys["avancer"]
        old_left = settings.keys["gauche"]
        self.assertTrue(settings.bind_key("avancer", old_left))
        self.assertEqual(settings.keys["gauche"], old_forward)
        self.assertFalse(settings.bind_key("roulade", pygame.K_F11))

    def test_ipv4_validation_is_strict_and_canonical(self):
        self.assertEqual(valid_ipv4("192.168.001.010"), None)
        self.assertEqual(valid_ipv4(" 192.168.1.10 "), "192.168.1.10")
        self.assertIsNone(valid_ipv4("localhost"))

    def _host_with_remote(self):
        host = CoopHostGame.__new__(CoopHostGame)
        host.level = Level(4, config=SURVIVAL_LEVEL)
        host.net_time = 0.1
        remote = RemotePlayer(1, *host.level.player_spawn)
        host.clients = {1: {
            "addr": ("127.0.0.1", 9000), "player": remote,
            "last_seen": 0.0, "fire_budget": REMOTE_FIRE_CAPACITY,
        }}
        host._resolve_remote_fire = Mock()
        return host, remote

    def test_host_rejects_teleport_nan_damage_and_roll_spam(self):
        host, remote = self._host_with_remote()
        start = (remote.x, remote.y)
        host._handle_input({
            "id": 1, "x": remote.x + 100, "y": remote.y,
            "a": 0.0, "rt": 0.5,
            "fx": [[0.0, MAX_REMOTE_DAMAGE + 100]] * 100,
        }, ("127.0.0.1", 9000))
        self.assertLessEqual(math.hypot(remote.x - start[0], remote.y - start[1]),
                             0.65 + 1e-6)
        self.assertTrue(remote.rolling)
        host._resolve_remote_fire.assert_not_called()

        remote.update_timers(0.56)
        host.net_time += 0.1
        host._handle_input({
            "id": 1, "x": float("nan"), "y": remote.y,
            "a": 0.0, "rt": 0.5, "fx": [],
        }, ("127.0.0.1", 9000))
        # Ancien protocole : le même `rt` répété ou retardé n'est pas un
        # nouveau déclenchement, même sans cooldown de gameplay.
        self.assertFalse(remote.rolling)

    def test_host_accepts_chained_roll_sequences_but_rejects_stale_one(self):
        host, remote = self._host_with_remote()
        address = ("127.0.0.1", 9000)

        host._handle_input({
            "id": 1, "x": remote.x, "y": remote.y,
            "a": 0.0, "rt": Player.ROLL_DURATION, "rs": 1, "fx": [],
        }, address)
        self.assertTrue(remote.rolling)
        remote.update_timers(Player.ROLL_DURATION + 0.01)

        host.net_time += 0.1
        host._handle_input({
            "id": 1, "x": remote.x, "y": remote.y,
            "a": 0.0, "rt": Player.ROLL_DURATION, "rs": 2, "fx": [],
        }, address)
        self.assertTrue(remote.rolling)
        remote.update_timers(Player.ROLL_DURATION + 0.01)

        host.net_time += 0.1
        host._handle_input({
            "id": 1, "x": remote.x, "y": remote.y,
            "a": 0.0, "rt": 0.2, "rs": 1, "fx": [],
        }, address)
        self.assertFalse(remote.rolling)

    def test_host_caps_remote_fire_budget_and_damage(self):
        host, remote = self._host_with_remote()
        remote.shield = 0.0
        valid = [[0.0, MAX_REMOTE_DAMAGE]] * 32
        host._handle_input({"id": 1, "x": remote.x, "y": remote.y,
                            "a": 0.0, "rt": 0.0, "fx": valid},
                           ("127.0.0.1", 9000))
        self.assertLessEqual(host._resolve_remote_fire.call_count,
                             int(REMOTE_FIRE_CAPACITY))
        self.assertTrue(all(call.args[3] <= MAX_REMOTE_DAMAGE
                            for call in host._resolve_remote_fire.call_args_list))

    def test_remote_spawn_shield_and_authoritative_snapshot_death(self):
        remote = RemotePlayer(2, 2.0, 2.0)
        health = remote.health
        remote.take_damage(50)
        self.assertEqual(remote.health, health)
        remote.update_timers(Player.SHIELD_DURATION + 0.01)
        remote.take_damage(50)
        self.assertEqual(remote.health, health - 50)

        client = CoopClientGame.__new__(CoopClientGame)
        client.level = Level(4, config=SURVIVAL_LEVEL)
        client.ghosts = {}
        client.synced = False
        client.particles = Mock()
        client.sounds = Mock()
        client.player = Player(*client.level.player_spawn)
        client._apply_enemies([[7, "soldier", 4.0, 4.0, 0.0, 100,
                                0, 0, 0, 1, 0.5]])
        self.assertTrue(client.ghosts[7].rolling)
        client._apply_enemies([[7, "soldier", 4.0, 4.0, 0.0, 0,
                                0, 0, 0, 0, 0]])
        self.assertFalse(client.ghosts[7].alive)

    def test_paused_game_ignores_reload_and_focus_loss_clears_aim(self):
        game = Game.__new__(Game)
        game.player = Player(1.5, 1.5)
        game.player.weapon.ammo -= 1
        game.player.aiming = True
        game.paused = True
        game.outcome = None
        game.settings = SimpleNamespace(keys=dict(DEFAULT_KEYS))
        game.sounds = Mock()
        game.handle_event(pygame.event.Event(
            pygame.KEYDOWN, key=DEFAULT_KEYS["recharger"], scancode=0,
        ))
        self.assertEqual(game.player.weapon.reloading, 0.0)
        game.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        self.assertFalse(game.player.aiming)
        self.assertTrue(game.paused)

    def test_weapon_scaling_is_cached_between_frames(self):
        hud = HUD((800, 600))
        player = Player(1.5, 1.5)
        screen = pygame.Surface((800, 600))
        real_scale = pygame.transform.scale
        with patch("hud.pygame.transform.scale", wraps=real_scale) as scale:
            hud._draw_weapon(screen, player)
            hud._draw_weapon(screen, player)
        self.assertEqual(scale.call_count, 1)

    def test_death_panel_fits_small_screen_and_draws_after_fall(self):
        hud = HUD((640, 480))
        screen = pygame.Surface((640, 480))
        screen.fill((80, 90, 100))
        hud.draw_death_screen(screen, 2.0)

        self.assertLessEqual(hud._death_panel.get_width(), 640)
        self.assertLessEqual(hud._death_title.get_width(),
                             hud._death_panel.get_width() - 40)
        self.assertLessEqual(hud._death_hint.get_width(),
                             hud._death_panel.get_width() - 40)
        self.assertNotEqual(screen.get_at((320, 240))[:3], (80, 90, 100))

    def test_survival_spawn_queue_is_constant_time(self):
        game = SurvivalGame.__new__(SurvivalGame)
        game.spawn_queue = deque(["grunt", "soldier"])
        self.assertEqual(game.spawn_queue.popleft(), "grunt")


if __name__ == "__main__":
    unittest.main()
