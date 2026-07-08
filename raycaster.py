"""Moteur de rendu pseudo-3D par raycasting (façon Wolfenstein 3D).

Pour chaque colonne de l'écran, un rayon donne la distance au premier
mur : on y "plie" verticalement une colonne de la texture pixel-art du
mur (assets/wall_*.png), mise à l'échelle selon la distance. Un z-buffer
(une profondeur par colonne) masque ensuite correctement les sprites
(ennemis, objets) et les particules derrière les murs.

Optimisations notables :
- l'ombrage est pré-calculé (variantes assombries + brume bleutée) ;
- la correction de perspective (fisheye) est une table de cosinus ;
- les colonnes de mur et les sprites mis à l'échelle sont mémoïsés :
  d'une frame à l'autre, les mêmes tailles reviennent sans cesse ;
- `cast_ray` lit la grille directement (pas d'appel de méthode par pas).

Portes ('D') : le panneau coulisse latéralement ; le rayon passe dans
l'ouverture (offset < fraction d'ouverture) et frappe le panneau au-delà,
avec la texture décalée d'autant.
"""

import math
import random

import pygame

import assets
from assets import TEX_SIZE

FOV = math.radians(70)        # champ de vision horizontal
HALF_FOV = FOV / 2
MAX_DEPTH = 30                # portée maximale des rayons (en cases)
COLUMN_WIDTH = 2              # largeur en pixels d'une colonne de rendu
SHADE_LEVELS = 10             # nombre de variantes d'ombrage par texture
FOG_COLOR = (14, 17, 26)      # brume bleutée ajoutée avec la distance
CACHE_LIMIT = 20000           # taille max des caches de mise à l'échelle


