"""Télégraphie au sol projetée avec la caméra et le z-buffer du monde."""

import math

import pygame

from raycaster import COLUMN_WIDTH


def draw_boss_warnings(screen, player, renderer, enemies):
    for enemy in enemies:
        pattern = getattr(enemy, "pattern", None)
        if not enemy.alive or pattern is None or pattern.state not in ("warn", "charge"):
            continue
        if pattern.kind == "slam":
            points = [(pattern.x + math.cos(i * math.tau / 64) * 1.8,
                       pattern.y + math.sin(i * math.tau / 64) * 1.8) for i in range(64)]
        else:
            points = [(enemy.x + (pattern.x - enemy.x) * i / 32,
                       enemy.y + (pattern.y - enemy.y) * i / 32) for i in range(33)]
        for x, y in points:
            projected = renderer._project(player, x, y)
            if projected is None:
                continue
            depth, delta = projected
            sx = int((.5 + delta / renderer.fov) * renderer.width)
            ray = sx // COLUMN_WIDTH
            if not 0 <= ray < renderer.num_rays or renderer.z_buffer[ray] < depth:
                continue
            sy = renderer.horizon + int(renderer.screen_dist * .5 / depth)
            pygame.draw.circle(screen, (255, 130, 65), (sx, sy), 3)
