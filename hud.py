"""Interface en jeu (HUD) : viseur, arme, barre de vie, munitions, minimap.

Tout est dessiné procéduralement, sans aucun asset externe. L'arme du
joueur est un simple polygone en bas de l'écran, animé d'un balancement
à la marche et d'un recul au tir.
"""

import math

import pygame


class HUD:
    def __init__(self, size):
        self.resize(size)
        self.kick = 0.0        # recul de l'arme (0 → 1)
        self.flash = 0.0       # éclair de bouche
        self.sway_time = 0.0   # horloge du balancement

    def resize(self, size):
        self.width, self.height = size
        self.font = pygame.font.Font(None, max(22, self.height // 24))
        self.big_font = pygame.font.Font(None, max(36, self.height // 12))

    # ------------------------------------------------------------------
    # Notifications venant du jeu
    # ------------------------------------------------------------------
    def on_player_shot(self):
        self.kick = 1.0
        self.flash = 0.06

    def update(self, dt, moving):
        self.kick = max(0.0, self.kick - dt * 8)
        self.flash = max(0.0, self.flash - dt)
        if moving:
            self.sway_time += dt

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def draw(self, screen, player, enemies, level):
        self._draw_weapon(screen)
        self._draw_crosshair(screen)
        self._draw_status(screen, player, enemies)
        self._draw_minimap(screen, player, enemies, level)
        self._draw_hurt_flash(screen, player)

    def _draw_weapon(self, screen):
        """Fusil vu à la première personne, en bas à droite du centre."""
        w, h = self.width, self.height
        sway_x = math.sin(self.sway_time * 7) * w * 0.008
        sway_y = abs(math.cos(self.sway_time * 7)) * h * 0.008
        kick_y = self.kick * h * 0.03
        cx = w // 2 + int(w * 0.10 + sway_x)
        cy = h + int(kick_y + sway_y)

        gun_dark = (38, 38, 42)
        gun_mid = (58, 58, 64)
        # crosse / corps de l'arme (trapèze partant du bas de l'écran)
        pygame.draw.polygon(screen, gun_mid, [
            (cx - w // 22, cy), (cx + w // 8, cy),
            (cx + w // 22, cy - h // 5), (cx - w // 40, cy - h // 5),
        ])
        # canon
        pygame.draw.rect(screen, gun_dark,
                         (cx - w // 90, cy - h // 3, w // 45, h // 7))
        if self.flash > 0.0:
            tip = (cx, cy - h // 3)
            pygame.draw.circle(screen, (255, 230, 120), tip, h // 30)
            pygame.draw.circle(screen, (255, 255, 210), tip, h // 60)

    def _draw_crosshair(self, screen):
        cx, cy = self.width // 2, self.height // 2
        gap, size = 5, 11
        color = (230, 230, 230)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(screen, color,
                             (cx + dx * gap, cy + dy * gap),
                             (cx + dx * size, cy + dy * size), 2)

    def _draw_status(self, screen, player, enemies):
        """Barre de vie + munitions + compteur d'ennemis restants."""
        margin = 14
        bar_w, bar_h = int(self.width * 0.22), 16
        y = self.height - bar_h - margin
        frac = max(0.0, player.health / player.max_health)
        color = (70, 190, 80) if frac > 0.35 else (210, 60, 50)
        pygame.draw.rect(screen, (25, 25, 28), (margin, y, bar_w, bar_h))
        pygame.draw.rect(screen, color, (margin, y, int(bar_w * frac), bar_h))
        pygame.draw.rect(screen, (200, 200, 200), (margin, y, bar_w, bar_h), 1)
        hp_text = self.font.render(f"{player.health} PV", True, (235, 235, 235))
        screen.blit(hp_text, (margin, y - hp_text.get_height() - 4))

        weapon = player.weapon
        if weapon.reloading > 0.0:
            ammo_str = "RECHARGEMENT..."
        else:
            ammo_str = f"{weapon.ammo} / {weapon.magazine_size}"
        ammo_text = self.big_font.render(ammo_str, True, (235, 235, 235))
        screen.blit(ammo_text, (self.width - ammo_text.get_width() - margin,
                                self.height - ammo_text.get_height() - margin))

        remaining = sum(1 for e in enemies if e.alive)
        info = self.font.render(f"Ennemis restants : {remaining}", True, (220, 220, 160))
        screen.blit(info, (self.width - info.get_width() - margin, margin))

    def _draw_minimap(self, screen, player, enemies, level, scale=6):
        """Petite carte en haut à gauche (murs, joueur, ennemis vivants)."""
        surf = pygame.Surface((level.width * scale, level.height * scale), pygame.SRCALPHA)
        surf.fill((10, 10, 14, 150))
        for y in range(level.height):
            for x in range(level.width):
                if level.grid[y][x] != ".":
                    pygame.draw.rect(surf, (170, 170, 180, 200),
                                     (x * scale, y * scale, scale, scale))
        for enemy in enemies:
            if enemy.alive:
                pygame.draw.circle(surf, (230, 70, 60),
                                   (int(enemy.x * scale), int(enemy.y * scale)), 2)
        px, py = int(player.x * scale), int(player.y * scale)
        pygame.draw.circle(surf, (90, 220, 90), (px, py), 3)
        tip = (px + int(math.cos(player.angle) * scale * 1.5),
               py + int(math.sin(player.angle) * scale * 1.5))
        pygame.draw.line(surf, (90, 220, 90), (px, py), tip, 1)
        screen.blit(surf, (10, 10))

    def _draw_hurt_flash(self, screen, player):
        """Voile rouge bref quand le joueur encaisse des dégâts."""
        if player.hurt_flash <= 0.0:
            return
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        alpha = int(120 * (player.hurt_flash / 0.35))
        overlay.fill((180, 20, 20, alpha))
        screen.blit(overlay, (0, 0))

    def draw_pause(self, screen):
        """Voile + texte de pause par-dessus la scène figée."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, (0, 0))
        title = self.big_font.render("PAUSE", True, (240, 240, 240))
        hint = self.font.render("Échap : reprendre    M : menu principal", True, (200, 200, 200))
        screen.blit(title, ((self.width - title.get_width()) // 2, self.height // 2 - 60))
        screen.blit(hint, ((self.width - hint.get_width()) // 2, self.height // 2 + 10))
