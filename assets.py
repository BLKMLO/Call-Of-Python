"""Assets pixel-art du jeu, façon Minecraft.

Chaque asset (texture de mur, sprite d'ennemi, arme, objet à ramasser)
est un petit fichier PNG dans `assets/`, dessiné en basse résolution puis
agrandi sans lissage pour garder le rendu "gros pixels". Les textures de
murs sont ensuite "pliées" sur les murs 3D par le raycaster.

Les PNG sont générés par ce module (dessin procédural, graine fixe) :
- au premier lancement s'ils manquent ;
- ou tous d'un coup avec `python assets.py`.
Ils peuvent donc aussi être retouchés à la main dans n'importe quel
éditeur d'images, comme un pack de textures.
"""

import os
import random

import pygame

ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
TEX_SIZE = 64          # taille finale des textures de murs (carrées)

_cache = {}
_avg_cache = {}


def get(name, flipped=False):
    """Retourne la surface de l'asset `name` (chargée du PNG ou générée).

    `flipped=True` retourne la version miroir horizontal (mise en cache) —
    utilisée pour les sprites de profil vus de l'autre côté.
    """
    key = (name, flipped)
    if key in _cache:
        return _cache[key]
    if flipped:
        surf = pygame.transform.flip(get(name), True, False)
    else:
        path = os.path.join(ASSET_DIR, name + ".png")
        if os.path.exists(path):
            surf = pygame.image.load(path)
        else:
            surf = _BUILDERS[name]()
            os.makedirs(ASSET_DIR, exist_ok=True)
            pygame.image.save(surf, path)
        if pygame.display.get_init() and pygame.display.get_surface():
            surf = surf.convert_alpha()  # accélère les blits une fois l'écran créé
    _cache[key] = surf
    return surf


def get_tinted(name, flipped=False):
    """Variante « flash blanc » d'un sprite (ennemi qui encaisse une balle).

    Mise en cache comme les autres : le sur-teintage n'est calculé qu'une
    seule fois par sprite.
    """
    key = (name, flipped, "tint")
    if key not in _cache:
        surf = get(name, flipped).copy()
        surf.fill((95, 95, 95), special_flags=pygame.BLEND_RGB_ADD)
        _cache[key] = surf
    return _cache[key]


def average_color(name):
    """Couleur moyenne d'un asset (utilisée pour teinter les particules)."""
    if name not in _avg_cache:
        _avg_cache[name] = pygame.transform.average_color(get(name))[:3]
    return _avg_cache[name]


# ----------------------------------------------------------------------
# Outils de dessin bas niveau
# ----------------------------------------------------------------------
def _clamp(v):
    return max(0, min(255, int(v)))


def _jit(color, rng, amount):
    """Couleur légèrement bruitée : donne le grain 'pixel-art'."""
    d = rng.randint(-amount, amount)
    return (_clamp(color[0] + d), _clamp(color[1] + d), _clamp(color[2] + d))


def _rect(surf, x, y, w, h, color, rng=None, jitter=0):
    """Rectangle pixel par pixel, avec bruit optionnel par pixel."""
    W, H = surf.get_size()
    for px in range(max(0, x), min(W, x + w)):
        for py in range(max(0, y), min(H, y + h)):
            c = _jit(color, rng, jitter) if rng and jitter else color
            surf.set_at((px, py), c)


def _upscale(surf, k):
    """Agrandissement sans lissage (nearest) : pixels bien nets."""
    w, h = surf.get_size()
    return pygame.transform.scale(surf, (w * k, h * k))


# ----------------------------------------------------------------------
# Textures de murs (dessinées en 32x32 pour deux fois plus de détail,
# agrandies x2 -> 64x64). Chaque matériau a du relief : arêtes claires en
# haut/gauche, ombres en bas/droite, fissures et usure aléatoires.
# ----------------------------------------------------------------------
def _tex_base():
    return pygame.Surface((32, 32))


def _bevel(surf, x, y, w, h, light, dark):
    """Relief d'un bloc : arête claire en haut/gauche, ombre en bas/droite."""
    _rect(surf, x, y, w, 1, light)
    _rect(surf, x, y, 1, h, light)
    _rect(surf, x, y + h - 1, w, 1, dark)
    _rect(surf, x + w - 1, y + 1, 1, h - 1, dark)


def _shift(color, delta):
    return tuple(_clamp(c + delta) for c in color)


