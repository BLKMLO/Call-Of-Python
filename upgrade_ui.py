"""Choix accessibles clavier, souris, tactile et croix directionnelle.

Jusqu'à quatre cartes : trois d'arme puis une hors arme (bordure ambre).
"""

import pygame

from upgrades import PERKS, UPGRADES

CARD_KEYS = (pygame.K_F5, pygame.K_F6, pygame.K_F7, pygame.K_F8)
CARD_BUTTONS = (pygame.CONTROLLER_BUTTON_DPAD_LEFT, pygame.CONTROLLER_BUTTON_DPAD_UP,
                pygame.CONTROLLER_BUTTON_DPAD_RIGHT, pygame.CONTROLLER_BUTTON_DPAD_DOWN)
CARD_ARROWS = ("←", "↑", "→", "↓")


def choice_rects(size, count=4):
    width, height = size
    gap = 8
    card_width = (width - 32 - (count - 1) * gap) // count
    return [pygame.Rect(16 + i * (card_width + gap), height - 220, card_width, 72)
            for i in range(count)]


def choice_event(event, size, build):
    if not build.offers:
        return None
    count = len(build.offers)
    if event.type == pygame.KEYDOWN:
        index = CARD_KEYS.index(event.key) if event.key in CARD_KEYS else None
    elif event.type == pygame.CONTROLLERBUTTONDOWN:
        index = CARD_BUTTONS.index(event.button) if event.button in CARD_BUTTONS else None
    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        index = _hit(event.pos, size, count)
    elif event.type == pygame.FINGERDOWN:
        index = _hit((event.x * size[0], event.y * size[1]), size, count)
    else:
        return None
    return index if index is not None and index < count else None


def _hit(point, size, count):
    return next((i for i, rect in enumerate(choice_rects(size, count))
                 if rect.collidepoint(point)), None)


def draw_choices(screen, hud, build):
    if not build.offers:
        return
    for index, rect in enumerate(choice_rects(screen.get_size(), len(build.offers))):
        key = build.offers[index]
        perk = key in PERKS
        pygame.draw.rect(screen, (34, 24, 10) if perk else (10, 25, 32), rect, border_radius=4)
        pygame.draw.rect(screen, (240, 178, 72) if perk else (82, 220, 153), rect, 1,
                         border_radius=4)
        name, description = UPGRADES[key]
        level = build.levels.get(key, 0)
        if index == 0:
            footer = f"Auto : choix 1 dans {build.remaining:.0f} s"
        else:
            footer = "Hors arme" if perk else "Arme"
            footer += f" - niv. {level + 1}"
        contents = (f"F{index + 5} / {CARD_ARROWS[index]} : {name}", description, footer)
        for line, content in enumerate(contents):
            text = hud.small_font.render(content, True, (220, 231, 230))
            if text.get_width() > rect.width - 12:
                text = pygame.transform.smoothscale(text, (rect.width - 12, text.get_height()))
            screen.blit(text, (rect.x + 6, rect.y + 5 + line * 22))
