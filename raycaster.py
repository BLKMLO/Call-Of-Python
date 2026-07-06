"""Moteur de rendu pseudo-3D par raycasting (façon Wolfenstein 3D).

Principe : pour chaque colonne de l'écran, on lance un rayon depuis le
joueur ; la distance au premier mur touché donne la hauteur de la colonne
de mur à dessiner. Un z-buffer (une profondeur par colonne) permet ensuite
de dessiner les ennemis (sprites "billboard") correctement masqués par
les murs.

Aucune texture externe n'est utilisée : les murs sont colorés par type de
case avec un ombrage selon la distance et l'orientation.
"""

import math

import pygame

FOV = math.radians(70)        # champ de vision horizontal
HALF_FOV = FOV / 2
MAX_DEPTH = 30                # portée maximale des rayons (en cases)
COLUMN_WIDTH = 2              # largeur en pixels d'une colonne de rendu

# Couleur de base de chaque type de mur.
WALL_COLORS = {
    "1": (130, 130, 138),   # béton gris
    "2": (150, 82, 60),     # brique rouge
    "3": (70, 95, 140),     # métal bleu
}


def cast_ray(level, ox, oy, angle, max_depth=MAX_DEPTH):
    """Lance un rayon depuis (ox, oy) et retourne (profondeur, type_de_mur, vertical).

    `vertical` indique si le mur touché est une face verticale de la grille
    (utilisé pour ombrer différemment les deux orientations).
    Méthode classique des intersections avec les lignes horizontales et
    verticales de la grille.
    """
    sin_a = math.sin(angle) or 1e-8
    cos_a = math.cos(angle) or 1e-8
    map_x, map_y = int(ox), int(oy)

    # --- intersections avec les lignes verticales de la grille ---
    if cos_a > 0:
        x_v, dx = map_x + 1.0, 1
    else:
        x_v, dx = map_x - 1e-6, -1
    depth_v = (x_v - ox) / cos_a
    y_v = oy + depth_v * sin_a
    delta_v = dx / cos_a
    dy_v = delta_v * sin_a
    tile_v = "1"
    for _ in range(max_depth):
        tile_v = level.tile(x_v, y_v)
        if tile_v != ".":
            break
        x_v += dx
        y_v += dy_v
        depth_v += delta_v

    # --- intersections avec les lignes horizontales de la grille ---
    if sin_a > 0:
        y_h, dy = map_y + 1.0, 1
    else:
        y_h, dy = map_y - 1e-6, -1
    depth_h = (y_h - oy) / sin_a
    x_h = ox + depth_h * cos_a
    delta_h = dy / sin_a
    dx_h = delta_h * cos_a
    tile_h = "1"
    for _ in range(max_depth):
        tile_h = level.tile(x_h, y_h)
        if tile_h != ".":
            break
        x_h += dx_h
        y_h += dy
        depth_h += delta_h

    # On garde l'intersection la plus proche.
    if depth_v < depth_h:
        return depth_v, tile_v, True
    return depth_h, tile_h, False


def has_line_of_sight(level, x0, y0, x1, y1):
    """Vrai si aucun mur ne bloque le segment entre deux points."""
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 1e-6:
        return True
    angle = math.atan2(y1 - y0, x1 - x0)
    depth, _, _ = cast_ray(level, x0, y0, angle)
    return depth > dist - 0.05


