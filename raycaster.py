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
CACHE_LIMIT = 4000            # entrées du cache mural (éviction FIFO incrémentale)
MIN_SPRITE_DIST = 0.5          # distance de projection plancher des billboards
                               # (évite qu'un décor/ennemi grossisse à l'infini
                               # de très près) ; ne change pas l'occlusion,
                               # seulement la taille affichée.


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


def cast_ray_layers(level, ox, oy, angle, heights, screen_dist, horizon,
                    ray_cos, max_depth=MAX_DEPTH):
    """Comme `cast_ray`, mais renvoie TOUS les murs traversés du plus proche
    au plus loin — tant qu'aucun n'occulte entièrement la suite au-dessus de
    l'horizon (ou jusqu'à la sortie de la carte / la portée max).

    Permet de voir le sommet des murs hauts (gratte-ciel) situés DERRIÈRE
    des murs plus bas (salles, barrières) : un raycaster classique s'arrête
    au premier mur et masque tout ce qui est derrière, même plus haut.

    Les profondeurs renvoyées sont déjà corrigées du fisheye (`ray_cos`).
    Liste de (profondeur, tile, vertical, offset), du plus proche au plus loin.
    """
    grid = level.grid
    width, height = level.width, level.height
    doors = level.doors
    sin_a = math.sin(angle) or 1e-8
    cos_a = math.cos(angle) or 1e-8
    map_x, map_y = int(ox), int(oy)
    step_x = 1 if cos_a > 0 else -1
    step_y = 1 if sin_a > 0 else -1
    # Distance au prochain croisement de ligne de grille (DDA unifié).
    next_x = map_x + 1 if step_x > 0 else map_x
    next_y = map_y + 1 if step_y > 0 else map_y
    t_max_x = (next_x - ox) / cos_a
    t_max_y = (next_y - oy) / sin_a
    t_delta_x = step_x / cos_a
    t_delta_y = step_y / sin_a

    hits = []
    # `highest_top` = sommet (y écran) le plus haut déjà couvert par les murs
    # plus proches. Un mur plus lointain n'est visible (et n'est donc gardé)
    # que s'il dépasse au-dessus : sinon il est entièrement masqué. Ce filtre
    # ramène le coût près de celui d'un rayon simple dans les zones dégagées.
    highest_top = float(horizon + 1)
    for _ in range(max_depth * 3):
        if t_max_x < t_max_y:
            map_x += step_x
            depth = t_max_x * ray_cos
            t_max_x += t_delta_x
            vertical = True
        else:
            map_y += step_y
            depth = t_max_y * ray_cos
            t_max_y += t_delta_y
            vertical = False
        if not (0 <= map_x < width and 0 <= map_y < height):
            break                 # hors carte : plus rien de modélisé derrière
        if depth > max_depth:
            break
        tile = grid[map_y][map_x]
        if tile == ".":
            continue
        off = ((oy + depth / ray_cos * sin_a) if vertical
               else (ox + depth / ray_cos * cos_a)) % 1.0
        if tile == "D":
            door = doors.get((map_x, map_y))
            gap = door["open"] if door else 0.0
            if off >= gap:
                off -= gap        # frappe le panneau (texture décalée)
            else:
                continue          # passe par l'entrebâillement
        if depth < 0.02:
            depth = 0.02
        unit = screen_dist / depth
        top = horizon + unit * (0.5 - heights.get(tile, 1.0))
        if top < highest_top:     # dépasse au-dessus de tout ce qui est devant
            hits.append((depth, tile, vertical, off))
            highest_top = top
            if highest_top <= 0:
                break             # occulte jusqu'au haut de l'écran : on arrête
    return hits


def has_line_of_sight(level, x0, y0, x1, y1):
    """Vrai si aucun mur ne bloque le segment entre deux points."""
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist < 1e-6:
        return True
    angle = math.atan2(y1 - y0, x1 - x0)
    if level.first_cover_hit(x0, y0, angle, dist) < dist - 0.05:
        return False
    depth, _, _, _ = cast_ray(level, x0, y0, angle)
    return depth > dist - 0.05