def cast_ray(level, ox, oy, angle, max_depth=MAX_DEPTH):
    """Lance un rayon depuis (ox, oy).

    Retourne (profondeur, type_de_mur, vertical, offset) où `vertical`
    indique une face verticale de la grille et `offset` (0..1) la position
    du point d'impact le long du mur (colonne de texture à afficher).
    Méthode classique des intersections avec les lignes horizontales et
    verticales de la grille — écrite avec des accès directs à la grille,
    c'est la fonction la plus chaude du jeu.
    """
    grid = level.grid
    width, height = level.width, level.height
    doors = level.doors
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
    off_v = 0.0
    for _ in range(max_depth):
        ix, iy = int(x_v), int(y_v)
        tile_v = (grid[iy][ix]
                  if 0 <= ix < width and 0 <= iy < height else "1")
        if tile_v == ".":         # cas ultra-majoritaire : chemin rapide
            x_v += dx
            y_v += dy_v
            depth_v += delta_v
            continue
        if tile_v == "D":
            door = doors.get((ix, iy))
            gap = door["open"] if door else 0.0
            off_v = y_v % 1.0
            if off_v >= gap:      # frappe le panneau (texture décalée)
                off_v -= gap
                break
            x_v += dx             # passe par l'entrebâillement
            y_v += dy_v
            depth_v += delta_v
            continue
        off_v = y_v % 1.0
        break

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
    off_h = 0.0
    for _ in range(max_depth):
        ix, iy = int(x_h), int(y_h)
        tile_h = (grid[iy][ix]
                  if 0 <= ix < width and 0 <= iy < height else "1")
        if tile_h == ".":
            x_h += dx_h
            y_h += dy
            depth_h += delta_h
            continue
        if tile_h == "D":
            door = doors.get((ix, iy))
            gap = door["open"] if door else 0.0
            off_h = x_h % 1.0
            if off_h >= gap:
                off_h -= gap
                break
            x_h += dx_h
            y_h += dy
            depth_h += delta_h
            continue
        off_h = x_h % 1.0
        break

    # On garde l'intersection la plus proche.
    if depth_v < depth_h:
        return depth_v, tile_v, True, off_v
    return depth_h, tile_h, False, off_h


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
        self.horizon = self.height // 2
        # Correction fisheye : l'écart angulaire de chaque colonne est fixe.
        self.ray_cos = [math.cos(-HALF_FOV + (i + 0.5) * self.delta_angle)
                        for i in range(self.num_rays)]
        self._wall_cache = {}
        self._sprite_cache = {}
        self._build_background()

    def set_level(self, level):
        """Prépare les textures ombrées du thème de ce niveau.

        Chaque texture existe en SHADE_LEVELS variantes : assombries avec
        la distance ET teintées d'une brume bleutée (brouillard).
        """
        self.level_config = level.config
        self._build_background()
        self._wall_cache.clear()
        # tex_cols[char][niveau_d_ombre][x] -> colonne de texture (1 px de large)
        # La texture de porte est ajoutée automatiquement à chaque thème.
        theme = {**self.level_config["theme"], "D": "wall_door"}
        self.tex_cols = {}
        for char, tex_name in theme.items():
            texture = assets.get(tex_name)
            shades = []
            for i in range(SHADE_LEVELS):
                factor = 1.0 - i / (SHADE_LEVELS + 1)
                shaded = texture.copy()
                mult = int(255 * factor)
                shaded.fill((mult, mult, mult), special_flags=pygame.BLEND_MULT)
                fog = tuple(int(c * (1.0 - factor)) for c in FOG_COLOR)
                shaded.fill(fog, special_flags=pygame.BLEND_ADD)
                shades.append([shaded.subsurface((x, 0, 1, TEX_SIZE))
                               for x in range(TEX_SIZE)])
            self.tex_cols[char] = shades

    def _build_background(self):
        """Pré-calcule le dégradé ciel/sol aux couleurs du niveau.

        La surface est plus haute que l'écran : elle est blittée décalée
        selon la visée verticale (y-shearing) et le tremblement d'écran.
        """
        (sky_top, sky_bot) = self.level_config["sky"]
        (floor_top, floor_bot) = self.level_config["floor"]
        self.bg_margin = int(self.height * 0.45) + 8
        total = self.height + 2 * self.bg_margin
        half = total // 2
        self.background = pygame.Surface((self.width, total))
        for y in range(half):
            t = y / max(1, half)
            color = [int(a + (b - a) * t) for a, b in zip(sky_top, sky_bot)]
            pygame.draw.line(self.background, color, (0, y), (self.width, y))
        for y in range(half, total):
            t = (y - half) / max(1, total - half)
            color = [int(a + (b - a) * t) for a, b in zip(floor_top, floor_bot)]
            pygame.draw.line(self.background, color, (0, y), (self.width, y))
        # Lueur de brume sur la ligne d'horizon (fond atmosphérique).
        for i in range(14):
            alpha_color = [min(255, c + (14 - i) * 3)
                           for c in ((sky_bot[j] + floor_top[j]) // 2
                                     for j in range(3))]
            pygame.draw.line(self.background, alpha_color,
                             (0, half - 7 + i), (self.width, half - 7 + i))
        # Ciel étoilé (la Lune) : le fond défile alors avec la rotation.
        self.sky_scroll = bool(self.level_config.get("stars"))
        if self.sky_scroll:
            rng = random.Random(42)
            for _ in range(90 + self.width // 4):
                sx = rng.randint(0, self.width - 1)
                sy = rng.randint(0, int(half * 0.88))
                color = rng.choice(((235, 235, 240), (200, 210, 255),
                                    (255, 240, 214), (150, 155, 175)))
                self.background.set_at((sx, sy), color)
                if rng.random() < 0.12:            # quelques étoiles brillantes
                    for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if 0 <= sx + ox < self.width:
                            self.background.set_at((sx + ox, sy + oy), color)

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def render(self, screen, player, level, sprites, particles, pitch_px=0):
        """`sprites` : entités billboard ; `pitch_px` : décalage vertical de
        l'horizon (visée verticale + tremblement d'écran)."""
        # L'horizon monte quand on vise vers le bas, et inversement.
        self.horizon = self.height // 2 + pitch_px
        bg_center = self.bg_margin + self.height // 2
        bg_y = self.horizon - bg_center
        if self.sky_scroll:
            # Ciel étoilé : défile horizontalement avec la rotation (deux
            # blits pour boucler sans couture ; x2 = un tour complet
            # décale le fond de deux largeurs d'écran).
            x_off = int(player.angle / (2 * math.pi)
                        * self.width * 2) % self.width
            screen.blit(self.background, (x_off - self.width, bg_y))
            screen.blit(self.background, (x_off, bg_y))
        else:
            screen.blit(self.background, (0, bg_y))
        self._render_walls(screen, player, level)
        self._render_sprites(screen, player, sprites)
        self._render_particles(screen, player, particles)

    def _render_walls(self, screen, player, level):
        # Localise tout ce qui est utilisé dans la boucle chaude.
        px, py, pangle = player.x, player.y, player.angle
        z_buffer = self.z_buffer
        ray_cos = self.ray_cos
        tex_cols = self.tex_cols
        wall_cache = self._wall_cache
        screen_dist = self.screen_dist
        horizon = self.horizon
        scr_h = self.height
        scale = pygame.transform.scale
        blit = screen.blit
        default_char = next(iter(tex_cols))
        angle = pangle - HALF_FOV + 0.5 * self.delta_angle

        for ray in range(self.num_rays):
            depth, tile, vertical, offset = cast_ray(level, px, py, angle)
            depth *= ray_cos[ray]     # correction fisheye pré-calculée
            if depth < 0.02:
                depth = 0.02
            z_buffer[ray] = depth

            # Hauteur quantifiée au pixel pair : divise l'espace de clés du
            # cache par deux pour une différence visuelle imperceptible.
            wall_height = int(screen_dist / depth) & ~1
            shade = int(depth * 0.55) + (0 if vertical else 2)
            if shade >= SHADE_LEVELS:
                shade = SHADE_LEVELS - 1
            tx = int(offset * TEX_SIZE)
            if tx >= TEX_SIZE:
                tx = TEX_SIZE - 1
            top = horizon - wall_height // 2

            if top >= 0 and top + wall_height <= scr_h:
                # Mur entièrement visible : cas ultra-fréquent, mémoïsé
                # (les mêmes hauteurs reviennent frame après frame).
                key = (tile, shade, tx, wall_height)
                scaled = wall_cache.get(key)
                if scaled is None:
                    shades = tex_cols.get(tile) or tex_cols[default_char]
                    scaled = scale(shades[shade][tx],
                                   (COLUMN_WIDTH, wall_height))
                    if len(wall_cache) >= CACHE_LIMIT:
                        # Éviction douce des plus anciennes entrées (les
                        # dicts gardent l'ordre d'insertion) : pas de purge
                        # brutale qui ferait bégayer une caméra qui tourne.
                        evict = iter(wall_cache)
                        for old in [next(evict) for _ in range(2048)]:
                            del wall_cache[old]
                    wall_cache[key] = scaled
                blit(scaled, (ray * COLUMN_WIDTH, top))
            else:
                # Mur débordant de l'écran : on ne plie que la partie
                # visible de la texture (surfaces bornées, pas de cache).
                draw_top = 0 if top < 0 else top
                draw_bottom = top + wall_height
                if draw_bottom > scr_h:
                    draw_bottom = scr_h
                if draw_bottom > draw_top:
                    tex_y0 = (draw_top - top) * TEX_SIZE / wall_height
                    tex_y1 = (draw_bottom - top) * TEX_SIZE / wall_height
                    tex_h = max(1, min(TEX_SIZE - int(tex_y0),
                                       int(tex_y1 - tex_y0) + 1))
                    shades = tex_cols.get(tile) or tex_cols[default_char]
                    sub = shades[shade][tx].subsurface(
                        (0, int(tex_y0), 1, tex_h))
                    blit(scale(sub, (COLUMN_WIDTH, draw_bottom - draw_top)),
                         (ray * COLUMN_WIDTH, draw_top))
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

    def _scaled_sprite(self, sprite, w, h):
        """Mise à l'échelle mémoïsée (tailles quantifiées au pixel pair)."""
        key = (id(sprite), w, h)
        scaled = self._sprite_cache.get(key)
        if scaled is None:
            scaled = pygame.transform.scale(sprite, (w, h))
            if len(self._sprite_cache) >= CACHE_LIMIT:
                evict = iter(self._sprite_cache)
                for old in [next(evict) for _ in range(1024)]:
                    del self._sprite_cache[old]
            self._sprite_cache[key] = scaled
        return scaled

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
            sprite = obj.current_sprite(player)  # pose selon l'angle de vue
            ratio = sprite.get_width() / sprite.get_height()
            h = int(proj * obj.SPRITE_HEIGHT) & ~1   # quantifié (cache)
            w = max(2, int(h * ratio) & ~1)
            if h < 2 or h > self.height * 4:
                continue
            scaled = self._scaled_sprite(sprite, w, h)

            screen_x = int((0.5 + delta / FOV) * self.width) - w // 2
            # Les pieds reposent sur la ligne de sol (bas d'un mur de hauteur
            # 1 = horizon + proj/2) ; les objets flottants ont un décalage.
            lift = getattr(obj, "v_offset", 0.0)
            bottom = self.horizon + int(proj * (0.5 - lift))
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

            if drawn and getattr(obj, "max_health", None) and obj.alive:
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
            # Les particules rétrécissent en fin de vie (fondu de sortie),
            # avec un plafond pour celles qui frôlent la caméra.
            fade = p.life * 3.5
            size = int(p.size * proj * (fade if fade < 1.0 else 1.0))
            size = max(1, min(size, self.height // 12))
            sx = int((0.5 + delta / FOV) * self.width) - size // 2
            sy = self.horizon + int(proj * (0.5 - p.z)) - size // 2
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
