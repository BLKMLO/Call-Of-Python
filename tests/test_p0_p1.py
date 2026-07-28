"""Non-régressions des corrections P0/P1 de robustesse et de coopération."""

import math
import os
import unittest
from collections import OrderedDict, deque
from unittest.mock import Mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from coop import (
    MOVE_BURST_SECONDS,
    MOVE_JITTER,
    PROTOCOL_VERSION,
    CoopClientGame,
    CoopHostGame,
    _starting_remote_weapons,
)
from entities import Player, RemotePlayer, Soldier
from level import SURVIVAL_LEVEL, Level
from network import COMPRESSED_PREFIX, UdpPeer
from raycaster import Raycaster


class _ReceiveSocket:
    def __init__(self, packets):
        self.packets = deque(packets)

    def recvfrom(self, _size):
        if not self.packets:
            raise BlockingIOError
        return self.packets.popleft()


class _SendSocket:
    def __init__(self):
        self.packets = []

    def sendto(self, data, addr):
        self.packets.append((data, addr))


class PriorityFixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1, 1))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _host_with_v2_remote(self):
        host = CoopHostGame.__new__(CoopHostGame)
        host.level = Level(4, config=SURVIVAL_LEVEL)
        host.net_time = 0.0
        host.paused = False
        host.outcome = None
        host.session_id = "p0-p1-session"
        host.event_sequence = 0
        host.event_journal = deque()
        host.net_events = []
        host.enemies = []
        host.player = Player(*host.level.player_spawn)
        host.player.health = 0
        remote = RemotePlayer(1, *host.level.player_spawn)
        capacity = Player.SPEED * MOVE_BURST_SECONDS + MOVE_JITTER
        host.clients = {1: {
            "addr": ("127.0.0.1", 9000),
            "player": remote,
            "last_seen": 0.0,
            "protocol": PROTOCOL_VERSION,
            "last_input_sequence": -1,
            "last_reload_sequence": 0,
            "event_ack": 0,
            "move_credit": capacity,
            "last_motion_time": 0.0,
            "last_roll_sequence": 0,
            "pending_roll_sequence": None,
            "legacy_roll_latched": False,
            "weapons": _starting_remote_weapons(),
            "active_weapon": "rifle",
        }}
        host._resolve_remote_shot = Mock()
        return host, remote

    @staticmethod
    def _open_horizontal(level):
        for y in range(1, level.height - 1):
            for x in range(1, level.width - 5):
                points = [(x + offset + 0.5, y + 0.5)
                          for offset in range(5)]
                if all(level.can_stand(px, py, 0.31) for px, py in points):
                    return points
        raise AssertionError("Aucun couloir horizontal trouvé")

    def test_sprite_cache_obeys_memory_budget_and_lru(self):
        raycaster = Raycaster.__new__(Raycaster)
        raycaster._sprite_cache = OrderedDict()
        raycaster._sprite_cache_bytes = 0
        raycaster._sprite_cache_budget = 1024 * 1024
        source = pygame.Surface((64, 96), pygame.SRCALPHA)

        for index in range(40):
            raycaster._scaled_sprite(
                source, 120 + index * 4, 160 + index * 4,
            )

        self.assertLessEqual(
            raycaster._sprite_cache_bytes,
            raycaster._sprite_cache_budget,
        )
        self.assertLess(len(raycaster._sprite_cache), 40)
        self.assertNotIn((id(source), 120, 160), raycaster._sprite_cache)

    def test_player_cannot_cross_enemy_even_with_large_dt(self):
        level = Level(4, config=SURVIVAL_LEVEL)
        points = self._open_horizontal(level)
        player = Player(*points[0])
        player.angle = 0.0
        enemy = Soldier(*points[1])
        keys = [True, False, False, False]
        bindings = {
            "avancer": 0, "reculer": 1, "droite": 2, "gauche": 3,
        }

        player.move(
            1.0, keys, bindings, level, blockers=[enemy],
        )

        self.assertLess(player.x, enemy.x)
        self.assertGreaterEqual(
            math.hypot(player.x - enemy.x, player.y - enemy.y),
            player.RADIUS + enemy.RADIUS - 1e-6,
        )

    def test_host_speed_budget_is_real_time_based(self):
        host, remote = self._host_with_v2_remote()
        address = host.clients[1]["addr"]
        start = (remote.x, remote.y)

        for sequence in range(1, 31):
            host.net_time = sequence / 30
            host._handle_input({
                "t": "in", "id": 1, "sid": host.session_id,
                "iq": sequence, "ea": 0,
                "x": remote.x + 10.0, "y": remote.y, "a": 0.0,
                "ad": 0, "rt": 0.0, "rs": 0, "rl": 0,
                "wid": "rifle", "fx": [],
            }, address)

        travelled = math.hypot(remote.x - start[0], remote.y - start[1])
        self.assertLessEqual(
            travelled,
            Player.SPEED * 1.0
            + Player.SPEED * MOVE_BURST_SECONDS + MOVE_JITTER + 1e-6,
        )

    def test_host_pause_rejects_motion_roll_reload_and_fire(self):
        host, remote = self._host_with_v2_remote()
        host.paused = True
        address = host.clients[1]["addr"]
        start = (remote.x, remote.y)
        rifle = host.clients[1]["weapons"]["rifle"]
        rifle.ammo -= 1

        host._handle_input({
            "t": "in", "id": 1, "sid": host.session_id,
            "iq": 1, "ea": 0,
            "x": remote.x + 3.0, "y": remote.y, "a": 1.0,
            "ad": 0, "rt": Player.ROLL_DURATION, "rs": 1, "rl": 1,
            "wid": "rifle", "fx": [["rifle", [1.0]]],
        }, address)

        self.assertEqual((remote.x, remote.y), start)
        self.assertFalse(remote.rolling)
        self.assertEqual(rifle.reloading, 0.0)
        host._resolve_remote_shot.assert_not_called()

    def test_host_rejects_stale_input_sequence(self):
        host, remote = self._host_with_v2_remote()
        address = host.clients[1]["addr"]
        host.net_time = 0.1
        host._handle_input({
            "t": "in", "id": 1, "sid": host.session_id,
            "iq": 2, "ea": 0,
            "x": remote.x + 0.2, "y": remote.y, "a": 0.0,
            "ad": 0, "rt": 0.0, "rs": 0, "rl": 0,
            "wid": "rifle", "fx": [],
        }, address)
        accepted = (remote.x, remote.y)

        host.net_time = 0.2
        host._handle_input({
            "t": "in", "id": 1, "sid": host.session_id,
            "iq": 1, "ea": 0,
            "x": remote.x + 3.0, "y": remote.y, "a": 1.0,
            "ad": 0, "rt": 0.0, "rs": 0, "rl": 0,
            "wid": "rifle", "fx": [],
        }, address)

        self.assertEqual((remote.x, remote.y), accepted)
        self.assertEqual(remote.angle, 0.0)

    def test_host_retransmits_events_until_client_acknowledges(self):
        host, _remote = self._host_with_v2_remote()
        host.snapshot_sequence = 0
        host.peer = Mock()
        host.hud = Mock(flash=0)
        host.pickups = []
        host.survival_info = Mock(return_value={
            "wave": 1, "final": 30, "remaining": 1,
            "next_in": 0.0, "intermission": False,
        })
        host._queue_net_event(["rs", 1, 4.0, 5.0])

        host._broadcast()
        first = host.peer.send.call_args.args[0]
        host._broadcast()
        second = host.peer.send.call_args.args[0]
        self.assertEqual(first["rev"], [[1, ["rs", 1, 4.0, 5.0]]])
        self.assertEqual(second["rev"], first["rev"])
        self.assertEqual(len(host.event_journal), 1)

        host.clients[1]["event_ack"] = 1
        host._broadcast()
        third = host.peer.send.call_args.args[0]
        self.assertEqual(third["rev"], [])
        self.assertEqual(len(host.event_journal), 0)

    def test_snapshot_session_sequence_and_reliable_event_order(self):
        client = CoopClientGame.__new__(CoopClientGame)
        client.host_session = "session-a"
        client.last_snapshot_sequence = -1
        client.last_event_sequence = 0
        client.host_paused = False
        client.paused = False
        client.player = Player(1.5, 1.5)
        client.pending_fires = []
        client.touch = Mock()
        client._mouse_fire_held = False
        client._mouse_aim_held = False
        client._apply_players = Mock()
        client._apply_enemies = Mock()
        client._apply_pickups = Mock()
        client._apply_wave = Mock()
        client._apply_event = Mock()
        client.outcome = None
        client.synced = False

        gap = {
            "t": "snap", "sid": "session-a", "sq": 2,
            "pl": [], "en": [], "pa": 0,
            "rev": [[2, ["hm", 1, 0]]],
        }
        self.assertTrue(client._apply_snapshot(gap))
        client._apply_event.assert_not_called()
        self.assertEqual(client.last_event_sequence, 0)

        repaired = {
            "t": "snap", "sid": "session-a", "sq": 3,
            "pl": [], "en": [], "pa": 0,
            "rev": [
                [1, ["hm", 1, 0]],
                [2, ["hm", 1, 1]],
            ],
        }
        self.assertTrue(client._apply_snapshot(repaired))
        self.assertEqual(client._apply_event.call_count, 2)
        self.assertEqual(client.last_event_sequence, 2)

        client.pending_fires.append(["rifle", [0.0]])
        paused = {
            "t": "snap", "sid": "session-a", "sq": 4,
            "pl": [], "en": [], "pa": 1, "eb": 2, "rev": [],
        }
        self.assertTrue(client._apply_snapshot(paused))
        self.assertTrue(client.controls_paused)
        self.assertEqual(client.pending_fires, [])

        self.assertFalse(client._apply_snapshot({
            **repaired, "sq": 1,
        }))
        self.assertFalse(client._apply_snapshot({
            **repaired, "sid": "session-b", "sq": 5,
        }))
        self.assertEqual(client._apply_event.call_count, 2)

    def test_inventory_state_repairs_a_lost_pickup_event(self):
        client = CoopClientGame.__new__(CoopClientGame)
        client.player = Player(1.5, 1.5)
        client.player.add_weapon("shotgun", 1)
        client._apply_authoritative_inventory([
            ["pistol", 0],
            ["shotgun", 1],
            ["rifle", 1],
            ["minigun", 3],
        ], "minigun")

        minigun = next(
            weapon for weapon in client.player.weapons
            if weapon.spec.id == "minigun"
        )
        self.assertEqual(minigun.level, 3)

    def test_large_udp_snapshot_is_compressed_and_decoded(self):
        sender = UdpPeer.__new__(UdpPeer)
        sender.sock = _SendSocket()
        address = ("127.0.0.1", 5577)
        message = {
            "t": "snap",
            "en": [[index, "soldier", 12.5, 18.5, 0.0, 100] * 3
                   for index in range(80)],
        }

        sender.send(message, address, compress=True)
        payload, sent_to = sender.sock.packets[0]
        self.assertEqual(sent_to, address)
        self.assertTrue(payload.startswith(COMPRESSED_PREFIX))

        receiver = UdpPeer.__new__(UdpPeer)
        receiver.sock = _ReceiveSocket([(payload, address)])
        self.assertEqual(receiver.receive(), [(message, address)])

    def test_holstered_weapon_finishes_reloading(self):
        player = Player(1.5, 1.5)
        player.add_weapon("shotgun", 1)
        shotgun = player.weapon
        shotgun.ammo = 0
        shotgun.start_reload()
        player.select_weapon(0)

        player.update(shotgun.spec.reload_time + 0.01)

        self.assertEqual(shotgun.reloading, 0.0)
        self.assertEqual(shotgun.ammo, shotgun.spec.magazine_size)


if __name__ == "__main__":
    unittest.main()
