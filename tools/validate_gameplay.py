"""Recette reproductible : rendu, loopback, MTU et 24 ennemis vivants.

Lancer depuis la racine : python tools/validate_gameplay.py --stage 1 --output /tmp/cop-qa
Le benchmark compare des exécutions sur la même machine, pas des FPS matériels.
"""

import argparse
import json
import os
import random
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pygame

from coop import CoopClientGame, CoopHostGame
from game import Game
from level import SURVIVAL_LEVEL
from settings import Settings


class MeasuredSocket:
    def __init__(self, sock):
        self.sock = sock
        self.maximum = 0

    def sendto(self, data, address):
        self.maximum = max(self.maximum, len(data))
        assert len(data) <= 1200, len(data)
        return self.sock.sendto(data, address)

    def __getattr__(self, name):
        return getattr(self.sock, name)


def validate(stage, output):
    output.mkdir(parents=True, exist_ok=True)
    pygame.init()
    random.seed(101)
    settings, sounds = Settings(), Mock()
    reports = []
    try:
        for size in ((800, 600), (1280, 720)):
            screen = pygame.display.set_mode(size)
            game = Game(screen, settings, sounds, level_config=SURVIVAL_LEVEL)
            try:
                positions = [(x + 0.5, y + 0.5)
                             for y in range(2, game.level.height - 2, 2)
                             for x in range(2, game.level.width - 2, 2)
                             if not game.level.is_wall(x + 0.5, y + 0.5)]
                for index, (x, y) in enumerate(positions[:24]):
                    game.spawn_enemy(("grunt", "soldier", "heavy")[index % 3], x, y)
                assert len(game.enemies) == 24
                times = []
                for frame in range(80):
                    game.player.health = game.player.max_health
                    game.player.shield = 3
                    started = time.perf_counter()
                    game.update(1 / 60)
                    game.draw(screen)
                    elapsed = (time.perf_counter() - started) * 1000
                    if frame >= 20:
                        times.append(elapsed)
                assert sum(e.alive for e in game.enemies) == 24
                pygame.image.save(screen, output / f"stage-{stage}-{size[0]}-24.png")
            finally:
                game.close()
            host = CoopHostGame(screen, settings, sounds, port=0)
            client = CoopClientGame(screen, settings, sounds, "127.0.0.1",
                                    port=host.peer.sock.getsockname()[1])
            host.peer.sock = MeasuredSocket(host.peer.sock)
            client.peer.sock = MeasuredSocket(client.peer.sock)
            try:
                host.intermission = 1000
                for x, y in positions[:24]:
                    host.spawn_enemy("grunt", x, y)
                for _ in range(120):
                    host.update(1 / 60)
                    client.update(1 / 60)
                assert client.synced and len(client.ghosts) == 24
                host.draw(screen)
                client.draw(screen)
                pygame.image.save(screen, output / f"stage-{stage}-{size[0]}-coop.png")
                reports.append(dict(resolution=list(size), alive=24,
                                    median_ms=round(statistics.median(times), 3),
                                    p95_ms=round(sorted(times)[56], 3),
                                    maximum_datagram=max(host.peer.sock.maximum,
                                                         client.peer.sock.maximum),
                                    loopback=True))
            finally:
                client.close()
                host.close()
    finally:
        pygame.quit()
    result = dict(stage=stage, seed=101, measurements=reports)
    (output / f"stage-{stage}.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate(args.stage, args.output)