class Raycaster:
    """Rendu du monde : ciel/sol, murs, puis sprites des ennemis."""

    def __init__(self, size):
        self.resize(size)

    def resize(self, size):
        """(Re)calcule tout ce qui dépend de la résolution."""
        self.width, self.height = size
        self.num_rays = self.width // COLUMN_WIDTH
        self.delta_angle = FOV / self.num_rays
        self.screen_dist = (self.width / 2) / math.tan(HALF_FOV)
        self.z_buffer = [MAX_DEPTH] * self.num_rays
        self._build_background()

    def _build_background(self):
        """Pré-calcule un dégradé ciel/sol (dessiné avant les murs)."""
        self.background = pygame.Surface((self.width, self.height))
        half = self.height // 2
        for y in range(half):
            t = y / half  # 0 en haut → 1 à l'horizon
            color = (int(28 + 22 * t), int(30 + 24 * t), int(46 + 30 * t))
            pygame.draw.line(self.background, color, (0, y), (self.width, y))
        for y in range(half, self.height):
            t = (y - half) / max(1, self.height - half)  # 0 à l'horizon → 1 en bas
            color = (int(38 + 34 * t), int(36 + 30 * t), int(34 + 26 * t))
            pygame.draw.line(self.background, color, (0, y), (self.width, y))

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def render(self, screen, player, level, enemies):
        screen.blit(self.background, (0, 0))
        self._render_walls(screen, player, level)
        self._render_sprites(screen, player, enemies)

    def _render_walls(self, screen, player, level):
        angle = player.angle - HALF_FOV
        for ray in range(self.num_rays):
            depth, tile, vertical = cast_ray(level, player.x, player.y, angle)
            # Correction de l'effet "fisheye" : on projette la distance sur
            # l'axe de vision du joueur.
            depth *= math.cos(player.angle - angle)
            depth = max(depth, 1e-4)
            self.z_buffer[ray] = depth

            wall_height = min(int(self.screen_dist / depth), self.height * 4)
            top = (self.height - wall_height) // 2

            base = WALL_COLORS.get(tile, (120, 120, 120))
            # Ombrage : atténuation avec la distance + faces horizontales
            # légèrement plus sombres pour donner du relief.
            shade = 1.0 / (1.0 + depth * depth * 0.008)
            if not vertical:
                shade *= 0.72
            color = (int(base[0] * shade), int(base[1] * shade), int(base[2] * shade))

            pygame.draw.rect(
                screen, color,
                (ray * COLUMN_WIDTH, top, COLUMN_WIDTH, wall_height),
            )
            angle += self.delta_angle

    def _render_sprites(self, screen, player, enemies):
        """Dessine les ennemis en billboards, du plus loin au plus proche."""
        visibles = []
        for enemy in enemies:
            if not enemy.alive:
                continue
            dx, dy = enemy.x - player.x, enemy.y - player.y
            dist = math.hypot(dx, dy)
            if dist < 0.3 or dist > MAX_DEPTH:
                continue
            # Angle du sprite par rapport à l'axe de vision, ramené dans [-pi, pi].
            delta = math.atan2(dy, dx) - player.angle
            delta = (delta + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) > HALF_FOV + 0.4:
                continue  # hors du champ de vision (marge pour les bords)
            visibles.append((dist, delta, enemy))

        visibles.sort(key=lambda item: -item[0])  # du plus loin au plus proche

        for dist, delta, enemy in visibles:
            # Distance projetée (cohérente avec le z-buffer des murs).
            proj_dist = max(dist * math.cos(delta), 1e-4)
            proj = self.screen_dist / proj_dist

            sprite = enemy.current_sprite()
            ratio = sprite.get_width() / sprite.get_height()
            h = int(proj * enemy.SPRITE_HEIGHT)
            w = max(1, int(h * ratio))
            if h < 2 or h > self.height * 4:
                continue
            scaled = pygame.transform.scale(sprite, (w, h))

            screen_x = int((0.5 + delta / FOV) * self.width) - w // 2
            # Les pieds du sprite reposent sur la ligne de sol du mur à
            # cette distance (bas d'un mur de hauteur 1 = milieu + proj/2).
            bottom = self.height // 2 + int(proj * 0.5)
            top = bottom - h

            # Occlusion par les murs : on blitte le sprite colonne de rendu
            # par colonne de rendu, en comparant au z-buffer.
            first_ray = max(0, screen_x // COLUMN_WIDTH)
            last_ray = min(self.num_rays - 1, (screen_x + w) // COLUMN_WIDTH)
            drawn = False
            for ray in range(first_ray, last_ray + 1):
                if self.z_buffer[ray] < proj_dist:
                    continue  # un mur est devant cette tranche du sprite
                # Intersection [colonne de rendu] ∩ [largeur du sprite].
                strip_x = max(screen_x, ray * COLUMN_WIDTH)
                strip_end = min(screen_x + w, (ray + 1) * COLUMN_WIDTH)
                strip_w = strip_end - strip_x
                if strip_w <= 0:
                    continue
                strip = scaled.subsurface((strip_x - screen_x, 0, strip_w, h))
                screen.blit(strip, (strip_x, top))
                drawn = True

            if drawn:
                self._draw_health_bar(screen, enemy, screen_x, top, w)

    def _draw_health_bar(self, screen, enemy, x, top, w):
        """Barre de vie flottante au-dessus de l'ennemi."""
        if enemy.health >= enemy.max_health:
            return
        bar_h = max(2, w // 12)
        y = max(2, top - bar_h - 4)
        frac = max(0.0, enemy.health / enemy.max_health)
        pygame.draw.rect(screen, (40, 8, 8), (x, y, w, bar_h))
        pygame.draw.rect(screen, (200, 40, 40), (x, y, int(w * frac), bar_h))