def exposure_fraction(level, ex, ey, tx, ty, radius=0.25, samples=5):
    """Fraction (0..1) de la largeur d'une cible visible depuis (ex, ey),
    en échantillonnant des points le long de son diamètre perpendiculaire
    à la ligne de tir.

    Un joueur qui ne dépasse que partiellement d'une couverture (mur,
    angle de bâtiment...) n'expose ainsi qu'une partie de sa silhouette —
    utilisé pour réduire la précision des ennemis en conséquence."""
    dx, dy = tx - ex, ty - ey
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return 1.0
    perp_x, perp_y = -dy / dist, dx / dist
    visible = 0
    for i in range(samples):
        t = (i / (samples - 1) - 0.5) * 2 if samples > 1 else 0.0
        sx, sy = tx + perp_x * radius * t, ty + perp_y * radius * t
        if has_line_of_sight(level, ex, ey, sx, sy):
            visible += 1
    return visible / samples


def zoom_screen(screen, zoom):
    """Zoom optique de visée en post-traitement : recadre le centre de
    l'image déjà rendue et l'agrandit plein écran.

    Bien plus rapide que re-rendre à un FOV réduit — qui invalidait tout
    le cache des colonnes de murs à chaque frame de transition (gros pics
    de lag). Pour un rendu pixel-art, l'agrandissement de l'image est
    visuellement équivalent."""
    if zoom <= 1.001:
        return
    w, h = screen.get_size()
    cw, ch = int(w / zoom), int(h / zoom)
    crop = screen.subsurface(((w - cw) // 2, (h - ch) // 2, cw, ch)).copy()
    pygame.transform.scale(crop, (w, h), screen)


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
        self.z_buffer = [MAX_DEPTH] * self.num_rays
        self.horizon = self.height // 2
        self._wall_cache = {}
        self._sprite_cache = {}
        self._set_fov(FOV)
        self._build_background()

    def _set_fov(self, fov):
        """Recalcule la projection pour un champ de vision donné (le zoom de
        visée réduit le FOV, ce qui grossit la scène)."""
        self.fov = fov
        self.half_fov = fov / 2
        self.delta_angle = fov / self.num_rays
        self.screen_dist = (self.width / 2) / math.tan(self.half_fov)
        # Correction fisheye : l'écart angulaire de chaque colonne est fixe.
        self.ray_cos = [math.cos(-self.half_fov + (i + 0.5) * self.delta_angle)
                        for i in range(self.num_rays)]

    def set_level(self, level):
        """Prépare les textures ombrées du thème de ce niveau.

        Chaque texture existe en SHADE_LEVELS variantes : assombries avec
        la distance ET teintées d'une brume bleutée (brouillard).
        """
        self.level_config = level.config
        self._build_background()
        self._wall_cache.clear()
        # Hauteurs des murs (multiplicateur d'unités monde ; 1.0 par défaut)
        # et repérage du mur d'énergie (limite du monde, rendu fondu).
        self.heights = self.level_config.get("heights", {})
        theme = {**self.level_config["theme"], "D": "wall_door"}
        self.energy_tile = next((c for c, t in theme.items()
                                 if t == "wall_energy"), None)

        def shade_texture(texture, i):
            """Assombrit + embrume une texture pour le niveau d'ombre `i`."""
            factor = 1.0 - i / (SHADE_LEVELS + 1)
            shaded = texture.copy()
            mult = int(255 * factor)
            shaded.fill((mult, mult, mult), special_flags=pygame.BLEND_MULT)
            fog = tuple(int(c * (1.0 - factor)) for c in FOG_COLOR)
            shaded.fill(fog, special_flags=pygame.BLEND_ADD)
            return shaded

        # tex_cols[char][niveau_d_ombre][x] -> colonne de texture (1 px de large)
        # d'une unité monde de haut (TEX_SIZE px). La porte est ajoutée à tout thème.
        self.tex_cols = {}
        # tall_cols : idem mais colonne pré-empilée sur toute la hauteur du
        # mur (bâtiments, barrières, mur d'énergie), alignée au sol.
        self.tall_cols = {}
        self.tall_h = {}
        for char, tex_name in theme.items():
            texture = assets.get(tex_name)
            shades = []
            for i in range(SHADE_LEVELS):
                shaded = shade_texture(texture, i)
                shades.append([shaded.subsurface((x, 0, 1, TEX_SIZE))
                               for x in range(TEX_SIZE)])
            self.tex_cols[char] = shades

            h_mult = self.heights.get(char, 1.0)
            if h_mult == 1.0:
                continue
            th = int(TEX_SIZE * h_mult)
            self.tall_h[char] = th
            tall_shades = []
            for i in range(SHADE_LEVELS):
                shaded = shade_texture(texture, i)
                stacked = pygame.Surface((TEX_SIZE, th)).convert()
                y = th - TEX_SIZE          # empilé depuis le sol vers le haut
                while y > -TEX_SIZE:
                    stacked.blit(shaded, (0, y))
                    y -= TEX_SIZE
                tall_shades.append([stacked.subsurface((x, 0, 1, th))
                                    for x in range(TEX_SIZE)])
            self.tall_cols[char] = tall_shades

        # Soleil du niveau (position fixe dans le monde, occulté par les murs).
        self.sun = self.level_config.get("sun")
        self._build_sun()

    def _build_sun(self):
        """Construit un soleil cohérent avec son heure et son élévation.

        À midi le disque est petit, blanc-jaune et net. Près de l'horizon il
        devient plus large, orangé, légèrement aplati et entouré d'une brume
        horizontale plus présente. La position reste gérée par `_render_sun`.
        """
        self.sun_surf = None
        if not self.sun:
            return
        color = self.sun["color"]
        hour = float(self.sun.get("hour", 12))
        elevation = max(0.0, min(1.0, float(self.sun.get("el", 0.5))))
        time_warmth = min(1.0, abs(hour - 13.0) / 6.0)
        horizon_warmth = max(0.0, min(1.0, (0.65 - elevation) / 0.55))
        warmth = max(time_warmth, horizon_warmth)

        # Le soleil paraît plus grand dans les couches épaisses de
        # l'atmosphère, près du lever et du coucher.
        r = max(13, int(self.height * (0.036 + 0.027 * horizon_warmth)))
        ry = max(10, int(r * (1.0 - 0.17 * horizon_warmth)))
        glow = max(r * 4, int(r * (3.5 + 1.7 * horizon_warmth)))
        surf = pygame.Surface((glow * 2, glow * 2), pygame.SRCALPHA)
        c = glow

        # Brume atmosphérique étirée sur l'horizon, quasi absente à midi.
        if horizon_warmth > 0.05:
            haze_h = max(ry * 2, int(r * (2.0 + horizon_warmth)))
            for layer in range(7, 0, -1):
                factor = layer / 7
                width = int(glow * 2 * factor)
                height = int(haze_h * factor)
                alpha = int(20 * horizon_warmth * (1.0 - factor * 0.55))
                rect = pygame.Rect(c - width // 2, c - height // 2,
                                   width, height)
                pygame.draw.ellipse(surf, (*color, alpha), rect)

        for i in range(glow, r, -1):                  # halo radial
            t = (i - r) / (glow - r)
            a = int((38 + 34 * warmth) * (1 - t) ** 2)
            pygame.draw.circle(surf, (color[0], color[1], color[2], a), (c, c), i)

        # Disque : cœur presque blanc à midi, franchement doré/rouge le soir.
        noon_core = (255, 255, 242)
        core_mix = 0.18 + 0.67 * warmth
        core = tuple(int(noon_core[i] * (1.0 - core_mix)
                         + color[i] * core_mix) for i in range(3))
        outer = pygame.Rect(c - r, c - ry, r * 2, ry * 2)
        inner = pygame.Rect(c - int(r * 0.82), c - int(ry * 0.82),
                            int(r * 1.64), int(ry * 1.64))
        pygame.draw.ellipse(surf, (*color, 255), outer)
        pygame.draw.ellipse(surf, (*core, 255), inner)

        # Quelques irrégularités ne deviennent perceptibles qu'au couchant.
        if horizon_warmth > 0.55:
            spot = tuple(max(0, int(channel * 0.72)) for channel in color)
            rng = random.Random(round(hour * 100))
            for _ in range(3):
                sx = c + rng.randint(-max(1, r // 2), max(1, r // 2))
                sy = c + rng.randint(-max(1, ry // 3), max(1, ry // 3))
                pygame.draw.ellipse(
                    surf, (*spot, 85),
                    (sx, sy, max(2, r // 5), max(1, ry // 10)),
                )
        self.sun_surf = surf

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
        if self.level_config.get("moon_ground"):
            self._texture_moon_ground(half, total)
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
        self._build_clouds(half, sky_bot)

    def _texture_moon_ground(self, horizon, total):
        """Ajoute au régolithe un grain minéral et des cratères en perspective.

        Cette surface est précalculée avec le fond puis défile avec les étoiles
        quand la caméra tourne : aucun bruit ni primitive n'est créé par frame.
        """
        rng = random.Random(26071969 + self.width * 3 + self.height)
        floor_h = max(1, total - horizon)
        count = max(180, self.width * floor_h // 190)
        for _ in range(count):
            y = rng.randrange(horizon, total)
            depth = (y - horizon) / floor_h
            x = rng.randrange(self.width)
            size = 1 + int(depth * depth * 3)
            base = self.background.get_at((x, y))[:3]
            shift = rng.randint(-20, 18)
            color = tuple(max(18, min(160, channel + shift))
                          for channel in base)
            pygame.draw.rect(self.background, color, (x, y, size, size))

        # Cratères discrets : petits à l'horizon, plus ouverts au premier plan.
        for _ in range(max(14, self.width // 65)):
            # Seule la moitié haute du fond de sol est visible sans baisser
            # la caméra : concentre les reliefs utiles dans cette zone.
            depth = 0.04 + rng.random() * 0.48
            y = horizon + int(depth * floor_h)
            radius_x = max(5, int((7 + rng.random() * 25)
                                  * (0.38 + depth)))
            radius_y = max(2, int(radius_x * (0.18 + depth * 0.22)))
            x = rng.randint(-radius_x, self.width + radius_x)
            pygame.draw.ellipse(
                self.background, (31, 31, 36),
                (x - radius_x, y - radius_y // 2,
                 radius_x * 2, radius_y * 2),
            )
            pygame.draw.arc(
                self.background, (130, 130, 134),
                (x - radius_x, y - radius_y,
                 radius_x * 2, radius_y * 2), math.pi, math.tau, 1,
            )

    def _build_clouds(self, sky_height, sky_horizon):
        """Précalcule un panorama nuageux transparent et horizontalement bouclé.

        Il est reconstruit uniquement au changement de niveau/résolution. Le
        rendu courant se limite ensuite à deux blits alpha, sans génération ni
        transformation de formes dans la boucle de jeu.
        """
        self.cloud_panorama = None
        if (self.level_config.get("stars")
                or not self.level_config.get("clouds", True)):
            return

        width = max(2, self.width * 2)
        surf = pygame.Surface((width, sky_height), pygame.SRCALPHA)
        name = self.level_config.get("name", "")
        seed = sum((i + 1) * ord(char) for i, char in enumerate(name)) + width
        rng = random.Random(seed)
        scale = max(0.65, self.height / 720)

        # Blanc/gris teinté par la couleur d'horizon : froid à midi, rosé au
        # couchant. L'alpha modéré laisse toujours lire le dégradé du niveau.
        light = tuple(min(238, int(150 + channel * 0.35))
                      for channel in sky_horizon)
        shadow = tuple(max(28, int(channel * 0.58)) for channel in light)

        def cloud_cluster(cx, cy, cw, ch):
            # Copies aux bords pour que le panorama boucle sans coupure.
            for wrap_x in (cx - width, cx, cx + width):
                pygame.draw.ellipse(
                    surf, (*shadow, 72),
                    (wrap_x - cw // 2, cy, cw, max(2, ch // 2)),
                )
                lobes = ((-0.30, 0.18, 0.44, 0.72),
                         (-0.08, 0.00, 0.48, 0.90),
                         (0.18, 0.12, 0.43, 0.78),
                         (0.37, 0.28, 0.30, 0.56))
                for ox, oy, wf, hf in lobes:
                    lw, lh = max(3, int(cw * wf)), max(2, int(ch * hf))
                    pygame.draw.ellipse(
                        surf, (*light, 104),
                        (int(wrap_x + cw * ox - lw / 2),
                         int(cy + ch * oy - lh / 2), lw, lh),
                    )

        count = max(12, self.width // 90)
        for _ in range(count):
            cx = rng.randrange(width)
            cy = rng.randint(int(sky_height * 0.50),
                             int(sky_height * 0.82))
            cw = int(rng.randint(100, 240) * scale)
            ch = int(cw * rng.uniform(0.25, 0.40))
            cloud_cluster(cx, cy, cw, ch)
        self.cloud_panorama = surf

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
            # décale le fond de deux largeurs d'écran). Angle négué : en
            # tournant à droite, les étoiles glissent vers la gauche,
            # comme les murs et le soleil.
            x_off = int(-player.angle / (2 * math.pi)
                        * self.width * 2) % self.width
            screen.blit(self.background, (x_off - self.width, bg_y))
            screen.blit(self.background, (x_off, bg_y))
        else:
            screen.blit(self.background, (0, bg_y))
        self._render_sun(screen, player)
        self._render_clouds(screen, player, bg_y)
        self._render_walls(screen, player, level)
        self._render_sprites(screen, player, sprites)
        self._render_particles(screen, player, particles)

    def _render_clouds(self, screen, player, bg_y):
        """Fait défiler le panorama avec la caméra ; désactivé sur la Lune."""
        surf = self.cloud_panorama
        if surf is None:
            return
        width = surf.get_width()
        x_off = int(-player.angle / (2 * math.pi) * width) % width
        screen.blit(surf, (x_off - width, bg_y))
        screen.blit(surf, (x_off, bg_y))

    def _render_sun(self, screen, player):
        """Blit le soleil à sa position monde (avant les murs, qui l'occultent).

        Il progresse d'un niveau à l'autre : bas et chaud à 8h (Entrepôt),
        haut à midi, bas et rouge à 19h (Laboratoire)."""
        if self.sun_surf is None:
            return
        delta = (self.sun["az"] - player.angle + math.pi) % (2 * math.pi) - math.pi
        if abs(delta) > self.half_fov + 0.6:
            return
        sx = int((0.5 + delta / self.fov) * self.width)
        sy = self.horizon - int(self.sun["el"] * self.height * 0.5)
        surf = self.sun_surf
        screen.blit(surf, (sx - surf.get_width() // 2, sy - surf.get_height() // 2))

    def _render_walls(self, screen, player, level):
        # Localise tout ce qui est utilisé dans la boucle chaude.
        px, py, pangle = player.x, player.y, player.angle
        z_buffer = self.z_buffer
        ray_cos = self.ray_cos
        heights = self.heights
        screen_dist = self.screen_dist
        horizon = self.horizon
        angle = pangle - self.half_fov + 0.5 * self.delta_angle

        for ray in range(self.num_rays):
            x = ray * COLUMN_WIDTH
            # Tous les murs traversés par le rayon (du plus proche au plus
            # loin) : le sommet d'un mur haut derrière un mur bas reste ainsi
            # visible.
            layers = cast_ray_layers(level, px, py, angle, heights,
                                     screen_dist, horizon, ray_cos[ray])
            angle += self.delta_angle
            if not layers:
                z_buffer[ray] = MAX_DEPTH
                continue
            z_buffer[ray] = layers[0][0]   # mur le plus proche (occlusion sprites)
            # Dessin du plus loin au plus proche : les murs proches recouvrent
            # le bas des murs lointains, mais leur sommet dépasse encore.
            for depth, tile, vertical, offset in reversed(layers):
                self._draw_wall_column(screen, x, depth, tile, vertical, offset)

    def _draw_wall_column(self, screen, x, depth, tile, vertical, offset):
        """Projette et dessine une colonne de mur à la profondeur `depth`
        (déjà corrigée du fisheye)."""
        screen_dist = self.screen_dist
        horizon = self.horizon
        # Unité projetée = hauteur d'un mur d'une case. Quantifiée à 4 px de
        # haut et 2 colonnes de texture : réduit fortement le nombre de clés
        # distinctes du cache pour une différence imperceptible.
        unit = int(screen_dist / depth) & ~3
        shade = int(depth * 0.55) + (0 if vertical else 2)
        if shade >= SHADE_LEVELS:
            shade = SHADE_LEVELS - 1
        tx = int(offset * TEX_SIZE) & ~1
        if tx >= TEX_SIZE:
            tx = TEX_SIZE - 2
        h_mult = self.heights.get(tile, 1.0)

        # Le mur d'énergie (limite du monde) ne se matérialise qu'à
        # l'approche : invisible au loin, opaque seulement tout contre.
        alpha = 255
        if tile == self.energy_tile:
            fade = (3.6 - depth) / 2.4
            if fade <= 0.02:
                return
            alpha = int(min(1.0, fade) * 255)

        if h_mult == 1.0:
            default_char = next(iter(self.tex_cols))
            column = (self.tex_cols.get(tile)
                      or self.tex_cols[default_char])[shade][tx]
            self._draw_column(screen, x, column, TEX_SIZE,
                              horizon - unit // 2, unit,
                              (tile, shade, tx, unit), alpha)
        else:
            # Mur haut (gratte-ciel, barrière...) : base au sol, la colonne
            # pré-empilée est étirée sur toute sa hauteur.
            th = self.tall_h[tile]
            total = int(unit * h_mult) & ~3
            floor_y = horizon + unit // 2
            column = self.tall_cols[tile][shade][tx]
            self._draw_column(screen, x, column, th, floor_y - total,
                              total, (tile, shade, tx, total), alpha)

    def _draw_column(self, screen, x, column, native_h, top, total_h,
                     cache_key, alpha=255):
        """Blit une colonne de mur (native `native_h` px) étirée à `total_h`
        px, sommet en `top`. Mémoïse les colonnes entièrement visibles ;
        clippe et redécoupe celles qui débordent de l'écran."""
        scr_h = self.height
        if total_h <= 0:
            return
        if top >= 0 and top + total_h <= scr_h:
            # Cache borné à éviction incrémentale (FIFO) : quand il est
            # plein, on retire UNE seule entrée (la plus ancienne) par
            # insertion. Statique = 100 % de hits (aucun redimensionnement) ;
            # en rotation, la libération d'une surface par colonne manquée
            # est amortie (pas de pic d'éviction en bloc).
            hot = self._wall_cache
            scaled = hot.get(cache_key)
            if scaled is None:
                scaled = pygame.transform.scale(column, (COLUMN_WIDTH, total_h))
                if len(hot) >= CACHE_LIMIT:
                    del hot[next(iter(hot))]
                hot[cache_key] = scaled
            if alpha < 255:
                scaled = scaled.copy()
                scaled.set_alpha(alpha)
            screen.blit(scaled, (x, top))
            return
        # Débordement : on ne plie que la tranche de texture visible.
        draw_top = 0 if top < 0 else top
        draw_bottom = min(scr_h, top + total_h)
        if draw_bottom <= draw_top:
            return
        ty0 = (draw_top - top) * native_h / total_h
        th_ = max(1, min(native_h - int(ty0),
                         int((draw_bottom - draw_top) * native_h / total_h) + 1))
        sub = column.subsurface((0, int(ty0), 1, th_))
        seg = pygame.transform.scale(sub, (COLUMN_WIDTH, draw_bottom - draw_top))
        if alpha < 255:
            seg = seg.copy()
            seg.set_alpha(alpha)
        screen.blit(seg, (x, draw_top))

    def _project(self, player, x, y):
        """Projection d'un point monde -> (distance projetée, delta d'angle).

        Retourne None si le point est hors du champ de vision (avec marge).
        """
        dx, dy = x - player.x, y - player.y
        dist = math.hypot(dx, dy)
        delta = math.atan2(dy, dx) - player.angle
        delta = (delta + math.pi) % (2 * math.pi) - math.pi
        if abs(delta) > self.half_fov + 0.5 or dist < 0.25 or dist > MAX_DEPTH:
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
            # La taille affichée est plafonnée à une distance plancher (pas
            # l'occlusion/le tri, qui utilisent la vraie distance) : sans
            # ça, un décor ou un ennemi grossit de façon absurde quand on
            # s'en approche de très près.
            proj = self.screen_dist / max(proj_dist, MIN_SPRITE_DIST)
            sprite = obj.current_sprite(player)  # pose selon l'angle de vue
            ratio = sprite.get_width() / sprite.get_height()
            h = int(proj * obj.SPRITE_HEIGHT) & ~1   # quantifié (cache)
            w = max(2, int(h * ratio) & ~1)
            if h < 2 or h > self.height * 4:
                continue
            scaled = self._scaled_sprite(sprite, w, h)

            screen_x = int((0.5 + delta / self.fov) * self.width) - w // 2
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
            ray = int((0.5 + delta / self.fov) * self.num_rays)
            if not (0 <= ray < self.num_rays) or self.z_buffer[ray] < proj_dist:
                continue
            proj = self.screen_dist / proj_dist
            # Les particules rétrécissent en fin de vie (fondu de sortie),
            # avec un plafond pour celles qui frôlent la caméra.
            fade = p.life * 3.5
            size = int(p.size * proj * (fade if fade < 1.0 else 1.0))
            size = max(1, min(size, self.height // 12))
            sx = int((0.5 + delta / self.fov) * self.width) - size // 2
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
