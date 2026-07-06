"""Moteur de rendu pseudo-3D par raycasting (façon Wolfenstein 3D).

Pour chaque colonne de l'écran, un rayon donne la distance au premier
mur : on y "plie" verticalement une colonne de la texture pixel-art du
mur (assets/wall_*.png), mise à l'échelle selon la distance. Un z-buffer
(une profondeur par colonne) masque ensuite correctement les sprites
(ennemis, objets) et les particules derrière les murs.

L'ombrage est pré-calculé : chaque texture existe en plusieurs variantes
assombries, choisies selon la distance et l'orientation de la face.
"""

import math

import pygame

import assets
from assets import TEX_SIZE

FOV = math.radians(70)        # champ de vision horizontal
HALF_FOV = FOV / 2
MAX_DEPTH = 30                # portée maximale des rayons (en cases)
COLUMN_WIDTH = 2              # largeur en pixels d'une colonne de rendu
SHADE_LEVELS = 10             # nombre de variantes d'ombrage par texture


def cast_ray(level, ox, oy, angle, max_depth=MAX_DEPTH):
    """Lance un rayon depuis (ox, oy).

    Retourne (profondeur, type_de_mur, vertical, offset) où `vertical`
    indique une face verticale de la grille et `offset` (0..1) la position
    du point d'impact le long du mur (colonne de texture à afficher).
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
        return depth_v, tile_v, True, y_v % 1.0
    return depth_h, tile_h, False, x_h % 1.0


def has_line_of_sight(level, x0, y0, x1, y1):
    """Vrai si aucun mur ne bloque le segment entre deux points."""
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 1e-6:
        return True
    angle = math.atan2(y1 - y0, x1 - x0)
    depth, _, _, _ = cast_ray(level, x0, y0, angle)
    return depth > dist - 0.05


class Raycaster:
    """Rendu du monde : ciel/sol thématisés, murs texturés, sprites, particules."""

    def __init__(self, size, level):
        self.width = self.height = 0
        self.level_config = level.config
        self.resize(size)
        self.set_level(level)

    def resize(self, size):
        """(Re)calcule tout ce qui dépend de la résolution."""
        self.width, self.height = size
        self.num_rays = self.width // COLUMN_WIDTH
        self.delta_angle = FOV / self.num_rays
        self.screen_dist = (self.width / 2) / math.tan(HALF_FOV)
        self.z_buffer = [MAX_DEPTH] * self.num_rays
        self._build_background()

    def set_level(self, level):
        """Prépare les textures ombrées du thème de ce niveau."""
        self.level_config = level.config
        self._build_background()
        # tex_cols[char][niveau_d_ombre][x] -> colonne de texture (1 px de large)
        self.tex_cols = {}
        for char, tex_name in self.level_config["theme"].items():
            texture = assets.get(tex_name)
            shades = []
            for i in range(SHADE_LEVELS):
                factor = 1.0 - i / (SHADE_LEVELS + 1)
                shaded = texture.copy()
                mult = int(255 * factor)
                shaded.fill((mult, mult, mult), special_flags=pygame.BLEND_MULT)
                shades.append([shaded.subsurface((x, 0, 1, TEX_SIZE))
                               for x in range(TEX_SIZE)])
            self.tex_cols[char] = shades

    def _build_background(self):
        """Pré-calcule le dégradé ciel/sol aux couleurs du niveau."""
        (sky_top, sky_bot) = self.level_config["sky"]
        (floor_top, floor_bot) = self.level_config["floor"]
        self.background = pygame.Surface((self.width, self.height))
        half = self.height // 2
        for y in range(half):
            t = y / max(1, half)
            color = [int(a + (b - a) * t) for a, b in zip(sky_top, sky_bot)]
            pygame.draw.line(self.background, color, (0, y), (self.width, y))
        for y in range(half, self.height):
            t = (y - half) / max(1, self.height - half)
            color = [int(a + (b - a) * t) for a, b in zip(floor_top, floor_bot)]
            pygame.draw.line(self.background, color, (0, y), (self.width, y))

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def render(self, screen, player, level, sprites, particles):
        """`sprites` : entités billboard (ennemis vivants, objets au sol)."""
        screen.blit(self.background, (0, 0))
        self._render_walls(screen, player, level)
        self._render_sprites(screen, player, sprites)
        self._render_particles(screen, player, particles)

    def _shade_index(self, depth, vertical):
        """Variante d'ombrage : plus loin = plus sombre ; faces horizontales
        légèrement plus sombres pour marquer les arêtes."""
        idx = int(depth * 0.55) + (0 if vertical else 2)
        return min(SHADE_LEVELS - 1, idx)

    def _render_walls(self, screen, player, level):
        angle = player.angle - HALF_FOV
        default_char = next(iter(self.tex_cols))
        for ray in range(self.num_rays):
            depth, tile, vertical, offset = cast_ray(level, player.x, player.y, angle)
            # Correction de l'effet "fisheye" : on projette la distance sur
            # l'axe de vision du joueur.
            depth *= math.cos(player.angle - angle)
            depth = max(depth, 0.02)
            self.z_buffer[ray] = depth

            wall_height = int(self.screen_dist / depth)
            shades = self.tex_cols.get(tile) or self.tex_cols[default_char]
            column = shades[self._shade_index(depth, vertical)][
                min(TEX_SIZE - 1, int(offset * TEX_SIZE))]

            if wall_height <= self.height:
                # Mur entier visible : la colonne de texture est étirée.
                scaled = pygame.transform.scale(column, (COLUMN_WIDTH, wall_height))
                screen.blit(scaled, (ray * COLUMN_WIDTH, (self.height - wall_height) // 2))
            else:
                # Mur plus haut que l'écran : on ne plie que la partie visible
                # de la texture (évite de créer des surfaces géantes).
                visible = TEX_SIZE * self.height / wall_height
                tex_y = (TEX_SIZE - visible) / 2
                sub = column.subsurface((0, int(tex_y), 1, max(1, int(visible))))
                scaled = pygame.transform.scale(sub, (COLUMN_WIDTH, self.height))
                screen.blit(scaled, (ray * COLUMN_WIDTH, 0))
            angle += self.delta_angle

    def _project(self, player, x, y):
        """Projection d'un point monde -> (distance projetée, delta d'angle).

        Retourne None si le point est hors du champ de vision (avec marge).
        """
        dx, dy = x - player.x, y - player.y
        dist = math.hypot(dx, dy)
        delta = math.atan2(dy, dx) - player.angle
        delta = (delta + math.pi) % (2 * math.pi) - math.pi
        if abs(delta) > HALF_FOV + 0.5 or dist < 0.25 or dist > MAX_DEPTH:
            return None
        return max(dist * math.cos(delta), 1e-4), delta

    def _render_sprites(self, screen, player, sprites):
        """Dessine les billboards (ennemis, objets), du plus loin au plus proche."""
        visibles = []
        for obj in sprites:
            projected = self._project(player, obj.x, obj.y)
            if projected is not None:
                visibles.append((*projected, obj))
        visibles.sort(key=lambda item: -item[0])

        for proj_dist, delta, obj in visibles:
            proj = self.screen_dist / proj_dist
            sprite = obj.current_sprite()
            ratio = sprite.get_width() / sprite.get_height()
            h = int(proj * obj.SPRITE_HEIGHT)
            w = max(1, int(h * ratio))
            if h < 2 or h > self.height * 4:
                continue
            scaled = pygame.transform.scale(sprite, (w, h))

            screen_x = int((0.5 + delta / FOV) * self.width) - w // 2
            # Les pieds reposent sur la ligne de sol (bas d'un mur de hauteur
            # 1 = milieu + proj/2) ; les objets flottants ont un décalage.
            lift = getattr(obj, "v_offset", 0.0)
            bottom = self.height // 2 + int(proj * (0.5 - lift))
            top = bottom - h

            # Occlusion par les murs : blit en tranches verticales, comparées
            # au z-buffer colonne par colonne.
            first_ray = max(0, screen_x // COLUMN_WIDTH)
            last_ray = min(self.num_rays - 1, (screen_x + w) // COLUMN_WIDTH)
            drawn = False
            for ray in range(first_ray, last_ray + 1):
                if self.z_buffer[ray] < proj_dist:
                    continue  # un mur est devant cette tranche du sprite
                strip_x = max(screen_x, ray * COLUMN_WIDTH)
                strip_end = min(screen_x + w, (ray + 1) * COLUMN_WIDTH)
                strip_w = strip_end - strip_x
                if strip_w <= 0:
                    continue
                strip = scaled.subsurface((strip_x - screen_x, 0, strip_w, h))
                screen.blit(strip, (strip_x, top))
                drawn = True

            if drawn and getattr(obj, "max_health", None):
                self._draw_health_bar(screen, obj, screen_x, top, w)

    def _render_particles(self, screen, player, particles):
        """Petits carrés projetés comme les sprites (z-buffer au centre)."""
        for p in particles.items:
            projected = self._project(player, p.x, p.y)
            if projected is None:
                continue
            proj_dist, delta = projected
            ray = int((0.5 + delta / FOV) * self.num_rays)
            if not (0 <= ray < self.num_rays) or self.z_buffer[ray] < proj_dist:
                continue
            proj = self.screen_dist / proj_dist
            size = max(1, int(p.size * proj))
            sx = int((0.5 + delta / FOV) * self.width) - size // 2
            sy = self.height // 2 + int(proj * (0.5 - p.z)) - size // 2
            screen.fill(p.color, (sx, sy, size, size))

    def _draw_health_bar(self, screen, enemy, x, top, w):
        """Barre de vie flottante au-dessus de l'ennemi."""
        if enemy.health >= enemy.max_health:
            return
        bar_h = max(2, w // 12)
        y = max(2, top - bar_h - 4)
        frac = max(0.0, enemy.health / enemy.max_health)
        pygame.draw.rect(screen, (40, 8, 8), (x, y, w, bar_h))
        pygame.draw.rect(screen, (200, 40, 40), (x, y, int(w * frac), bar_h))
