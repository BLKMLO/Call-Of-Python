"""Cartes et niveaux du jeu.

Une carte est une grille de caractères :
    '1', '2', '3' : murs — leur texture dépend du thème du niveau
    'D'           : porte coulissante automatique (s'ouvre à l'approche)
    '.'           : sol praticable
    'P'           : apparition du joueur
    'E'           : apparition d'un ennemi (type selon la composition du niveau)
    'B'           : apparition du boss (le Colosse, alias le Sceau)
    'S'           : point d'apparition de la horde (mode Déferlement)
    'W'           : arme à ramasser (type selon la liste `weapons` du niveau)
    'H'           : trousse de soins
    '+'           : pack de vie caché (rare, soin complet, hors minimap)
    décors        : 'c' voiture, 'n' pupitres, 't' tribune, 'm' paillasse,
                    'r' rocher, 'V' crevasse luisante, 'o' portail —
                    billboards qui bloquent le passage (mais pas les balles
                    ni les regards)
    'G'           : mur d'énergie (limite du monde lunaire) — bloque tout,
                    mais n'est rendu que lorsqu'on s'en approche

Campagne : Entrepôt → Métropole → Gouvernement → Base militaire →
Laboratoire (l'assaut final, où le Sceau attend). Le Déferlement se joue
ensuite sur la Lune. Chaque niveau définit sa carte, son thème visuel,
sa composition d'ennemis, ses armes au sol et sa difficulté.
"""

# Décor associé à chaque caractère de carte.
PROP_CHARS = {"c": "car", "n": "bench", "t": "tribune",
              "m": "labtable", "r": "rock", "V": "fissure", "o": "portal"}

MAP_WAREHOUSE = [
    "111111111111111111111111111111",
    "1P...................2222222.1",
    "1....................2..H..2.1",
    "1....................2.....2.1",
    "1....................22D2222.1",
    "1............................1",
    "1..4444444444..4444444444....1",
    "1......E...........E.........1",
    "1..........................W.1",
    "1..4444444444..4444444444....1",
    "1....E.......................1",
    "1.............E..............1",
    "1.H..........................1",
    "1..4444444444..4444444444....1",
    "1........E...........W.......1",
    "1............................1",
    "1..4444444444..4444444444....1",
    "1................E...........1",
    "1............................1",
    "1...22....2..E..2.....22...H.1",
    "1......E...............2....+1",
    "111111111111111111111111111111",
]

# Métropole : gratte-ciel ('1'), commerces en brique ('2'), le périmètre
# est bouclé par des barrières anti-émeute ('3') entre les immeubles.
# Voitures abandonnées dans les rues, kiosque au centre.
MAP_CITY = [
    "333333333333333333333333333333",
    "3P...........c...............3",
    "3...11.2D22.......11....11...3",
    "3...11.2HW2...E...11....11..H3",
    "3.H.11.2..2.......11.........3",
    "3......2222...........E......3",
    "3.E......E..........c........3",
    "3.....c.................c...E3",
    "3..11................11......3",
    "3.W11..2D221...E.....11...11.3",
    "3..11..2WH21......E..11...11.3",
    "3......2..21..............11c3",
    "3.....E2222...E..............3",
    "3.c......c.......c......E....3",
    "3.........11.c.......11....E.3",
    "3...2D22..11.........11......3",
    "3...2.E2..11...2D22..11......3",
    "3.E.2H.2..11...2W.2......11.W3",
    "3...2222.......2.E2......11..3",
    "3H.......E...E.2222......11E.3",
    "3+E.................E.......H3",
    "333333333333333333333333333333",
]

# Gouvernement : hémicycle de marbre et de boiseries — tribune ('t'),
# rangées de pupitres ('n'), bureaux latéraux fermés par des portes.
MAP_GOV = [
    "111111111111111111111111111",
    "111111111111111111111111111",
    "1111111111.......1111111111",
    "11111111.....W.....11111111",
    "111111............E..111111",
    "11111.................11111",
    "1111.......22D22.......1111",
    "1111..E..22.....22..E..1111",
    "111.....22.n..n..22.....111",
    "111....22...n.....22....111",
    "11.....2...E.......2.....11",
    "11....2.n.n....n.n..2....11",
    "11....2.............2....11",
    "11.H..D......t......D..W.11",
    "11....2.n.n....n.n..2....11",
    "11....2.........E...2....11",
    "11.....2..E..n.....2.....11",
    "111....22..n..n...22....111",
    "111.....22.......22.....111",
    "1111.....22.....22..E..1111",
    "1111..E....22D22.......1111",
    "11111................+11111",
    "111111..E............111111",
    "11111111.....H.....11111111",
    "1111111111...P...1111111111",
    "111111111111111111111111111",
    "111111111111111111111111111",
]

