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
# Textures de murs (dessinées en 16x16, agrandies x4 -> 64x64)
# ----------------------------------------------------------------------
def _tex_base():
    return pygame.Surface((16, 16))


def _tex_brick():
    """Mur de briques rouges."""
    rng = random.Random(101)
    s = _tex_base()
    _rect(s, 0, 0, 16, 16, (74, 66, 62), rng, 6)          # mortier
    brick = (150, 74, 56)
    for row in range(4):
        y = row * 4 + 1
        offset = 0 if row % 2 == 0 else 4
        for bx in range(-1, 3):
            _rect(s, bx * 8 + offset, y, 7, 3, brick, rng, 12)
    return _upscale(s, 4)


def _tex_crate():
    """Caisse en bois (planches + cadre)."""
    rng = random.Random(102)
    s = _tex_base()
    _rect(s, 0, 0, 16, 16, (150, 112, 62), rng, 10)       # planches
    for y in (3, 7, 11):                                  # rainures
        _rect(s, 0, y, 16, 1, (104, 76, 40), rng, 6)
    _rect(s, 0, 0, 16, 1, (112, 82, 44), rng, 6)          # cadre
    _rect(s, 0, 15, 16, 1, (112, 82, 44), rng, 6)
    _rect(s, 0, 0, 1, 16, (112, 82, 44), rng, 6)
    _rect(s, 15, 0, 1, 16, (112, 82, 44), rng, 6)
    return _upscale(s, 4)


def _tex_stone():
    """Pierres grises irrégulières."""
    rng = random.Random(103)
    s = _tex_base()
    _rect(s, 0, 0, 16, 16, (52, 52, 58), rng, 4)          # joints
    for y in (0, 5, 10):
        x = -rng.randint(0, 2)
        while x < 16:
            w = rng.randint(3, 6)
            _rect(s, x, y, w - 1, 4 if y < 10 else 5, (124, 126, 132), rng, 10)
            x += w
    return _upscale(s, 4)


def _tex_metal():
    """Panneau métallique riveté."""
    rng = random.Random(104)
    s = _tex_base()
    _rect(s, 0, 0, 16, 16, (108, 112, 124), rng, 6)
    _rect(s, 0, 7, 16, 2, (84, 88, 100), rng, 5)          # rainure centrale
    _rect(s, 0, 0, 16, 1, (130, 134, 146), rng, 5)        # arête claire
    for px, py in ((1, 2), (14, 2), (1, 13), (14, 13)):   # rivets
        s.set_at((px, py), (176, 180, 192))
    return _upscale(s, 4)


def _tex_tech():
    """Panneau high-tech sombre avec lignes lumineuses (laboratoire)."""
    rng = random.Random(105)
    s = _tex_base()
    _rect(s, 0, 0, 16, 16, (42, 47, 58), rng, 5)
    _rect(s, 0, 7, 16, 1, (30, 34, 44), rng, 3)           # jointure
    _rect(s, 7, 0, 1, 16, (30, 34, 44), rng, 3)
    _rect(s, 2, 3, 5, 1, (86, 220, 230))                  # lignes néon
    _rect(s, 10, 11, 4, 1, (86, 220, 230))
    s.set_at((12, 3), (240, 90, 90))                      # diodes
    s.set_at((3, 12), (110, 235, 130))
    return _upscale(s, 4)


def _tex_door():
    """Porte coulissante métallique avec bandes de signalisation."""
    rng = random.Random(106)
    s = _tex_base()
    _rect(s, 0, 0, 16, 16, (86, 92, 104), rng, 5)         # panneau
    _rect(s, 7, 0, 2, 16, (56, 60, 70), rng, 3)           # jointure centrale
    _rect(s, 0, 0, 1, 16, (120, 126, 140))                # rails latéraux
    _rect(s, 15, 0, 1, 16, (120, 126, 140))
    for x in range(1, 15, 2):                             # bandes jaune/noir
        _rect(s, x, 2, 1, 2, (214, 176, 40))
        _rect(s, x + 1, 2, 1, 2, (40, 38, 30))
        _rect(s, x, 12, 1, 2, (214, 176, 40))
        _rect(s, x + 1, 12, 1, 2, (40, 38, 30))
    s.set_at((3, 8), (110, 235, 130))                     # voyant d'ouverture
    return _upscale(s, 4)


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
}


def _enemy_sprite(kind, pose):
    """Sprite d'ennemi : poses de face (idle/walk/fire), de dos
    (idle_back/walk_back), de profil (idle_side/walk_side) et au sol (dead)."""
    p = ENEMY_PALETTES[kind]
    if pose == "dead":
        return _enemy_dead_sprite(p)
    if pose.endswith("_back"):
        return _enemy_back_sprite(p, walk=pose.startswith("walk"))
    if pose.endswith("_side"):
        return _enemy_side_sprite(p, walk=pose.startswith("walk"))
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
        swing = 1 if pose == "walk" else 0
        _rect(s, 2, 6 + swing, 2, 6, p["dark"])              # bras gauche
        _rect(s, 12, 6 - swing, 2, 6, p["dark"])             # bras droit
        _rect(s, 2, 11 + swing, 2, 1, p["skin"])             # mains
        _rect(s, 12, 10 + swing, 2, 1, p["skin"])

    if pose == "walk":                                        # jambes écartées
        _rect(s, 4, 14, 3, 7, p["legs"])
        _rect(s, 9, 14, 3, 7, p["legs"])
        _rect(s, 4, 21, 3, 3, p["boots"])
        _rect(s, 9, 21, 3, 3, p["boots"])
    else:
        _rect(s, 5, 14, 3, 7, p["legs"])
        _rect(s, 8, 14, 3, 7, p["legs"])
        _rect(s, 5, 21, 3, 3, p["boots"])
        _rect(s, 8, 21, 3, 3, p["boots"])
    return _upscale(s, 4)


def _enemy_back_sprite(p, walk):
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
    swing = 1 if walk else 0
    _rect(s, 2, 6 + swing, 2, 6, p["dark"])      # bras
    _rect(s, 12, 6 - swing, 2, 6, p["dark"])
    if walk:
        _rect(s, 4, 14, 3, 7, p["legs"])
        _rect(s, 9, 14, 3, 7, p["legs"])
        _rect(s, 4, 21, 3, 3, p["boots"])
        _rect(s, 9, 21, 3, 3, p["boots"])
    else:
        _rect(s, 5, 14, 3, 7, p["legs"])
        _rect(s, 8, 14, 3, 7, p["legs"])
        _rect(s, 5, 21, 3, 3, p["boots"])
        _rect(s, 8, 21, 3, 3, p["boots"])
    return _upscale(s, 4)


def _enemy_side_sprite(p, walk):
    """Profil (tourné vers la droite) : arme pointée vers l'avant.

    La vue de l'autre profil est obtenue par miroir (assets.get flipped).
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
    # jambes de profil (ciseaux en marche)
    if walk:
        _rect(s, 4, 14, 3, 7, p["legs"])
        _rect(s, 9, 14, 3, 7, p["legs"])
        _rect(s, 3, 21, 3, 3, p["boots"])
        _rect(s, 10, 21, 3, 3, p["boots"])
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
}
for _kind in ENEMY_PALETTES:
    for _pose in ("idle", "walk", "fire", "dead",
                  "idle_back", "walk_back", "idle_side", "walk_side"):
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
