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

HUD_GREEN = (82, 220, 153)
HUD_AMBER = (238, 166, 75)
HUD_TEXT = (220, 231, 230)
HUD_DIM = (115, 139, 143)


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
        self.time_acc = 0.0          # horloge continue (clignotements)
        self._scope_size = None      # cache de la vignette de lunette
        self._scope_vignette = None

    def resize(self, size):
        self.width, self.height = size
        self.font = pygame.font.SysFont(
            "consolas,dejavusansmono,couriernew",
            max(18, self.height // 28), bold=True,
        )
        self.big_font = pygame.font.SysFont(
            "consolas,dejavusansmono,couriernew",
            max(32, self.height // 13), bold=True,
        )
        self.death_font = pygame.font.SysFont(
            "impact,arialblack,dejavusanscondensed",
            max(60, self.height // 6), bold=True,
        )
        # Voiles plein écran pré-remplis : blittés avec set_alpha (rapide)
        # au lieu de recréer une surface SRCALPHA à chaque frame.
        self._red_veil = pygame.Surface(size)
        self._red_veil.fill((180, 20, 20))
        self._dark_veil = pygame.Surface(size)
        self._dark_veil.fill((10, 0, 0))
        self._flash_veil = pygame.Surface(size)   # voile chaud du tir
        self._flash_veil.fill((255, 226, 150))
        # Vignette du bouclier temporaire : bordure bleutée qui s'estompe
        # vers le centre (construite une fois, modulée par set_alpha ensuite).
        w, h = size
        self._shield_veil = pygame.Surface(size, pygame.SRCALPHA)
        border = max(24, h // 10)
        for i in range(border):
            alpha = int(140 * (1 - i / border))
            pygame.draw.rect(self._shield_veil, (90, 175, 255, alpha),
                             (i, i, w - 2 * i, h - 2 * i), 2)
        self._minimap_level = None
        self._slot_cache = {}        # fonds d'emplacements d'armes mémoïsés
        self._panel_cache = {}       # plaques translucides du HUD

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
        self.time_acc += dt
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
        if self.flash > 0.0 and player.ads < 0.5:
            # Brève lueur chaude du coup de feu qui éclaire la scène
            # (désactivée en visée à la lunette, où elle gênerait).
            self._flash_veil.set_alpha(int(42 * (self.flash / 0.06)))
            screen.blit(self._flash_veil, (0, 0))
        self._draw_weapon(screen, player)
        if player.ads > 0.55:
            self._draw_scope(screen, player)     # lunette de visée
        else:
            self._draw_crosshair(screen)
        self._draw_hit_marker(screen)
        self._draw_damage_dirs(screen)
        if player.shield > 0.0:
            self._draw_shield(screen, player)
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

    def _panel(self, size, accent=HUD_GREEN):
        """Plaque tactique translucide, construite une fois par variante."""
        key = (size, accent)
        if key not in self._panel_cache:
            surf = pygame.Surface(size, pygame.SRCALPHA)
            rect = surf.get_rect()
            pygame.draw.rect(surf, (5, 11, 16, 210), rect, border_radius=4)
            pygame.draw.rect(surf, (71, 92, 96, 205), rect, 1,
                             border_radius=4)
            pygame.draw.line(surf, (*accent, 230), (1, 1),
                             (rect.width - 2, 1), 2)
            pygame.draw.rect(surf, (*accent, 215),
                             (0, 0, 3, rect.height), border_radius=2)
            self._panel_cache[key] = surf
        return self._panel_cache[key]

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
        # Abaissement interpolé : l'arme plonge au rechargement... et
        # descend hors champ quand on met en joue (remplacée par la lunette).
        target_lower = self.height * 0.16 if player.weapon.reloading > 0.0 else 0.0
        target_lower += player.ads * self.height * 0.5
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

    def _draw_scope(self, screen, player):
        """Viseur de lunette : vignette noire circulaire, croix fine et
        graduations — dessiné en visée (clic droit)."""
        w, h = self.width, self.height
        cx, cy = w // 2, h // 2
        radius = int(h * 0.42)
        # Vignette : coins noircis autour du cercle de visée.
        if self._scope_size != (w, h):
            self._scope_size = (w, h)
            vig = pygame.Surface((w, h), pygame.SRCALPHA)
            vig.fill((0, 0, 0, 255))
            pygame.draw.circle(vig, (0, 0, 0, 0), (cx, cy), radius)
            pygame.draw.circle(vig, (0, 0, 0, 130), (cx, cy), radius, h // 40)
            self._scope_vignette = vig
        screen.blit(self._scope_vignette, (0, 0))
        pygame.draw.circle(screen, (12, 14, 12), (cx, cy), radius, 2)
        # Réticule : croix fine avec rupture centrale + graduations.
        col = (20, 24, 20)
        pygame.draw.line(screen, col, (cx - radius, cy), (cx - 8, cy), 1)
        pygame.draw.line(screen, col, (cx + 8, cy), (cx + radius, cy), 1)
        pygame.draw.line(screen, col, (cx, cy - radius), (cx, cy - 8), 2)
        pygame.draw.line(screen, col, (cx, cy + 8), (cx, cy + radius), 1)
        for i in range(1, 6):                    # graduations verticales
            gy = cy + i * radius // 6
            pygame.draw.line(screen, col, (cx - 4, gy), (cx + 4, gy), 1)
        pygame.draw.circle(screen, (200, 40, 40), (cx, cy), 1)

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

    def _draw_shield(self, screen, player):
        """Bouclier temporaire à l'arrivée sur un niveau : vignette bleutée
        pulsée, qui clignote dans la dernière seconde avant expiration."""
        remaining = player.shield
        pulse = 0.7 + 0.3 * math.sin(self.time_acc * 6.0)
        if remaining < 1.0 and int(self.time_acc * 8) % 2 == 0:
            pulse *= 0.25   # clignote pour prévenir de la fin imminente
        self._shield_veil.set_alpha(int(255 * pulse))
        screen.blit(self._shield_veil, (0, 0))
        text = self.font.render(f"BOUCLIER  {remaining:.1f} s",
                                True, (150, 210, 255))
        screen.blit(text, (14, self.height - 92 - text.get_height() - 4))

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
        margin = 12
        panel_h = 78
        left_w = max(230, int(self.width * 0.23))
        right_w = max(225, int(self.width * 0.21))
        panel_y = self.height - panel_h - margin
        left_rect = pygame.Rect(margin, panel_y, left_w, panel_h)
        right_rect = pygame.Rect(self.width - margin - right_w, panel_y,
                                 right_w, panel_h)
        screen.blit(self._panel(left_rect.size), left_rect)
        screen.blit(self._panel(right_rect.size, HUD_AMBER), right_rect)

        frac = max(0.0, player.health / player.max_health)
        health_color = HUD_GREEN if frac > 0.35 else (230, 75, 67)
        label = self.font.render("INTÉGRITÉ", True, HUD_DIM)
        hp_text = self.font.render(f"{player.health:03d} PV", True, HUD_TEXT)
        screen.blit(label, (left_rect.x + 14, left_rect.y + 10))
        screen.blit(hp_text, (left_rect.right - hp_text.get_width() - 12,
                              left_rect.y + 10))
        segments = 10
        gap = 3
        bar_x = left_rect.x + 14
        bar_y = left_rect.bottom - 24
        bar_w = left_rect.width - 28
        seg_w = (bar_w - gap * (segments - 1)) // segments
        filled = math.ceil(frac * segments)
        for idx in range(segments):
            rect = pygame.Rect(bar_x + idx * (seg_w + gap), bar_y,
                               seg_w, 10)
            pygame.draw.rect(screen,
                             health_color if idx < filled else (28, 43, 47),
                             rect)
            pygame.draw.rect(screen, (78, 98, 101), rect, 1)

        weapon = player.weapon
        low = weapon.ammo <= max(1, weapon.spec.magazine_size // 4)
        if weapon.reloading > 0.0:
            ammo_str, ammo_col = "RECHARGEMENT...", (235, 200, 120)
        elif weapon.ammo == 0:
            # chargeur vide : invite au rechargement, clignotante.
            blink = int(self.time_acc * 6) % 2 == 0
            ammo_str = "RECHARGEZ [R]"
            ammo_col = (235, 70, 60) if blink else (150, 40, 34)
        else:
            ammo_str = f"{weapon.ammo} / {weapon.spec.magazine_size}"
            ammo_col = (235, 100, 78) if low else HUD_TEXT
        ammo_text = self.big_font.render(ammo_str, True, ammo_col)
        name_text = self.font.render(weapon.display_name.upper(), True, HUD_AMBER)
        screen.blit(name_text, (right_rect.x + 12, right_rect.y + 8))
        screen.blit(ammo_text,
                    (right_rect.right - ammo_text.get_width() - 12,
                     right_rect.bottom - ammo_text.get_height() - 5))

        if survival is not None:
            remaining = survival["remaining"]   # inclut la file d'attente
        else:
            remaining = sum(1 for e in enemies if e.alive)
        info = self.font.render(f"CONTACTS  {remaining:02d}", True, HUD_AMBER)
        kill_count = stats["kills"] if stats is not None else 0
        kills = self.font.render(f"NEUTRALISÉS  {kill_count:02d}",
                                 True, HUD_TEXT)
        info_w = max(info.get_width(), kills.get_width()) + 26
        info_h = info.get_height() + kills.get_height() + 17
        info_rect = pygame.Rect(self.width - margin - info_w, margin,
                                info_w, info_h)
        screen.blit(self._panel(info_rect.size, HUD_AMBER), info_rect)
        screen.blit(info, (info_rect.x + 12, info_rect.y + 8))
        if stats is not None:
            screen.blit(kills, (info_rect.x + 12,
                                info_rect.y + 8 + info.get_height()))

    def _draw_slots(self, screen, player, box=44):
        """Emplacements d'armes (touches 1..4), l'arme active surlignée."""
        owned = {WEAPON_ORDER.index(w.spec.id): w for w in player.weapons}
        total_w = len(WEAPON_ORDER) * (box + 6)
        x0 = self.width // 2 - total_w // 2
        y = self.height - box - 8
        # Fonds semi-transparents mémoïsés (actif / inactif) : évite de
        # recréer 4 surfaces SRCALPHA à chaque frame.
        if box not in self._slot_cache:
            variants = {}
            for key, bg in (("on", (20, 54, 48, 230)),
                            ("off", (7, 14, 19, 205))):
                s = pygame.Surface((box, box), pygame.SRCALPHA)
                s.fill(bg)
                variants[key] = s
            self._slot_cache[box] = variants
        bgs = self._slot_cache[box]
        for slot in range(len(WEAPON_ORDER)):
            x = x0 + slot * (box + 6)
            rect = pygame.Rect(x, y, box, box)
            weapon = owned.get(slot)
            active = weapon is not None and weapon is player.weapon
            screen.blit(bgs["on"] if active else bgs["off"], rect)
            border = HUD_GREEN if active else (72, 91, 95)
            pygame.draw.rect(screen, border, rect, 2)
            if active:
                pygame.draw.line(screen, HUD_AMBER,
                                 (rect.x + 3, rect.y + 3),
                                 (rect.right - 4, rect.y + 3), 2)
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
        label = self.font.render(text.upper(), True, HUD_TEXT)
        plate = self._panel((label.get_width() + 28, label.get_height() + 12))
        x = (self.width - plate.get_width()) // 2
        screen.blit(plate, (x, 8))
        screen.blit(label, (x + 14, 14))

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
        screen.blit(label, ((self.width - label.get_width()) // 2, 50))

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
        bar_h = 12
        x = (self.width - bar_w) // 2
        y = 72
        frac = boss.health / boss.max_health
        panel = self._panel((bar_w + 28, 52), HUD_AMBER)
        screen.blit(panel, (x - 14, y - 25))
        name = self.font.render("LE COLOSSE", True, HUD_AMBER)
        screen.blit(name, ((self.width - name.get_width()) // 2, y - 21))
        pygame.draw.rect(screen, (40, 18, 17), (x, y, bar_w, bar_h))
        pygame.draw.rect(screen, (226, 91, 45),
                         (x, y, int(bar_w * frac), bar_h))
        for marker in range(1, 10):
            mx = x + marker * bar_w // 10
            pygame.draw.line(screen, (65, 35, 30),
                             (mx, y), (mx, y + bar_h - 1), 1)
        pygame.draw.rect(screen, (211, 151, 92),
                         (x, y, bar_w, bar_h), 1)

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
            base.fill((10, 10, 14, 235))   # opaque : le soleil ne transparaît pas
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
        frame = pygame.Rect(8, 8, surf.get_width() + 4, surf.get_height() + 4)
        pygame.draw.rect(screen, (4, 10, 15), frame)
        pygame.draw.rect(screen, (92, 116, 119), frame, 1)
        pygame.draw.line(screen, HUD_GREEN,
                         (frame.x + 1, frame.y + 1),
                         (frame.right - 2, frame.y + 1), 2)
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

    def draw_death_screen(self, screen, t):
        """Écran de mort cinématique façon Dark Souls : la scène (déjà
        basculée au sol par la caméra de mort) s'assombrit progressivement,
        puis « VOUS ÊTES MORT » apparaît en lettres rouges espacées.

        `t` : temps écoulé depuis la mort (s)."""
        # Assombrissement progressif de toute la scène.
        darkness = min(0.78, t / 1.6 * 0.78)
        self._dark_veil.set_alpha(int(255 * darkness))
        screen.blit(self._dark_veil, (0, 0))

        # « VOUS ÊTES MORT » : fondu lent après une courte pause.
        if t <= 0.7:
            return
        alpha = min(1.0, (t - 0.7) / 1.3)
        cy = self.height // 2
        # Bandeau sombre horizontal derrière le texte (contraste, façon DS).
        band_h = self.death_font.get_height() + self.height // 12
        band = pygame.Surface((self.width, band_h), pygame.SRCALPHA)
        band.fill((0, 0, 0, int(160 * alpha)))
        screen.blit(band, (0, cy - band_h // 2))
        # Filet clair en haut et en bas du bandeau.
        line_a = int(120 * alpha)
        line = pygame.Surface((self.width, 2), pygame.SRCALPHA)
        line.fill((150, 30, 30, line_a))
        screen.blit(line, (0, cy - band_h // 2))
        screen.blit(line, (0, cy + band_h // 2 - 2))
        # Texte espacé (letter-spacing) centré.
        self._blit_spaced(screen, self.death_font, "VOUS ÊTES MORT",
                          (150, 22, 26), cy, alpha,
                          spacing=self.death_font.get_height() // 5)

    def _blit_spaced(self, screen, font, text, color, cy, alpha, spacing):
        """Rend `text` centré horizontalement avec un espacement ajouté
        entre les lettres, appliqué avec un fondu (`alpha` 0..1)."""
        glyphs = [font.render(ch, True, color) for ch in text]
        total = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
        x = (self.width - total) // 2
        for g in glyphs:
            g.set_alpha(int(255 * alpha))
            screen.blit(g, (x, cy - g.get_height() // 2))
            x += g.get_width() + spacing

    def draw_pause(self, screen):
        """Voile + texte de pause par-dessus la scène figée."""
        self._dark_veil.set_alpha(150)
        screen.blit(self._dark_veil, (0, 0))
        title = self.big_font.render("PAUSE", True, (240, 240, 240))
        hint = self.font.render("Échap : reprendre    M : menu principal", True, (200, 200, 200))
        screen.blit(title, ((self.width - title.get_width()) // 2, self.height // 2 - 60))
        screen.blit(hint, ((self.width - hint.get_width()) // 2, self.height // 2 + 10))