MAP_BASE = [
    "111111111111111111111111",
    "1P....2.........2......1",
    "1.....2....E....2..E...1",
    "1..W..2.........2......1",
    "1.....2..33333..2......1",
    "122D222..3...3..222D2221",
    "1........3.H.3.........1",
    "1...E....33.33....E....1",
    "1.........E............1",
    "1..33..............33..1",
    "1..33....E....E....33..1",
    "1....E....H............1",
    "122D222.........222D2221",
    "1.....2....W....2....E.1",
    "1..E..2..11D111.2...E..1",
    "1.....2..1.+..1.2......1",
    "1..H..2..1....1.2......1",
    "111111111111111111111111",
]

# Laboratoire : l'assaut final. Le Colosse ('B') garde le cœur du
# complexe, entre les paillasses ('m') chargées d'éprouvettes.
MAP_LAB = [
    "111111111111111111111111111111",
    "1.......2.......2......2.....1",
    "1.......2.....W.2......2..H..1",
    "1..3.3..2.......2..33332..m..1",
    "1.m.....2.mmmm..2......2.E...1",
    "1.....m.2.......2......D.....1",
    "1..3.3..2.......2..33332.....1",
    "1.......2..E....2......2.E...1",
    "1...E...2.....E.2....E.2...E.1",
    "1.......2.......2......2.....1",
    "1222D2222222D2222222D22......1",
    "1................E...........1",
    "1.P....E................E....1",
    "1............................1",
    "12222D22222222D222222222.....1",
    "1.........2........2.........1",
    "1.....E...2........2.333333331",
    "1..22.....2.m...m..2.3.E...H31",
    "1.........2........2.D......31",
    "1.W....2..2....E...2.3...B..31",
    "1.........2.H......2.D......31",
    "1..2....2.2......+.2.3....E.31",
    "1.........2........2.333333331",
    "111111111111111111111111111111",
]

# Arène du Déferlement, sur la Lune : régolithe et cratères, sas
# d'invasion aux coins, rochers épars, ciel noir étoilé.
MAP_MOON = [
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
    "G............................G",
    "G.+..........................G",
    "G.................VV.........G",
    "G..............H......V......G",
    "G....VV................V.....G",
    "G......V.....................G",
    "G............................G",
    "G............................G",
    "G........V....SS.............G",
    "G.......V............V.......G",
    "G...........S....S....V......G",
    "G..W........S..o.S........W..G",
    "G............................G",
    "G.............SS.............G",
    "G............................G",
    "G...V........................G",
    "G....V..................VV...G",
    "G....V....................V..G",
    "G............................G",
    "G..........VV..H.............G",
    "G..............P.............G",
    "G............................G",
    "GGGGGGGGGGGGGGGGGGGGGGGGGGGGGG",
]

# Configuration du mode survie (hors progression des LEVELS).
SURVIVAL_LEVEL = {
    "name": "Le Déferlement",
    "survival": True,
    "grid": MAP_MOON,
    "theme": {"G": "wall_energy"},
    "heights": {"G": 1.25},
    "portal": (15.5, 12.5),                      # cœur du Déferlement
    "sky": ((3, 3, 8), (12, 12, 20)),           # nuit lunaire...
    "stars": True,                               # ... constellée d'étoiles
    "floor": ((96, 96, 102), (48, 48, 54)),      # régolithe gris
    "enemies": [],                               # gérés par les vagues
    "weapons": ["rifle", "minigun"],
    "enemy_health_mult": 1.0,                    # écrasés par la vague
    "enemy_damage_mult": 1.0,
}

