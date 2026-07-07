"""Interface en jeu (HUD).

Viseur, arme pixel-art vue à la première personne (balancement à la
marche, recul et éclair au tir), barre de vie, munitions, emplacements
d'armes (1..4), nom du niveau, messages temporaires (ramassages), minimap
et voile rouge de dégâts.
"""

import math

import pygame

import assets
from weapons import WEAPON_ORDER


class HUD:
    def __init__(self, size):
        self.resize(size)
        self.kick = 0.0        # recul de l'arme (0 → 1)
        self.flash = 0.0       # éclair de bouche
        self.sway_time = 0.0   # horloge du balancement
        self.message = ""
        self.message_timer = 0.0
        self.spread = 0.0      # écartement du viseur (tirs récents)
        self.hit_timer = 0.0   # marqueur de touche
        self.hit_kill = False
        self.damage_dirs = []  # [(angle_relatif, minuterie)] dégâts reçus

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
        self.spread = min(10.0, self.spread + 3.5)

    def on_enemy_hit(self, killed):
        """Marqueur de touche au centre du viseur (rouge si l'ennemi meurt)."""
        self.hit_timer = 0.18
        self.hit_kill = killed

    def on_player_hit(self, rel_angle):
        """Mémorise la direction d'où viennent les dégâts (indicateur)."""
        self.damage_dirs.append([rel_angle, 0.8])

    def show_message(self, text):
        self.message = text
        self.message_timer = 2.2

    def update(self, dt, moving):
        self.kick = max(0.0, self.kick - dt * 8)
        self.flash = max(0.0, self.flash - dt)
        self.spread = max(0.0, self.spread - dt * 18)
        self.hit_timer = max(0.0, self.hit_timer - dt)
        self.message_timer = max(0.0, self.message_timer - dt)
        for entry in self.damage_dirs:
            entry[1] -= dt
        self.damage_dirs = [e for e in self.damage_dirs if e[1] > 0]
        if moving:
            self.sway_time += dt

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def draw(self, screen, player, enemies, level, pickups=(), fps=None):
        self._draw_weapon(screen, player)
        self._draw_crosshair(screen)
        self._draw_hit_marker(screen)
        self._draw_damage_dirs(screen)
        self._draw_status(screen, player, enemies)
        self._draw_slots(screen, player)
        self._draw_level_label(screen, level)
        self._draw_boss_bar(screen, enemies)
        self._draw_message(screen)
        self._draw_minimap(screen, player, enemies, level, pickups)
        if fps is not None:
            self._draw_fps(screen, fps)
        self._draw_hurt_flash(screen, player)

    def _draw_weapon(self, screen, player):
        """Sprite pixel-art de l'arme courante, vu à la première personne."""
        sprite = assets.get("fp_" + player.weapon.spec.id)
        target_w = int(self.width * 0.34)
        target_h = int(target_w * sprite.get_height() / sprite.get_width())
        scaled = pygame.transform.scale(sprite, (target_w, target_h))

        sway_x = math.sin(self.sway_time * 7) * self.width * 0.008
        sway_y = abs(math.cos(self.sway_time * 7)) * self.height * 0.008
        # Pendant le rechargement, l'arme est abaissée.
        lowered = self.height * 0.14 if player.weapon.reloading > 0.0 else 0
        x = self.width // 2 - target_w // 2 + int(self.width * 0.07 + sway_x)
        y = (self.height - int(target_h * 0.86)
             + int(self.kick * self.height * 0.04 + sway_y + lowered))
        screen.blit(scaled, (x, y))

        if self.flash > 0.0:
            # Éclair de bouche au sommet du canon.
            tip = (x + target_w // 2, y + int(target_h * 0.04))
            pygame.draw.circle(screen, (255, 230, 120), tip, self.height // 26)
            pygame.draw.circle(screen, (255, 255, 210), tip, self.height // 52)

    def _draw_crosshair(self, screen):
        """Viseur dynamique : s'écarte quand on tire (dispersion)."""
        cx, cy = self.width // 2, self.height // 2
        gap = 5 + int(self.spread)
        size = gap + 6
        color = (230, 230, 230)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(screen, color,
                             (cx + dx * gap, cy + dy * gap),
                             (cx + dx * size, cy + dy * size), 2)

    def _draw_hit_marker(self, screen):
        """Croix diagonale brève quand une balle touche un ennemi."""
        if self.hit_timer <= 0.0:
            return
        cx, cy = self.width // 2, self.height // 2
        color = (255, 70, 60) if self.hit_kill else (255, 235, 160)
        for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
            pygame.draw.line(screen, color,
                             (cx + dx * 7, cy + dy * 7),
                             (cx + dx * 14, cy + dy * 14), 3)

    def _draw_damage_dirs(self, screen):
        """Flèches rouges autour du centre indiquant d'où viennent les tirs."""
        if not self.damage_dirs:
            return
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        cx, cy = self.width // 2, self.height // 2
        radius = self.height * 0.17
        for rel, timer in self.damage_dirs:
            alpha = max(0, min(255, int(300 * timer)))
            # rel = 0 -> devant (haut de l'écran) ; croît vers la droite.
            px = cx + math.sin(rel) * radius
            py = cy - math.cos(rel) * radius
            # petit triangle pointant vers l'extérieur
            out_x, out_y = math.sin(rel), -math.cos(rel)
            side_x, side_y = math.cos(rel), math.sin(rel)
            points = [
                (px + out_x * 14, py + out_y * 14),
                (px + side_x * 9, py + side_y * 9),
                (px - side_x * 9, py - side_y * 9),
            ]
            pygame.draw.polygon(overlay, (215, 40, 35, alpha), points)
        screen.blit(overlay, (0, 0))

    def _draw_status(self, screen, player, enemies):
        """Barre de vie + arme/munitions + compteur d'ennemis restants."""
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
            ammo_str = f"{weapon.ammo} / {weapon.spec.magazine_size}"
        ammo_text = self.big_font.render(ammo_str, True, (235, 235, 235))
        name_text = self.font.render(weapon.display_name, True, (220, 220, 160))
        ax = self.width - ammo_text.get_width() - margin
        ay = self.height - ammo_text.get_height() - margin
        screen.blit(ammo_text, (ax, ay))
        screen.blit(name_text, (self.width - name_text.get_width() - margin,
                                ay - name_text.get_height() - 2))

        remaining = sum(1 for e in enemies if e.alive)
        info = self.font.render(f"Ennemis restants : {remaining}", True, (220, 220, 160))
        screen.blit(info, (self.width - info.get_width() - margin, margin))

    def _draw_slots(self, screen, player, box=44):
        """Emplacements d'armes (touches 1..4), l'arme active surlignée."""
        owned = {WEAPON_ORDER.index(w.spec.id): w for w in player.weapons}
        total_w = len(WEAPON_ORDER) * (box + 6)
        x0 = self.width // 2 - total_w // 2
        y = self.height - box - 8
        for slot in range(len(WEAPON_ORDER)):
            x = x0 + slot * (box + 6)
            rect = pygame.Rect(x, y, box, box)
            weapon = owned.get(slot)
            active = weapon is not None and weapon is player.weapon
            bg = (50, 50, 58, 210) if active else (22, 22, 26, 150)
            surf = pygame.Surface((box, box), pygame.SRCALPHA)
            surf.fill(bg)
            screen.blit(surf, rect)
            border = (255, 210, 90) if active else (110, 110, 120)
            pygame.draw.rect(screen, border, rect, 2)
            num = self.font.render(str(slot + 1), True, border)
            screen.blit(num, (x + 4, y + 2))
            if weapon is not None:
                icon = pygame.transform.scale(
                    assets.get("pickup_" + weapon.spec.id), (box - 10, box - 10))
                screen.blit(icon, (x + 5, y + 5))

    def _draw_level_label(self, screen, level):
        label = self.font.render(
            f"Niveau {level.index + 1} — {level.name}", True, (235, 235, 235))
        screen.blit(label, ((self.width - label.get_width()) // 2, 10))

    def _draw_boss_bar(self, screen, enemies):
        """Grande barre de vie du boss en haut de l'écran (s'il est en vie)."""
        boss = next((e for e in enemies if e.IS_BOSS and e.alive), None)
        if boss is None:
            return
        bar_w = int(self.width * 0.44)
        bar_h = 14
        x = (self.width - bar_w) // 2
        y = 40
        frac = boss.health / boss.max_health
        pygame.draw.rect(screen, (30, 12, 12), (x, y, bar_w, bar_h))
        pygame.draw.rect(screen, (235, 120, 40), (x, y, int(bar_w * frac), bar_h))
        pygame.draw.rect(screen, (240, 200, 160), (x, y, bar_w, bar_h), 1)
        name = self.font.render("LE COLOSSE", True, (240, 200, 160))
        screen.blit(name, ((self.width - name.get_width()) // 2,
                           y + bar_h + 2))

    def _draw_fps(self, screen, fps):
        text = self.font.render(f"{fps:.0f} FPS", True, (160, 230, 160))
        screen.blit(text, (12, self.height - text.get_height() * 3 - 40))

    def _draw_message(self, screen):
        """Message temporaire (arme ramassée...) au-dessus du viseur."""
        if self.message_timer <= 0.0:
            return
        surf = self.font.render(self.message, True, (255, 220, 120))
        screen.blit(surf, ((self.width - surf.get_width()) // 2,
                           self.height // 2 - self.height // 8))

    def _draw_minimap(self, screen, player, enemies, level, pickups=(), scale=6):
        """Petite carte en haut à gauche (murs, joueur, ennemis, objets)."""
        surf = pygame.Surface((level.width * scale, level.height * scale), pygame.SRCALPHA)
        surf.fill((10, 10, 14, 150))
        for y in range(level.height):
            for x in range(level.width):
                if level.grid[y][x] != ".":
                    pygame.draw.rect(surf, (170, 170, 180, 200),
                                     (x * scale, y * scale, scale, scale))
        for pickup in pickups:
            if not pickup.taken:
                pygame.draw.circle(surf, (240, 210, 90),
                                   (int(pickup.x * scale), int(pickup.y * scale)), 2)
        for enemy in enemies:
            if enemy.alive:
                radius = 3 if enemy.IS_BOSS else 2
                pygame.draw.circle(surf, (230, 70, 60),
                                   (int(enemy.x * scale), int(enemy.y * scale)), radius)
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
