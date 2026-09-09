"""Grenade bornée : mouvement 2D avec rebonds et fusée au temps de simulation."""

import math

import pygame

FUSE = 2.0
RADIUS = 2.7
DAMAGE = 90


class Grenade:
    SPRITE_HEIGHT = .18
    _surface = None

    def __init__(self, ident, owner, x, y, angle=0):
        self.ident, self.owner = ident, owner
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle) * 6, math.sin(angle) * 6
        self.timer = FUSE

    @property
    def v_offset(self):
        return .05 + .4 * math.sin(math.pi * (FUSE - self.timer) / FUSE)

    def current_sprite(self, player=None):
        if Grenade._surface is None:
            surface = pygame.Surface((24, 24), pygame.SRCALPHA)
            pygame.draw.circle(surface, (74, 95, 57), (12, 14), 8)
            pygame.draw.rect(surface, (235, 192, 91), (10, 2, 5, 7))
            pygame.draw.circle(surface, (255, 115, 70), (12, 14), 9, 2)
            Grenade._surface = surface
        return Grenade._surface

    def step(self, dt, blocked):
        if type(dt) not in (int, float) or not math.isfinite(dt) or not 0 <= dt <= .25:
            return False
        dt = min(dt, max(0, self.timer))
        self.timer = max(0.0, self.timer - dt)
        steps = max(1, math.ceil(math.hypot(self.vx, self.vy) * dt / .08))
        for _ in range(steps):
            x = self.x + self.vx * dt / steps
            if any(blocked(x + dx, self.y + dy) for dx in (-.08, .08) for dy in (-.08, .08)):
                self.vx *= -.55
            else:
                self.x = x
            y = self.y + self.vy * dt / steps
            if any(blocked(self.x + dx, y + dy) for dx in (-.08, .08) for dy in (-.08, .08)):
                self.vy *= -.55
            else:
                self.y = y
        drag = math.exp(-dt)
        self.vx *= drag
        self.vy *= drag
        return self.timer <= 1e-9

    def snapshot(self):
        return [self.ident, self.owner, round(self.x, 3), round(self.y, 3), round(self.timer, 3)]


def read_grenades(rows):
    if not isinstance(rows, list) or len(rows) > 8:
        return None
    result, seen = [], set()
    for row in rows:
        if (not isinstance(row, list) or len(row) != 5
                or any(type(v) is not int or not 0 <= v < 2 ** 31 for v in row[:2])
                or row[0] in seen
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in row[2:])
                or not 0 <= row[2] <= 256 or not 0 <= row[3] <= 256 or not 0 <= row[4] <= FUSE):
            return None
        grenade = Grenade(*row[:4])
        grenade.timer = row[4]
        result.append(grenade)
        seen.add(row[0])
    return result