# Chaque niveau : carte, thème visuel, composition des ennemis (cyclée sur
# les 'E' de la carte), armes au sol (cyclées sur les 'W'), multiplicateurs.
LEVELS = [
    {
        "name": "Entrepôt",
        "grid": MAP_WAREHOUSE,
        "theme": {"1": "wall_brick", "2": "wall_crate", "3": "wall_metal",
                  "4": "wall_shelf"},
        "heights": {"4": 1.5},
        "sun": {"hour": 8, "az": -0.7, "el": 0.44, "color": (255, 214, 150)},
        "sky": ((30, 32, 48), (66, 60, 70)),      # dégradé haut -> horizon
        "floor": ((60, 54, 48), (34, 32, 30)),    # dégradé horizon -> bas
        "enemies": ["grunt"],
        "weapons": ["shotgun"],
        "enemy_health_mult": 1.0,
        "enemy_damage_mult": 1.0,
    },
    {
        "name": "Métropole",
        "grid": MAP_CITY,
        "theme": {"1": "wall_tower", "2": "wall_brick", "3": "wall_barrier"},
        "heights": {"1": 3.4, "3": 0.6},   # commerces (2) à hauteur normale
        "sun": {"hour": 11, "az": -0.5, "el": 0.82, "color": (255, 240, 200)},
        "sky": ((18, 16, 36), (88, 62, 84)),      # crépuscule urbain
        "floor": ((52, 52, 58), (28, 28, 32)),    # asphalte
        "enemies": ["grunt", "grunt", "soldier"],
        "weapons": ["rifle", "shotgun"],
        "enemy_health_mult": 1.15,
        "enemy_damage_mult": 1.1,
    },
    {
        "name": "Gouvernement",
        "grid": MAP_GOV,
        "theme": {"1": "wall_marble", "2": "wall_govwood", "3": "wall_marble"},
        "heights": {"1": 2.4},             # murs de salle (2, à portes) hauteur 1
        "sun": {"hour": 14, "az": 0.15, "el": 0.92, "color": (255, 250, 235)},
        "sky": ((44, 38, 32), (86, 74, 60)),      # plafond d'apparat
        "floor": ((104, 96, 84), (52, 48, 42)),   # dalles de marbre
        "enemies": ["soldier", "sniper", "grunt"],
        "weapons": ["shotgun", "rifle"],
        "enemy_health_mult": 1.3,
        "enemy_damage_mult": 1.2,
    },
    {
        "name": "Base militaire",
        "grid": MAP_BASE,
        "theme": {"1": "wall_stone", "2": "wall_metal", "3": "wall_crate"},
        "sky": ((22, 26, 40), (52, 60, 84)),
        "floor": ((58, 60, 56), (30, 32, 30)),
        "sun": {"hour": 16, "az": 0.55, "el": 0.6, "color": (255, 226, 168)},
        "enemies": ["soldier", "kamikaze", "heavy"],
        "weapons": ["rifle", "minigun"],
        "enemy_health_mult": 1.5,
        "enemy_damage_mult": 1.35,
    },
    {
        "name": "Laboratoire — Assaut final",
        "grid": MAP_LAB,
        "theme": {"1": "wall_tech", "2": "wall_metal", "3": "wall_stone"},
        # Enceinte technique légèrement surélevée et murs de confinement
        # renforcés autour des salles sensibles et de la chambre du Colosse.
        "heights": {"1": 1.25, "3": 1.55},
        "sky": ((44, 22, 18), (150, 70, 44)),   # crépuscule rougeoyant (19h)
        "floor": ((58, 40, 36), (26, 20, 20)),
        "sun": {"hour": 19, "az": 0.8, "el": 0.1, "color": (255, 120, 60)},
        "enemies": ["heavy", "sniper", "kamikaze"],
        "weapons": ["minigun", "rifle"],
        "enemy_health_mult": 1.7,
        "enemy_damage_mult": 1.5,
    },
]


