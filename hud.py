"""Interface en jeu (HUD).

Viseur, arme pixel-art vue à la première personne (balancement à la
marche, recul et éclair au tir), barre de vie, munitions, emplacements
d'armes (1..4), nom du niveau, messages temporaires (ramassages), minimap
et voile rouge de dégâts.
"""

import math
import random

import pygame

import assets
from weapons import WEAPON_ORDER


class HUD:
    def __init__(self, size):
        self.resize(size)
        self.kick = 0.0        # recul de l'arme (0 → 1)
        self.flash = 0.0       # éclair de bouche
        self.lower = 0.0       # abaissement de l'arme (rechargement, lissé)
        self.smoke = []        # volutes de fumée du canon [x, y, âge]
        self.sway_time = 0.0   # horloge du balancement
        self.message = ""
        self.message_timer = 0.0
        self.spread = 0.0      # écartement du viseur (tirs récents)
        self.hit_timer = 0.0   # marqueur de touche
        self.hit_kill = False
        self.damage_dirs = []  # [(angle_relatif, minuterie)] dégâts reçus
        self.announce_text = ""
        self.announce_timer = 0.0

    def resize(self, size):
        self.width, self.height = size
        self.font = pygame.font.Font(None, max(22, self.height // 24))
        self.big_font = pygame.font.Font(None, max(36, self.height // 12))
        # Voiles plein écran pré-remplis : blittés avec set_alpha (rapide)
        # au lieu de recréer une surface SRCALPHA à chaque frame.
        self._red_veil = pygame.Surface(size)
        self._red_veil.fill((180, 20, 20))
        self._dark_veil = pygame.Surface(size)
        self._dark_veil.fill((10, 0, 0))
        self._minimap_level = None

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

    def announce(self, text):
        """Grande annonce centrale (début de vague...)."""
        self.announce_text = text
        self.announce_timer = 2.2

    def update(self, dt, moving):
        self.kick = max(0.0, self.kick - dt * 8)
        self.flash = max(0.0, self.flash - dt)
        self.spread = max(0.0, self.spread - dt * 18)
        self.hit_timer = max(0.0, self.hit_timer - dt)
        self.message_timer = max(0.0, self.message_timer - dt)
        self.announce_timer = max(0.0, self.announce_timer - dt)
        for entry in self.damage_dirs:
            entry[1] -= dt
        self.damage_dirs = [e for e in self.damage_dirs if e[1] > 0]
        for puff in self.smoke:      # la fumée monte et dérive
            puff[1] -= dt * self.height * 0.14
            puff[0] += dt * self.width * 0.008
            puff[2] += dt
        self.smoke = [p for p in self.smoke if p[2] < 0.7]
        if moving:
            self.sway_time += dt

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def draw(self, screen, player, enemies, level, pickups=(), fps=None,
             survival=None, stats=None):
        self._draw_weapon(screen, player)
        self._draw_crosshair(screen)
        self._draw_hit_marker(screen)
        self._draw_damage_dirs(screen)
        self._draw_status(screen, player, enemies, survival, stats)
        self._draw_slots(screen, player)
        self._draw_level_label(screen, level)
        if survival is not None:
            self._draw_survival(screen, survival)
        self._draw_boss_bar(screen, enemies)
        self._draw_message(screen)
        self._draw_announce(screen)
        self._draw_minimap(screen, player, enemies, level, pickups)
        if fps is not None:
            self._draw_fps(screen, fps)
        self._draw_hurt_flash(screen, player)

    def _draw_weapon(self, screen, player):
        """Sprite pixel-art de l'arme courante, vu à la première personne.

        Balancement à la marche, recul au tir, abaissement lissé pendant le
        rechargement, fumée qui s'échappe du canon après les tirs.
        """
        sprite = assets.get("fp_" + player.weapon.spec.id)
        target_w = int(self.width * 0.34)
        target_h = int(target_w * sprite.get_height() / sprite.get_width())
        scaled = pygame.transform.scale(sprite, (target_w, target_h))

        sway_x = math.sin(self.sway_time * 7) * self.width * 0.008
        sway_y = abs(math.cos(self.sway_time * 7)) * self.height * 0.008
        # Abaissement interpolé : l'arme plonge et remonte en douceur.
        target_lower = self.height * 0.16 if player.weapon.reloading > 0.0 else 0.0
        self.lower += (target_lower - self.lower) * 0.16
        x = self.width // 2 - target_w // 2 + int(self.width * 0.07 + sway_x)
        y = (self.height - int(target_h * 0.86)
             + int(self.kick * self.height * 0.04 + sway_y + self.lower))
        tip = (x + target_w // 2, y + int(target_h * 0.04))

        # Volutes de fumée derrière l'arme.
        for px, py, age in self.smoke:
            fade = 1.0 - age / 0.7
            radius = int(self.height * (0.006 + age * 0.02))
            gray = int(120 + 60 * fade)
            pygame.draw.circle(screen, (gray, gray, gray), (int(px), int(py)),
                               radius, 1)

        screen.blit(scaled, (x, y))

        if self.flash > 0.0:
            # Éclair de bouche en étoile, taille légèrement aléatoire.
            big = self.height // 24 + random.randint(-2, 3)
            small = big * 0.45
            points = []
            spin = random.uniform(0, math.pi / 4)
            for i in range(8):
                ang = spin + i * math.pi / 4
                r = big if i % 2 == 0 else small
                points.append((tip[0] + math.cos(ang) * r,
                               tip[1] + math.sin(ang) * r))
            pygame.draw.polygon(screen, (255, 225, 110), points)
            pygame.draw.circle(screen, (255, 255, 215), tip, int(small * 0.8))
        elif self.kick > 0.4:
            # Juste après un tir : une volute de fumée naît au canon.
            self.smoke.append([tip[0] + random.uniform(-4, 4), tip[1], 0.0])

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
        """Flèches rouges autour du centre indiquant d'où viennent les tirs.

        Dessinées directement (pas de voile plein écran) : le fondu se fait
        par la couleur et la taille du triangle.
        """
        cx, cy = self.width // 2, self.height // 2
        radius = self.height * 0.17
        for rel, timer in self.damage_dirs:
            fade = min(1.0, timer * 2.2)
            color = (int(90 + 130 * fade), int(20 + 25 * fade), 30)
            size = 8 + 7 * fade
            # rel = 0 -> devant (haut de l'écran) ; croît vers la droite.
            px = cx + math.sin(rel) * radius
            py = cy - math.cos(rel) * radius
            out_x, out_y = math.sin(rel), -math.cos(rel)
            side_x, side_y = math.cos(rel), math.sin(rel)
            pygame.draw.polygon(screen, color, [
                (px + out_x * (size + 5), py + out_y * (size + 5)),
                (px + side_x * size * 0.65, py + side_y * size * 0.65),
                (px - side_x * size * 0.65, py - side_y * size * 0.65),
            ])

    def _draw_status(self, screen, player, enemies, survival=None, stats=None):
        """Barre de vie + arme/munitions + ennemis restants + éliminations."""
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

        if survival is not None:
            remaining = survival["remaining"]   # inclut la file d'attente
        else:
            remaining = sum(1 for e in enemies if e.alive)
        info = self.font.render(f"Ennemis restants : {remaining}", True, (220, 220, 160))
        screen.blit(info, (self.width - info.get_width() - margin, margin))
        if stats is not None:
            kills = self.font.render(f"Éliminations : {stats['kills']}",
                                     True, (200, 200, 200))
            screen.blit(kills, (self.width - kills.get_width() - margin,
                                margin + info.get_height() + 2))

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
        if level.is_survival:
            text = level.name       # "Le Déferlement" (les vagues suivent)
        else:
            text = f"Niveau {level.index + 1} — {level.name}"
        label = self.font.render(text, True, (235, 235, 235))
        screen.blit(label, ((self.width - label.get_width()) // 2, 10))

    def _draw_survival(self, screen, info):
        """Sous le titre : vague courante, et compte à rebours (répit ou
        submersion imminente)."""
        if info["wave"] <= 0:
            text = f"La horde arrive dans {math.ceil(info['next_in'])} s..."
            color = (240, 200, 160)
        elif info["intermission"]:
            text = (f"Vague {info['wave']} / {info['final']} nettoyée — "
                    f"suivante dans {math.ceil(info['next_in'])} s")
            color = (170, 230, 170)
        else:
            text = (f"Vague {info['wave']} / {info['final']}   "
                    f"Prochaine vague : {math.ceil(info['next_in'])} s")
            # le compte à rebours vire au rouge quand la submersion menace
            color = (230, 90, 70) if info["next_in"] < 15 else (220, 220, 160)
        label = self.font.render(text, True, color)
        screen.blit(label, ((self.width - label.get_width()) // 2, 36))

    def _draw_announce(self, screen):
        """Grande annonce centrale fugace ("VAGUE 12")."""
        if self.announce_timer <= 0.0:
            return
        alpha = min(1.0, self.announce_timer / 0.6)
        surf = self.big_font.render(self.announce_text, True, (255, 170, 60))
        surf.set_alpha(int(255 * alpha))
        screen.blit(surf, ((self.width - surf.get_width()) // 2,
                           self.height // 3 - surf.get_height() // 2))

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
        """Petite carte en haut à gauche (murs, joueur, ennemis, objets).

        Le fond (murs) est statique : rendu une seule fois puis copié.
        """
        if getattr(self, "_minimap_level", None) is not level:
            self._minimap_level = level
            base = pygame.Surface((level.width * scale, level.height * scale),
                                  pygame.SRCALPHA)
            base.fill((10, 10, 14, 150))
            for y in range(level.height):
                for x in range(level.width):
                    if level.grid[y][x] != ".":
                        pygame.draw.rect(base, (170, 170, 180, 200),
                                         (x * scale, y * scale, scale, scale))
                    elif (x, y) in level.prop_tiles:   # décors (voitures...)
                        pygame.draw.rect(base, (105, 105, 115, 170),
                                         (x * scale, y * scale, scale, scale))
            self._minimap_base = base
        surf = self._minimap_base.copy()
        for pickup in pickups:
            # Les packs de vie cachés ne trahissent pas leur position ici.
            if not pickup.taken and not pickup.hidden:
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
        self._red_veil.set_alpha(int(120 * (player.hurt_flash / 0.35)))
        screen.blit(self._red_veil, (0, 0))

    def draw_dead_overlay(self, screen):
        """Voile sombre pendant l'attente de réapparition (coop LAN)."""
        self._red_veil.set_alpha(110)
        screen.blit(self._red_veil, (0, 0))
        title = self.big_font.render("VOUS ÊTES À TERRE", True, (240, 200, 190))
        hint = self.font.render("Réapparition dans quelques secondes...",
                                True, (220, 200, 200))
        screen.blit(title, ((self.width - title.get_width()) // 2,
                            self.height // 2 - 60))
        screen.blit(hint, ((self.width - hint.get_width()) // 2,
                           self.height // 2 + 10))

    def draw_pause(self, screen):
        """Voile + texte de pause par-dessus la scène figée."""
        self._dark_veil.set_alpha(150)
        screen.blit(self._dark_veil, (0, 0))
        title = self.big_font.render("PAUSE", True, (240, 240, 240))
        hint = self.font.render("Échap : reprendre    M : menu principal", True, (200, 200, 200))
        screen.blit(title, ((self.width - title.get_width()) // 2, self.height // 2 - 60))
        screen.blit(hint, ((self.width - hint.get_width()) // 2, self.height // 2 + 10))
