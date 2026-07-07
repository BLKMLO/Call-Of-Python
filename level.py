"""Cartes et niveaux du jeu.

Une carte est une grille de caractères :
    '1', '2', '3' : murs — leur texture dépend du thème du niveau
    '.'           : sol praticable
    'P'           : apparition du joueur
    'E'           : apparition d'un ennemi (type selon la composition du niveau)
    'B'           : apparition du boss (le Colosse)
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
    "1........2..222..2.E.1",
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
    "122.222..3...3..222.2221",
    "1........3.H.3.........1",
    "1...E....33.33....E....1",
    "1......................1",
    "1..33..............33..1",
    "1..33....E....E....33..1",
    "1......................1",
    "122.222.........222.2221",
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
    "1....22.3333.3333.22.....1",
    "1........................1",
    "1..E.....................1",
    "1....33..2.E..W.2..33....1",
    "1....3...2......2...3.E..1",
    "1....3...22.11.22...3....1",
    "1....33.....11.....33....1",
    "1..H.....................1",
    "1.........E....E.........1",
    "1..222.222......222.222..1",
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
    "1222.222...3....3.222.2221",
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
    """Grille de collision + points d'apparition, construits depuis la carte."""

    def __init__(self, level_index=0):
        self.index = level_index
        self.config = LEVELS[level_index]
        self.name = self.config["name"]
        self.grid = [list(row) for row in self.config["grid"]]
        self.height = len(self.grid)
        self.width = len(self.grid[0])

        self.player_spawn = (1.5, 1.5)
        self.enemy_spawns = []     # [(x, y, type_d_ennemi)]
        self.pickup_spawns = []    # [(x, y, "weapon:<id>" | "medkit")]
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
                elif char == "W":
                    wid = weapon_ids[n_weapon % len(weapon_ids)]
                    self.pickup_spawns.append((cx, cy, "weapon:" + wid))
                    n_weapon += 1
                elif char == "H":
                    self.pickup_spawns.append((cx, cy, "medkit"))
                if char in "PEBWH":
                    self.grid[y][x] = "."

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
        return self.tile(x, y) != "."

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
