"""Variantes lisibles et aura de commandement sans accumulation de bonus."""

import math
from collections import OrderedDict

import pygame

ELITES = ("bulwark", "hunter")
_CACHE = OrderedDict()


def apply_elite(enemy, kind):
    if kind not in ELITES or enemy.IS_BOSS or enemy.KIND == "commander" or enemy.elite:
        return
    enemy.elite = kind
    factor = .9 if kind == "bulwark" else 1.15
    enemy._base_speed *= factor
    enemy.SPEED *= factor
    if kind == "bulwark":
        enemy.max_health = round(enemy.max_health * 1.35)
        enemy.health = enemy.max_health


def update_command(enemies, visible):
    commanders = [e for e in enemies if e.alive and e.KIND == "commander"][:1]
    for enemy in enemies:
        enemy.commanded = bool(enemy.alive and not enemy.IS_BOSS and enemy.KIND != "commander"
                               and any(math.hypot(enemy.x - c.x, enemy.y - c.y) <= 5
                                       and visible(enemy.x, enemy.y, c.x, c.y) for c in commanders))


def variant_sprite(surface, kind):
    if not kind:
        return surface
    key = (surface, kind)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    result = surface.copy()
    color = {"bulwark": (80, 135, 255), "hunter": (245, 100, 70),
             "commander": (255, 205, 70), "commanded": (90, 200, 210)}[kind]
    overlay = surface.copy()
    overlay.fill((*color, 0), special_flags=pygame.BLEND_RGB_MAX)
    overlay.set_alpha(60)
    result.blit(overlay, (0, 0))
    pygame.draw.line(result, color, (result.get_width() // 2 - 5, 3),
                     (result.get_width() // 2 + 5, 3), 2)
    _CACHE[key] = result
    if len(_CACHE) > 128:
        _CACHE.popitem(last=False)
    return result
