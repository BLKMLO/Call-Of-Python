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


SHIELD_SPEED = 0.85   # le porte-bouclier avance plus lentement
SWARM_SPEED = 1.25    # les kamikazes d'un essaim foncent plus vite


def apply_shield(enemy):
    """Porte-bouclier : bouclier frontal (voir `weapons.shield_blocks`)."""
    if enemy.IS_BOSS or enemy.EXPLODES or enemy.shielded:
        return
    enemy.shielded = True
    enemy._base_speed *= SHIELD_SPEED
    enemy.SPEED *= SHIELD_SPEED


def apply_swarm(enemy):
    """Membre d'un essaim : plus rapide, arrive en grappe."""
    if enemy.IS_BOSS or enemy.swarm:
        return
    enemy.swarm = True
    enemy._base_speed *= SWARM_SPEED
    enemy.SPEED *= SWARM_SPEED


def apply_traits(enemy, traits):
    if traits == "shield":
        apply_shield(enemy)
    elif traits == "swarm":
        apply_swarm(enemy)


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
             "commander": (255, 205, 70), "commanded": (90, 200, 210),
             "hostage": (250, 240, 210), "sealed": (110, 200, 255)}[kind]
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


def shield_sprite(surface, lowered=False):
    """Superpose un bouclier anti-émeute au billboard (caché par surface)."""
    key = (surface, "shield-low" if lowered else "shield")
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    result = surface.copy()
    box = surface.get_bounding_rect(min_alpha=8)
    if box.width and box.height:
        w = max(6, int(box.width * 0.62))
        h = max(8, int(box.height * 0.5))
        shield = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(shield, (120, 146, 170, 215), shield.get_rect(),
                         border_radius=max(2, w // 6))
        pygame.draw.rect(shield, (210, 228, 240, 255), shield.get_rect(), 2,
                         border_radius=max(2, w // 6))
        slit = pygame.Rect(w // 5, h // 6, w * 3 // 5, max(2, h // 10))
        pygame.draw.rect(shield, (30, 40, 52, 230), slit)
        pygame.draw.line(shield, (255, 255, 255, 120), (3, 3), (3, h - 4), 1)
        if lowered:
            shield = pygame.transform.rotate(shield, -38)
            pos = (box.left - w // 6, box.top + int(box.height * 0.42))
        else:
            pos = (box.centerx - w // 2, box.top + int(box.height * 0.3))
        result.blit(shield, pos)
    _CACHE[key] = result
    if len(_CACHE) > 128:
        _CACHE.popitem(last=False)
    return result