def _tex_brick():
    """Mur de briques rouges : teinte propre à chaque brique, arêtes en
    relief, fissures et éclats occasionnels."""
    rng = random.Random(101)
    s = _tex_base()
    _rect(s, 0, 0, 32, 32, (66, 58, 54), rng, 5)          # mortier
    for row in range(4):
        y = row * 8
        offset = 0 if row % 2 == 0 else 8
        for bx in range(-1, 3):
            x = bx * 16 + offset
            base = _shift((152, 74, 56), rng.randint(-16, 14))
            _rect(s, x, y + 1, 15, 7, base, rng, 7)
            _bevel(s, x, y + 1, 15, 7, _shift(base, 22), _shift(base, -26))
            if rng.random() < 0.35:                        # fissure
                cx_, cy_ = x + rng.randint(3, 11), y + 2
                for step in range(rng.randint(2, 4)):
                    if 0 <= cx_ < 32:
                        s.set_at((cx_, min(31, cy_ + step)), _shift(base, -40))
                    cx_ += rng.choice((-1, 0, 1))
    return _upscale(s, 2)


def _tex_crate():
    """Caisse en bois : planches veinées, cadre en relief, équerres
    métalliques cloutées aux coins."""
    rng = random.Random(102)
    s = _tex_base()
    for y in range(32):                                    # planches + veines
        tone = (150, 112, 62) if (y // 8) % 2 == 0 else (142, 104, 56)
        _rect(s, 0, y, 32, 1, tone, rng, 6)
    for y in (7, 15, 23):                                  # rainures
        _rect(s, 0, y, 32, 1, (96, 70, 38), rng, 4)
        _rect(s, 0, y + 1, 32, 1, (168, 128, 74), rng, 4)  # rebord éclairé
    for _ in range(10):                                    # nœuds du bois
        wx, wy = rng.randint(2, 29), rng.randint(1, 30)
        s.set_at((wx, wy), (110, 80, 44))
    _rect(s, 0, 0, 32, 3, (124, 92, 50), rng, 5)           # cadre
    _rect(s, 0, 29, 32, 3, (108, 78, 42), rng, 5)
    _rect(s, 0, 0, 3, 32, (124, 92, 50), rng, 5)
    _rect(s, 29, 0, 3, 32, (108, 78, 42), rng, 5)
    for cx_, cy_ in ((1, 1), (27, 1), (1, 27), (27, 27)):  # équerres
        _rect(s, cx_, cy_, 4, 4, (118, 122, 132), rng, 6)
        s.set_at((cx_ + 1, cy_ + 1), (170, 174, 184))      # clou
    return _upscale(s, 2)


def _tex_stone():
    """Pierres grises : blocs biseautés de tailles inégales, mousse rare."""
    rng = random.Random(103)
    s = _tex_base()
    _rect(s, 0, 0, 32, 32, (42, 42, 48), rng, 4)          # joints
    for row, (y, h) in enumerate(((0, 9), (9, 8), (17, 9), (26, 6))):
        x = -rng.randint(0, 3)
        while x < 32:
            w = rng.randint(6, 11)
            base = _shift((122, 124, 130), rng.randint(-14, 12))
            _rect(s, x, y, w - 1, h - 1, base, rng, 8)
            _bevel(s, x, y, w - 1, h - 1, _shift(base, 24), _shift(base, -30))
            if rng.random() < 0.25:                        # mousse discrète
                mx, my = x + rng.randint(1, max(2, w - 3)), y + h - 2
                if 0 <= mx < 32 and 0 <= my < 32:
                    s.set_at((mx, my), (86, 116, 74))
            x += w
    return _upscale(s, 2)


def _tex_metal():
    """Panneau métallique : brossage vertical, jointure biseautée,
    rivets en relief et rayures d'usure."""
    rng = random.Random(104)
    s = _tex_base()
    for x in range(32):                                    # brossage vertical
        tone = _shift((106, 110, 122), rng.randint(-5, 5))
        _rect(s, x, 0, 1, 32, tone, rng, 3)
    _rect(s, 0, 15, 32, 1, (74, 78, 90))                   # jointure centrale
    _rect(s, 0, 16, 32, 1, (134, 138, 150))
    _rect(s, 0, 0, 32, 1, (140, 144, 156))                 # arêtes du panneau
    _rect(s, 0, 31, 32, 1, (70, 74, 86))
    for px, py in ((3, 4), (28, 4), (3, 27), (28, 27),
                   (15, 4), (15, 27)):                     # rivets bombés
        s.set_at((px, py), (176, 180, 192))
        s.set_at((px + 1, py + 1), (66, 70, 82))
    for _ in range(4):                                     # rayures claires
        sx, sy = rng.randint(2, 24), rng.randint(3, 27)
        for step in range(rng.randint(3, 6)):
            s.set_at((min(31, sx + step), max(0, sy - step)), (150, 154, 166))
    return _upscale(s, 2)


def _tex_tech():
    """Panneau high-tech : conduits néon à halo, petit écran à balayage,
    grille d'aération (laboratoire)."""
    rng = random.Random(105)
    s = _tex_base()
    _rect(s, 0, 0, 32, 32, (38, 43, 54), rng, 4)
    _rect(s, 0, 15, 32, 1, (26, 30, 40))                   # jointures
    _rect(s, 15, 0, 1, 32, (26, 30, 40))
    # conduit néon horizontal avec halo
    _rect(s, 2, 6, 28, 1, (36, 96, 108))                   # halo
    _rect(s, 2, 8, 28, 1, (36, 96, 108))
    _rect(s, 2, 7, 28, 1, (92, 226, 238))                  # cœur lumineux
    # petit écran à lignes de balayage
    _rect(s, 19, 19, 10, 8, (16, 22, 20))
    for i, sy in enumerate(range(20, 26)):
        _rect(s, 20, sy, 8, 1, (52, 150, 92) if i % 2 == 0 else (26, 74, 46))
    _bevel(s, 19, 19, 10, 8, (70, 78, 92), (18, 22, 30))
    # grille d'aération
    for sy in range(21, 28, 2):
        _rect(s, 4, sy, 9, 1, (20, 24, 32))
    # diodes d'état
    s.set_at((25, 3), (240, 90, 90))
    s.set_at((27, 3), (110, 235, 130))
    s.set_at((4, 12), (235, 200, 90))
    return _upscale(s, 2)


def _tex_door():
    """Porte coulissante : deux vantaux biseautés, bandes de signalisation
    diagonales, rails latéraux et voyant d'ouverture."""
    rng = random.Random(106)
    s = _tex_base()
    _rect(s, 0, 0, 32, 32, (88, 94, 106), rng, 4)          # panneau
    _rect(s, 0, 0, 2, 32, (128, 134, 146))                 # rails
    _rect(s, 30, 0, 2, 32, (128, 134, 146))
    _rect(s, 15, 0, 2, 32, (52, 56, 66))                   # jointure centrale
    _bevel(s, 2, 0, 13, 32, (116, 122, 134), (62, 66, 78))  # vantail gauche
    _bevel(s, 17, 0, 13, 32, (116, 122, 134), (62, 66, 78))  # vantail droit
    for y in (5, 24):                                      # bandes diagonales
        for x in range(3, 29):
            if 14 <= x <= 17:
                continue
            color = (216, 178, 44) if ((x + y) // 3) % 2 == 0 else (42, 40, 32)
            _rect(s, x, y, 1, 3, color)
    for y in range(13, 20, 2):                             # rainures de prise
        _rect(s, 5, y, 7, 1, (66, 70, 82))
        _rect(s, 20, y, 7, 1, (66, 70, 82))
    s.set_at((3, 10), (110, 235, 130))                     # voyant + halo
    s.set_at((4, 10), (60, 140, 82))
    return _upscale(s, 2)


# ----------------------------------------------------------------------
# Sprites d'ennemis (16x24, agrandis x4 -> 64x96) : style bonhomme
# Minecraft, trois poses : repos, marche, tir.
# ----------------------------------------------------------------------
ENEMY_PALETTES = {
    "grunt": {   # milicien débraillé
        "skin": (204, 162, 122), "top": (62, 46, 32),
        "suit": (148, 122, 82), "dark": (116, 94, 60),
        "legs": (94, 78, 54), "boots": (44, 40, 32), "accent": None,
    },
    "soldier": {  # soldat en treillis, casqué
        "skin": (198, 156, 118), "top": (60, 74, 48),
        "suit": (86, 106, 62), "dark": (66, 84, 48),
        "legs": (72, 88, 54), "boots": (36, 36, 32), "accent": None,
    },
    "heavy": {    # soldat lourd en armure, visière rouge
        "skin": (70, 72, 84), "top": (78, 80, 94),
        "suit": (84, 86, 100), "dark": (60, 62, 74),
        "legs": (64, 66, 78), "boots": (32, 32, 38), "accent": (222, 62, 52),
        "bulk": True,
    },
    "boss": {     # le Colosse : armure noire, visière orange incandescente
        "skin": (44, 42, 48), "top": (52, 50, 58),
        "suit": (66, 56, 62), "dark": (46, 38, 44),
        "legs": (52, 44, 50), "boots": (26, 24, 28), "accent": (255, 150, 40),
        "bulk": True,
    },
    "kamikaze": {  # fanatique au gilet explosif, fonce sur le joueur
        "skin": (206, 160, 118), "top": (120, 44, 30),
        "suit": (168, 84, 42), "dark": (128, 60, 30),
        "legs": (96, 58, 36), "boots": (42, 32, 26), "accent": None,
        "chest": (216, 40, 36),   # pains d'explosif sur le torse
    },
    "sniper": {    # tireur d'élite, lunette turquoise
        "skin": (198, 156, 118), "top": (96, 106, 96),
        "suit": (112, 122, 106), "dark": (86, 94, 82),
        "legs": (92, 100, 88), "boots": (36, 38, 34), "accent": (90, 210, 200),
    },
    "ally": {      # coéquipier (multijoueur LAN) : uniforme bleu
        "skin": (200, 158, 120), "top": (40, 56, 92),
        "suit": (62, 86, 132), "dark": (46, 66, 104),
        "legs": (52, 70, 106), "boots": (30, 34, 44), "accent": None,
    },
}


def _enemy_sprite(kind, pose):
    """Sprite d'ennemi : poses de face (idle/walk/walk2/fire), de dos
    (_back), de profil (_side) et au sol (dead).

    `walk` et `walk2` forment un vrai cycle de marche à deux frames
    (jambe gauche puis jambe droite levée, balancement des bras opposé).
    """
    p = ENEMY_PALETTES[kind]
    if pose == "dead":
        return _enemy_dead_sprite(p)
    if pose.endswith("_back"):
        return _enemy_back_sprite(p, pose[:-5])
    if pose.endswith("_side"):
        return _enemy_side_sprite(p, pose[:-5])
    heavy = p.get("bulk", False)
    s = pygame.Surface((16, 24), pygame.SRCALPHA)

    # --- tête : casque/cheveux, visage, yeux (ou visière) ---
    _rect(s, 5, 0, 6, 2, p["top"])
    _rect(s, 5, 2, 6, 4, p["skin"])
    if p["accent"]:
        _rect(s, 5, 3, 6, 1, p["accent"])       # visière lumineuse du lourd
    else:
        s.set_at((6, 3), (28, 28, 28))          # yeux
        s.set_at((9, 3), (28, 28, 28))

    # --- torse (plus large pour le lourd) + ceinture ---
    bx, bw = (3, 10) if heavy else (4, 8)
    _rect(s, bx, 6, bw, 7, p["suit"])
    _rect(s, bx, 12, bw, 1, p["dark"])
    if heavy:                                    # épaulières
        _rect(s, 2, 5, 3, 2, p["dark"])
        _rect(s, 11, 5, 3, 2, p["dark"])
    if p.get("chest"):                           # gilet explosif (kamikaze)
        for cx_ in (5, 7, 9):
            _rect(s, cx_, 7, 2, 3, p["chest"])
            s.set_at((cx_, 7), (255, 220, 120))  # détonateurs


    # --- bras et jambes selon la pose ---
    if pose == "fire":
        # bras ramenés devant, arme pointée vers la caméra + éclair de tir
        _rect(s, 3, 7, 3, 4, p["dark"])
        _rect(s, 10, 7, 3, 4, p["dark"])
        _rect(s, 6, 8, 4, 4, (34, 34, 38))                   # arme
        _rect(s, 6, 7, 4, 1, (255, 226, 110))                # halo
        _rect(s, 6, 12, 4, 1, (255, 226, 110))
        _rect(s, 5, 8, 1, 4, (255, 226, 110))
        _rect(s, 10, 8, 1, 4, (255, 226, 110))
        _rect(s, 7, 9, 2, 2, (255, 255, 220))                # cœur du flash
    else:
        swing = {"walk": 1, "walk2": -1}.get(pose, 0)
        _rect(s, 2, 6 + swing, 2, 6, p["dark"])              # bras gauche
        _rect(s, 12, 6 - swing, 2, 6, p["dark"])             # bras droit
        _rect(s, 2, 11 + swing, 2, 1, p["skin"])             # mains
        _rect(s, 12, 10 - swing, 2, 1, p["skin"])

    if pose == "walk":                    # jambe gauche levée, droite au sol
        _rect(s, 4, 15, 3, 6, p["legs"])
        _rect(s, 4, 20, 3, 3, p["boots"])
        _rect(s, 9, 14, 3, 7, p["legs"])
        _rect(s, 9, 21, 3, 3, p["boots"])
    elif pose == "walk2":                 # frame opposée du cycle
        _rect(s, 4, 14, 3, 7, p["legs"])
        _rect(s, 4, 21, 3, 3, p["boots"])
        _rect(s, 9, 15, 3, 6, p["legs"])
        _rect(s, 9, 20, 3, 3, p["boots"])
    else:
        _rect(s, 5, 14, 3, 7, p["legs"])
        _rect(s, 8, 14, 3, 7, p["legs"])
        _rect(s, 5, 21, 3, 3, p["boots"])
        _rect(s, 8, 21, 3, 3, p["boots"])
    return _upscale(s, 4)


def _enemy_back_sprite(p, base):
    """Vue de dos : casque plein (pas de visage), sac à dos, arme invisible."""
    heavy = p.get("bulk", False)
    s = pygame.Surface((16, 24), pygame.SRCALPHA)
    # tête : casque/cheveux pleins + nuque
    _rect(s, 5, 0, 6, 4, p["top"])
    _rect(s, 5, 4, 6, 2, p["skin"])
    # torse + sac à dos
    bx, bw = (3, 10) if heavy else (4, 8)
    _rect(s, bx, 6, bw, 7, p["suit"])
    _rect(s, 6, 7, 4, 5, p["dark"])              # sac
    _rect(s, bx, 12, bw, 1, p["dark"])
    if heavy:
        _rect(s, 2, 5, 3, 2, p["dark"])
        _rect(s, 11, 5, 3, 2, p["dark"])
    swing = {"walk": 1, "walk2": -1}.get(base, 0)
    _rect(s, 2, 6 + swing, 2, 6, p["dark"])      # bras
    _rect(s, 12, 6 - swing, 2, 6, p["dark"])
    if base == "walk":
        _rect(s, 4, 15, 3, 6, p["legs"])
        _rect(s, 4, 20, 3, 3, p["boots"])
        _rect(s, 9, 14, 3, 7, p["legs"])
        _rect(s, 9, 21, 3, 3, p["boots"])
    elif base == "walk2":
        _rect(s, 4, 14, 3, 7, p["legs"])
        _rect(s, 4, 21, 3, 3, p["boots"])
        _rect(s, 9, 15, 3, 6, p["legs"])
        _rect(s, 9, 20, 3, 3, p["boots"])
    else:
        _rect(s, 5, 14, 3, 7, p["legs"])
        _rect(s, 8, 14, 3, 7, p["legs"])
        _rect(s, 5, 21, 3, 3, p["boots"])
        _rect(s, 8, 21, 3, 3, p["boots"])
    return _upscale(s, 4)


def _enemy_side_sprite(p, base):
    """Profil (tourné vers la droite) : arme pointée vers l'avant.

    La vue de l'autre profil est obtenue par miroir (assets.get flipped).
    Cycle de marche : jambes en ciseaux (walk) puis passage (walk2).
    """
    heavy = p.get("bulk", False)
    s = pygame.Surface((16, 24), pygame.SRCALPHA)
    # tête de profil
    _rect(s, 6, 0, 6, 2, p["top"])
    _rect(s, 6, 2, 6, 4, p["skin"])
    if p["accent"]:
        _rect(s, 9, 3, 3, 1, p["accent"])        # visière vers l'avant
    else:
        s.set_at((10, 3), (28, 28, 28))          # œil vers l'avant
    # torse (plus étroit de profil)
    bw = 8 if heavy else 6
    _rect(s, 5, 6, bw, 7, p["suit"])
    _rect(s, 5, 12, bw, 1, p["dark"])
    if heavy:
        _rect(s, 5, 5, 4, 2, p["dark"])          # épaulière visible
    # bras visible + arme vers l'avant
    _rect(s, 7, 7, 3, 5, p["dark"])
    _rect(s, 9, 9, 6, 2, (34, 34, 38))           # canon
    _rect(s, 8, 11, 2, 2, p["skin"])             # main
    # jambes de profil : grand écart (walk) / jambes croisées (walk2)
    if base == "walk":
        _rect(s, 4, 14, 3, 7, p["legs"])
        _rect(s, 9, 14, 3, 7, p["legs"])
        _rect(s, 3, 21, 3, 3, p["boots"])
        _rect(s, 10, 21, 3, 3, p["boots"])
    elif base == "walk2":
        _rect(s, 6, 14, 3, 7, p["legs"])
        _rect(s, 8, 15, 2, 6, p["dark"])
        _rect(s, 6, 21, 3, 3, p["boots"])
        _rect(s, 8, 20, 2, 3, p["boots"])
    else:
        _rect(s, 6, 14, 3, 7, p["legs"])
        _rect(s, 8, 14, 2, 7, p["dark"])
        _rect(s, 6, 21, 4, 3, p["boots"])
    return _upscale(s, 4)


def _enemy_dead_sprite(p):
    """Cadavre allongé au sol (24x12) : flaque de sang + silhouette couchée."""
    s = pygame.Surface((24, 12), pygame.SRCALPHA)
    # flaque de sang
    _rect(s, 3, 8, 19, 3, (96, 14, 16))
    _rect(s, 5, 7, 14, 1, (96, 14, 16))
    _rect(s, 6, 11, 12, 1, (70, 10, 12))
    # corps couché : jambes à gauche, tête à droite
    _rect(s, 2, 6, 7, 3, p["legs"])
    _rect(s, 1, 6, 2, 3, p["boots"])
    _rect(s, 9, 5, 8, 4, p["suit"])
    _rect(s, 12, 3, 3, 2, p["dark"])       # bras replié
    _rect(s, 17, 5, 4, 4, p["skin"])       # tête
    _rect(s, 20, 5, 1, 4, p["top"])
    return _upscale(s, 4)


# ----------------------------------------------------------------------
# Armes vues à la première personne (32x24, agrandies x6)
# ----------------------------------------------------------------------
GUN_DARK = (40, 40, 46)
GUN_MID = (66, 66, 76)
WOOD = (122, 88, 50)
SKIN = (204, 162, 122)


def _fp_base():
    return pygame.Surface((32, 24), pygame.SRCALPHA)


def _fp_pistol():
    s = _fp_base()
    _rect(s, 14, 6, 4, 9, GUN_MID)               # glissière
    _rect(s, 15, 4, 2, 3, GUN_DARK)              # canon
    _rect(s, 13, 15, 6, 8, (86, 62, 40))         # crosse
    _rect(s, 11, 15, 2, 5, SKIN)                 # mains
    _rect(s, 19, 15, 2, 5, SKIN)
    return _upscale(s, 6)


def _fp_shotgun():
    s = _fp_base()
    _rect(s, 13, 0, 6, 11, GUN_DARK)             # double canon
    _rect(s, 15, 0, 2, 11, GUN_MID)
    _rect(s, 12, 11, 8, 4, WOOD)                 # pompe
    _rect(s, 13, 15, 6, 9, (100, 70, 40))        # fût
    _rect(s, 10, 12, 2, 5, SKIN)
    _rect(s, 20, 12, 2, 5, SKIN)
    return _upscale(s, 6)


def _fp_rifle():
    s = _fp_base()
    _rect(s, 14, 0, 4, 9, GUN_DARK)              # canon
    _rect(s, 13, 3, 6, 2, GUN_MID)               # viseur
    _rect(s, 12, 9, 8, 8, GUN_MID)               # corps
    _rect(s, 14, 17, 4, 7, GUN_DARK)             # chargeur
    _rect(s, 10, 12, 2, 5, SKIN)
    _rect(s, 20, 14, 2, 5, SKIN)
    return _upscale(s, 6)


def _fp_minigun():
    s = _fp_base()
    for x in (10, 15, 20):                       # trois canons
        _rect(s, x, 0, 2, 11, GUN_MID)
        _rect(s, x, 0, 1, 11, (96, 96, 108))
    _rect(s, 8, 11, 16, 7, GUN_DARK)             # bloc rotatif
    _rect(s, 9, 12, 14, 1, (96, 96, 108))
    _rect(s, 7, 18, 3, 5, SKIN)                  # poignées tenues
    _rect(s, 22, 18, 3, 5, SKIN)
    return _upscale(s, 6)


# ----------------------------------------------------------------------
# Objets à ramasser (16x16, agrandis x4) : armes vues de côté, soins
# ----------------------------------------------------------------------
def _pk_base():
    return pygame.Surface((16, 16), pygame.SRCALPHA)


def _pickup_pistol():
    s = _pk_base()
    _rect(s, 3, 6, 9, 2, GUN_MID)
    _rect(s, 9, 8, 3, 5, (86, 62, 40))
    return _upscale(s, 4)


def _pickup_shotgun():
    s = _pk_base()
    _rect(s, 1, 6, 11, 2, GUN_DARK)
    _rect(s, 12, 6, 3, 3, WOOD)                  # crosse
    _rect(s, 4, 8, 4, 2, WOOD)                   # pompe
    return _upscale(s, 4)


def _pickup_rifle():
    s = _pk_base()
    _rect(s, 1, 6, 11, 2, GUN_DARK)
    _rect(s, 12, 6, 3, 3, GUN_MID)
    _rect(s, 6, 8, 3, 4, GUN_MID)                # chargeur
    _rect(s, 3, 4, 4, 2, GUN_MID)                # viseur
    return _upscale(s, 4)


def _pickup_minigun():
    s = _pk_base()
    for y in (5, 7, 9):
        _rect(s, 1, y, 10, 1, GUN_MID)
    _rect(s, 11, 4, 4, 8, GUN_DARK)
    return _upscale(s, 4)


def _pickup_medkit():
    s = _pk_base()
    _rect(s, 2, 4, 12, 9, (230, 230, 232))
    _rect(s, 2, 4, 12, 1, (180, 180, 184))
    _rect(s, 7, 6, 2, 5, (212, 42, 42))          # croix rouge
    _rect(s, 5, 8, 6, 2, (212, 42, 42))
    return _upscale(s, 4)


def _pickup_lifepack():
    """Pack de vie caché : gros bloc blanc, grande croix rouge, lueur verte."""
    s = _pk_base()
    _rect(s, 1, 2, 14, 12, (242, 242, 244))
    _rect(s, 1, 2, 14, 1, (190, 190, 194))       # arête supérieure
    _rect(s, 1, 13, 14, 1, (200, 200, 204))
    _rect(s, 6, 4, 4, 8, (206, 32, 32))          # grande croix
    _rect(s, 4, 6, 8, 4, (206, 32, 32))
    for px, py in ((0, 1), (15, 1), (0, 14), (15, 14)):
        s.set_at((px, py), (120, 235, 130))      # lueur verte aux coins
    return _upscale(s, 4)


# ----------------------------------------------------------------------
_BUILDERS = {
    "wall_brick": _tex_brick,
    "wall_crate": _tex_crate,
    "wall_stone": _tex_stone,
    "wall_metal": _tex_metal,
    "wall_tech": _tex_tech,
    "wall_door": _tex_door,
    "fp_pistol": _fp_pistol,
    "fp_shotgun": _fp_shotgun,
    "fp_rifle": _fp_rifle,
    "fp_minigun": _fp_minigun,
    "pickup_pistol": _pickup_pistol,
    "pickup_shotgun": _pickup_shotgun,
    "pickup_rifle": _pickup_rifle,
    "pickup_minigun": _pickup_minigun,
    "pickup_medkit": _pickup_medkit,
    "pickup_lifepack": _pickup_lifepack,
}
for _kind in ENEMY_PALETTES:
    for _pose in ("idle", "walk", "walk2", "fire", "dead",
                  "idle_back", "walk_back", "walk2_back",
                  "idle_side", "walk_side", "walk2_side"):
        _BUILDERS[f"enemy_{_kind}_{_pose}"] = (
            lambda k=_kind, p=_pose: _enemy_sprite(k, p)
        )


def generate_all():
    """Régénère tous les PNG dans assets/ (écrase les fichiers existants)."""
    os.makedirs(ASSET_DIR, exist_ok=True)
    for name, builder in _BUILDERS.items():
        pygame.image.save(builder(), os.path.join(ASSET_DIR, name + ".png"))
        print("assets/" + name + ".png")


if __name__ == "__main__":
    pygame.init()
    generate_all()
