"""Balise d'objectif dessinée une fois, sans dépendre de nouveaux assets."""

import pygame


class MissionMarker:
    SPRITE_HEIGHT = 0.75
    v_offset = 0.25

    def __init__(self):
        self.x = self.y = 0.0
        self.surface = pygame.Surface((48, 64), pygame.SRCALPHA)
        pygame.draw.rect(self.surface, (13, 35, 39), (7, 8, 34, 48), border_radius=4)
        pygame.draw.rect(self.surface, (82, 220, 153), (7, 8, 34, 48), 3, border_radius=4)
        pygame.draw.line(self.surface, (230, 245, 233), (24, 19), (24, 35), 5)
        pygame.draw.circle(self.surface, (230, 245, 233), (24, 44), 3)

    def current_sprite(self, player=None):
        return self.surface

    def sprites(self, mission):
        step = mission.current
        if step is None:
            return []
        self.x, self.y = step.x, step.y
        return [self]
