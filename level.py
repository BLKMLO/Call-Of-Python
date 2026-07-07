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

Chaque niveau (`LEVELS`) définit sa carte, son thème visuel (textures de
murs, couleurs du ciel et du sol), sa composition d'ennemis et ses armes
au sol. Les ennemis et les armes deviennent plus puissants au fil des
niveaux. Pour ajouter un niveau : une grille + une entrée dans `LEVELS`.
"""

MAP_WAREHOUSE = [
    "1111111111111111111111",
    "1P.......2.......2...1",
    "1........22D222..2.E.1",
    "1..22....2....2..2...1",
    "1...2....2.W..2..222.1",
    "1...2....22222.......1",
    "1...2................1",
    "1.........33.........1",
    "1....E....33....E....1",
    "1....................1",
    "1..222..........222..1",
    "1..2..............2..1",
    "1..2..H....E......2.E1",
    "1..2..............2..1",
    "1....................1",
    "1111111111111111111111",
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
    "1......................1",
    "1..33..............33..1",
    "1..33....E....E....33..1",
    "1......................1",
    "122D222.........222D2221",
    "1.....2....W....2......1",
    "1..E..2..111111.2...E..1",
    "1.....2..1....1.2......1",
    "1..H..2..1....1.2......1",
    "111111111111111111111111",
]

MAP_LAB = [
    "11111111111111111111111111",
    "1P...2..........2........1",
    "1....2....E.....2...E....1",
    "1.W..2..........2........1",
    "1....22.3333D3333.22.....1",
    "1........................1",
    "1..E.....................1",
    "1....33..2.E..W.2..33....1",
    "1....3...2......2...3.E..1",
    "1....3...22.11.22...3....1",
    "1....33.....11.....33....1",
    "1..H.....................1",
    "1.........E....E.........1",
    "1..222D222......222D222..1",
    "1..2.....................1",
    "1..2..E......H.......E...1",
    "1..2.....................1",
    "11111111111111111111111111",
]

MAP_FINAL = [
    "11111111111111111111111111",
    "1P.....2..........2......1",
    "1......2....E.....2..E...1",
    "1..W...2..........2......1",
    "1......2...33..33.2......1",
    "1222D222...3....3.222D2221",
    "1..........3..B.3........1",
    "1...E......3....3....E...1",
    "1..........33..33........1",
    "1.....33..........33.....1",
    "1..H..33....WH....33..H..1",
    "1........................1",
    "1..2222....1111....2222..1",
    "1..2..........E.......2..1",
    "1..2..E...............2..1",
    "1..2.....22....22.....2..1",
    "1..2..H..2......2..E..2..1",
    "1..2.....2......2.....2..1",
    "1........................1",
    "11111111111111111111111111",
]

# Arène du Déferlement (mode survie) : quatre sas d'invasion aux coins
# (poches de 'S' fermées par des portes), abri central, armes au milieu.
MAP_HORDE = [
    "11111111111111111111111111",
    "1SS2..................2SS1",
    "1SSD.......W..........DSS1",
    "1222..................2221",
    "1........................1",
    "1...33..............33...1",
    "1...33......H.......33...1",
    "1........................1",
    "1......333......333......1",
    "1......3..........3......1",
    "1......3....P.....3......1",
    "1......3..........3......1",
    "1......333......333......1",
    "1........................1",
    "1...33......W.......33...1",
    "1...33..............33...1",
    "1222..................2221",
    "1SSD..................DSS1",
    "1SS2.......H..........2SS1",
    "11111111111111111111111111",
]

# Configuration du mode survie (hors progression des LEVELS).
SURVIVAL_LEVEL = {
    "name": "Le Déferlement",
    "survival": True,
    "grid": MAP_HORDE,
    "theme": {"1": "wall_tech", "2": "wall_metal", "3": "wall_stone"},
    "sky": ((10, 6, 16), (74, 24, 30)),        # ciel d'apocalypse
    "floor": ((48, 38, 42), (22, 18, 22)),
    "enemies": [],                              # gérés par les vagues
    "weapons": ["rifle", "minigun"],
    "enemy_health_mult": 1.0,                   # écrasés par la vague
    "enemy_damage_mult": 1.0,
}

# Chaque niveau : carte, thème visuel, composition des ennemis (cyclée sur
# les 'E' de la carte), armes au sol (cyclées sur les 'W'), multiplicateurs.
LEVELS = [
    {
        "name": "Entrepôt",
        "grid": MAP_WAREHOUSE,
        "theme": {"1": "wall_brick", "2": "wall_crate", "3": "wall_metal"},
        "sky": ((30, 32, 48), (66, 60, 70)),      # dégradé haut -> horizon
        "floor": ((60, 54, 48), (34, 32, 30)),    # dégradé horizon -> bas
        "enemies": ["grunt"],
        "weapons": ["shotgun"],
        "enemy_health_mult": 1.0,
        "enemy_damage_mult": 1.0,
    },
    {
        "name": "Base militaire",
        "grid": MAP_BASE,
        "theme": {"1": "wall_stone", "2": "wall_metal", "3": "wall_crate"},
        "sky": ((22, 26, 40), (52, 60, 84)),
        "floor": ((58, 60, 56), (30, 32, 30)),
        "enemies": ["grunt", "soldier", "soldier"],
        "weapons": ["rifle", "shotgun"],
        "enemy_health_mult": 1.25,
        "enemy_damage_mult": 1.2,
    },
    {
        "name": "Laboratoire",
        "grid": MAP_LAB,
        "theme": {"1": "wall_tech", "2": "wall_metal", "3": "wall_stone"},
        "sky": ((12, 16, 26), (34, 52, 66)),
        "floor": ((44, 50, 58), (22, 26, 32)),
        "enemies": ["soldier", "heavy", "soldier"],
        "weapons": ["minigun", "rifle"],
        "enemy_health_mult": 1.5,
        "enemy_damage_mult": 1.4,
    },
    {
        "name": "Assaut final",
        "grid": MAP_FINAL,
        "theme": {"1": "wall_metal", "2": "wall_tech", "3": "wall_brick"},
        "sky": ((16, 10, 14), (66, 30, 26)),      # ciel rougeoyant
        "floor": ((52, 42, 40), (26, 22, 22)),
        "enemies": ["heavy", "soldier", "heavy"],
        "weapons": ["minigun", "rifle"],
        "enemy_health_mult": 1.7,
        "enemy_damage_mult": 1.5,
    },
]


class Level:
    """Grille de collision + points d'apparition + portes, depuis la carte."""

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
        self.pickup_spawns = []    # [(x, y, "weapon:<id>" | "medkit")]
        self.horde_spawns = []     # [(x, y)] points d'invasion (survie)
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
                elif char == "D":
                    self.doors[(x, y)] = {"open": 0.0, "opening": False}
                if char in "PEBSWH":
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
        presque entièrement ouverte."""
        t = self.tile(x, y)
        if t == ".":
            return False
        if t == "D":
            return self.door_open_at(x, y) < 0.9
        return True

    def blocks_path(self, x, y):
        """Pour le pathfinding : les portes sont traversables (elles
        s'ouvriront à l'approche de l'ennemi)."""
        return self.tile(x, y) not in (".", "D")

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
