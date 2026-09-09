"""Choix accessibles clavier, souris, tactile et croix directionnelle."""

import pygame

from upgrades import UPGRADES


def choice_rects(size):
    width, height = size
    gap = 8
    card_width = (width - 32 - 2 * gap) // 3
    return [pygame.Rect(16 + i * (card_width + gap), height - 220, card_width, 72)
            for i in range(3)]


def choice_event(event, size, build):
    if not build.offers:
        return None
    if event.type == pygame.KEYDOWN:
        return {pygame.K_F5: 0, pygame.K_F6: 1, pygame.K_F7: 2}.get(event.key)
    if event.type == pygame.CONTROLLERBUTTONDOWN:
        return {pygame.CONTROLLER_BUTTON_DPAD_LEFT: 0,
                pygame.CONTROLLER_BUTTON_DPAD_UP: 1,
                pygame.CONTROLLER_BUTTON_DPAD_RIGHT: 2}.get(event.button)
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
        point = event.pos
    elif event.type == pygame.FINGERDOWN:
        point = (event.x * size[0], event.y * size[1])
    else:
        return None
    return next((i for i, rect in enumerate(choice_rects(size)) if rect.collidepoint(point)), None)


def draw_choices(screen, hud, build):
    if not build.offers:
        return
    for index, rect in enumerate(choice_rects(screen.get_size())):
        pygame.draw.rect(screen, (10, 25, 32), rect, border_radius=4)
        pygame.draw.rect(screen, (82, 220, 153), rect, 1, border_radius=4)
        name, description = UPGRADES[build.offers[index]]
        footer = (f"Auto : choix 1 dans {build.remaining:.0f} s" if index == 0
                  else "Pour cette partie")
        contents = (f"F{index + 5} / {('←', '↑', '→')[index]} : {name}", description, footer)
        for line, content in enumerate(contents):
            text = hud.small_font.render(content, True, (220, 231, 230))
            if text.get_width() > rect.width - 12:
                text = pygame.transform.smoothscale(text, (rect.width - 12, text.get_height()))
            screen.blit(text, (rect.x + 6, rect.y + 5 + line * 22))