class Level:
    """Grille de collision + points d'apparition + portes + décors."""

    DOOR_SPEED = 1.6        # vitesse d'ouverture (fraction / s)
    DOOR_TRIGGER = 1.6      # distance de déclenchement automatique

    def __init__(self, level_index=0, config=None):
        self.index = level_index
        self.config = config if config is not None else LEVELS[level_index]
        self.name = self.config["name"]
        self.is_survival = bool(self.config.get("survival"))
        self.grid = [list(row) for row in self.config["grid"]]
        self.height = len(self.grid)
        self.width = len(self.grid[0])

        self.player_spawn = (1.5, 1.5)
        self.enemy_spawns = []     # [(x, y, type_d_ennemi)]
        self.pickup_spawns = []    # [(x, y, "weapon:<id>" | "medkit" | ...)]
        self.horde_spawns = []     # [(x, y)] points d'invasion (survie)
        self.prop_spawns = []      # [(x, y, type_de_décor)]
        self.prop_tiles = set()    # cases occupées par un décor (bloquantes)
        self.doors = {}            # {(x, y): {"open": 0..1, "opening": bool}}
        enemy_kinds = self.config["enemies"]
        weapon_ids = self.config["weapons"]
        n_enemy, n_weapon = 0, 0
        for y, row in enumerate(self.grid):
            for x, char in enumerate(row):
                cx, cy = x + 0.5, y + 0.5
                if char == "P":
                    self.player_spawn = (cx, cy)
                elif char == "E":
                    kind = enemy_kinds[n_enemy % len(enemy_kinds)]
                    self.enemy_spawns.append((cx, cy, kind))
                    n_enemy += 1
                elif char == "B":
                    self.enemy_spawns.append((cx, cy, "boss"))
                elif char == "S":
                    self.horde_spawns.append((cx, cy))
                elif char == "W":
                    wid = weapon_ids[n_weapon % len(weapon_ids)]
                    self.pickup_spawns.append((cx, cy, "weapon:" + wid))
                    n_weapon += 1
                elif char == "H":
                    self.pickup_spawns.append((cx, cy, "medkit"))
                elif char == "+":
                    self.pickup_spawns.append((cx, cy, "lifepack"))
                elif char in PROP_CHARS:
                    self.prop_spawns.append((cx, cy, PROP_CHARS[char]))
                    self.prop_tiles.add((x, y))
                elif char == "D":
                    self.doors[(x, y)] = {"open": 0.0, "opening": False}
                if char in "PEBSWH+" or char in PROP_CHARS:
                    self.grid[y][x] = "."

    # ------------------------------------------------------------------
    # Portes coulissantes
    # ------------------------------------------------------------------
    def door_open_at(self, x, y):
        """Fraction d'ouverture (0 fermée → 1 ouverte) de la porte en (x, y)."""
        door = self.doors.get((int(x), int(y)))
        return door["open"] if door else 0.0

    def update_doors(self, dt, entities):
        """Ouvre les portes à l'approche d'une entité, les referme sinon.

        Retourne les positions des portes qui commencent à bouger (sons).
        """
        events = []
        for (x, y), door in self.doors.items():
            cx, cy = x + 0.5, y + 0.5
            near = any(
                abs(e.x - cx) < self.DOOR_TRIGGER and abs(e.y - cy) < self.DOOR_TRIGGER
                for e in entities)
            if near != door["opening"]:
                door["opening"] = near
                events.append((cx, cy))
            target = 1.0 if near else 0.0
            if door["open"] < target:
                door["open"] = min(1.0, door["open"] + self.DOOR_SPEED * dt)
            elif door["open"] > target:
                door["open"] = max(0.0, door["open"] - self.DOOR_SPEED * dt)
        return events

    # ------------------------------------------------------------------
    # Requêtes sur la grille
    # ------------------------------------------------------------------
    def tile(self, x, y):
        """Caractère de la case contenant le point (x, y) ; mur hors limites."""
        ix, iy = int(x), int(y)
        if 0 <= ix < self.width and 0 <= iy < self.height:
            return self.grid[iy][ix]
        return "1"

    def is_wall(self, x, y):
        """Bloque les déplacements : une porte compte tant qu'elle n'est pas
        presque entièrement ouverte ; les décors (voitures, pupitres...)
        bloquent aussi, mais pas les balles (cast_ray lit la grille)."""
        t = self.tile(x, y)
        if t == ".":
            return (int(x), int(y)) in self.prop_tiles
        if t == "D":
            return self.door_open_at(x, y) < 0.9
        return True

    def blocks_path(self, x, y):
        """Pour le pathfinding : les portes sont traversables (elles
        s'ouvriront à l'approche de l'ennemi), les décors non."""
        t = self.tile(x, y)
        if t == ".":
            return (int(x), int(y)) in self.prop_tiles
        return t != "D"

    def can_stand(self, x, y, radius=0.25):
        """Vrai si un cercle de rayon donné centré en (x, y) ne touche aucun mur."""
        for dx in (-radius, radius):
            for dy in (-radius, radius):
                if self.is_wall(x + dx, y + dy):
                    return False
        return True

    def move_with_collisions(self, x, y, dx, dy, radius=0.25):
        """Déplace un cercle en glissant le long des murs (axes traités séparément).

        Retourne la nouvelle position (x, y).
        """
        if self.can_stand(x + dx, y, radius):
            x += dx
        if self.can_stand(x, y + dy, radius):
            y += dy
        return x, y
