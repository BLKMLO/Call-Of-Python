"""Carte du jeu.

La carte est une grille de caractères :
    '1', '2', '3' : murs (différentes couleurs)
    '.'           : sol praticable
    'P'           : point d'apparition du joueur
    'E'           : point d'apparition d'un ennemi

Pour ajouter une nouvelle map, il suffit de définir une autre liste de
chaînes (toutes les lignes de même longueur) et de la passer au
constructeur de `Level`.
"""

# Map de test (22 x 16) : une arène avec des salles, couloirs et piliers
# qui servent de couverture aux ennemis.
TEST_MAP = [
    "1111111111111111111111",
    "1P...........2......E1",
    "1....11......2.......1",
    "1....11......2..333..1",
    "1............2..3.3..1",
    "1....................1",
    "1..22222.....11..11..1",
    "1..2...2.............1",
    "1..2...2....E........1",
    "1..22.22.............1",
    "1............33333...1",
    "1...E............3...1",
    "1........11......3..E1",
    "1........11..........1",
    "1..E.................1",
    "1111111111111111111111",
]


class Level:
    """Grille de collision + points d'apparition, construits depuis la map ASCII."""

    def __init__(self, grid=None):
        grid = grid if grid is not None else TEST_MAP
        self.grid = [list(row) for row in grid]
        self.height = len(self.grid)
        self.width = len(self.grid[0])

        self.player_spawn = (1.5, 1.5)
        self.enemy_spawns = []
        for y, row in enumerate(self.grid):
            for x, char in enumerate(row):
                if char == "P":
                    self.player_spawn = (x + 0.5, y + 0.5)
                    self.grid[y][x] = "."
                elif char == "E":
                    self.enemy_spawns.append((x + 0.5, y + 0.5))
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
