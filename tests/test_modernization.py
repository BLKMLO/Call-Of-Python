"""Non-regressions de la modernisation P0-P2."""

import os
import secrets
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import settings as settings_module
from coop import PROTOCOL_VERSION, CoopHostGame
from difficulty import ThreatDirector, get_difficulty
from gamepad import _axis_value
from level import Level
from network import SAFE_DATAGRAM_SIZE, UdpPeer
from raycaster import Raycaster
from runtime import SIMULATION_STEP, FixedStepClock
from settings import Settings


class _RecorderPeer:
    def __init__(self):
        self.messages = []

    def send(self, message, addr, compress=False):
        self.messages.append((message, addr, compress))
        return True


class ModernizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_fixed_step_is_repeatable_and_drops_excess_backlog(self):
        clock = FixedStepClock()
        self.assertEqual(clock.advance(SIMULATION_STEP * 3.5), 3)
        self.assertAlmostEqual(clock.alpha, 0.5)
        self.assertEqual(clock.advance(10.0), clock.max_steps)
        self.assertGreater(clock.dropped_time, 0.0)
        self.assertLess(clock.accumulator, clock.step)

    def test_udp_fragments_and_reassembles_below_safe_mtu(self):
        receiver = UdpPeer(0)
        sender = UdpPeer()
        try:
            address = ("127.0.0.1", receiver.sock.getsockname()[1])
            message = {"t": "diagnostic", "payload": secrets.token_hex(5000)}
            self.assertTrue(sender.send(message, address, compress=False))
            self.assertGreater(sender.metrics.sent_datagrams, 1)
            self.assertGreater(sender.metrics.fragmented_messages, 0)
            self.assertLessEqual(
                sender.metrics.sent_bytes,
                sender.metrics.sent_datagrams * SAFE_DATAGRAM_SIZE,
            )
            received = receiver.receive()
            self.assertEqual([item[0] for item in received], [message])
            self.assertEqual(receiver.metrics.reassembled_messages, 1)
        finally:
            sender.close()
            receiver.close()

    def test_host_port_is_exclusive(self):
        first = UdpPeer(0)
        second = None
        try:
            port = first.sock.getsockname()[1]
            with self.assertRaises(OSError):
                second = UdpPeer(port)
        finally:
            if second is not None:
                second.close()
            first.close()

    def test_protocol_version_mismatch_is_rejected_explicitly(self):
        host = CoopHostGame.__new__(CoopHostGame)
        host.peer = _RecorderPeer()
        host.clients = {}
        address = ("127.0.0.1", 40000)
        host._handle_join({"t": "join", "v": PROTOCOL_VERSION - 1}, address)
        response, target, _compress = host.peer.messages[0]
        self.assertEqual(target, address)
        self.assertEqual(response["t"], "incompatible")
        self.assertEqual(response["expected"], PROTOCOL_VERSION)
        self.assertFalse(host.clients)

    def test_difficulty_and_director_only_adjust_declared_pressure(self):
        recruit = get_difficulty("recruit")
        veteran = get_difficulty("veteran")
        self.assertLess(recruit.enemy_damage, veteran.enemy_damage)
        self.assertGreater(recruit.spawn_interval, veteran.spawn_interval)
        director = ThreatDirector("soldier")
        low_health = director.observe(0.1, 0.2)
        for _ in range(40):
            high_health = director.observe(1.0, 0.0)
        self.assertGreater(low_health, high_health)

    def test_accessibility_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "settings.json")
            with patch.object(settings_module, "SETTINGS_FILE", path):
                settings = Settings()
                settings.fov = 85
                settings.camera_shake = 0.5
                settings.toggle_ads = True
                settings.difficulty = "veteran"
                settings.save()
                loaded = Settings()
        self.assertEqual(loaded.fov, 85)
        self.assertEqual(loaded.camera_shake, 0.5)
        self.assertTrue(loaded.toggle_ads)
        self.assertEqual(loaded.difficulty, "veteran")

    def test_raycaster_applies_configured_fov_once(self):
        raycaster = Raycaster((320, 240), Level(0), fov=1.2)
        self.assertAlmostEqual(raycaster.fov, 1.2)
        raycaster.resize((640, 360))
        self.assertAlmostEqual(raycaster.fov, 1.2)

    def test_gamepad_deadzone_is_normalized(self):
        self.assertEqual(_axis_value(1000), 0.0)
        self.assertAlmostEqual(_axis_value(32767), 1.0)
        self.assertAlmostEqual(_axis_value(-32768), -1.0)


if __name__ == "__main__":
    unittest.main()
