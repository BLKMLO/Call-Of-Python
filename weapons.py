"""Armes du jeu.

Chaque arme est définie par un `WeaponSpec` (statistiques de base) ; une
`Weapon` est une instance possédée par le joueur, dont les dégâts sont
multipliés selon le niveau où elle a été trouvée ("Mk. II", "Mk. III"...).
Le tir est un hitscan résolu dans `game.py` ; le fusil à pompe tire
plusieurs plombs par coup, chacun avec sa propre dispersion.

Pour ajouter une arme : créer un `WeaponSpec` dans `WEAPON_SPECS`,
l'ajouter à `WEAPON_ORDER`, et dessiner ses sprites `fp_<id>` /
`pickup_<id>` dans `assets.py`.
"""

from dataclasses import dataclass, field

MARKS = ["", " Mk. II", " Mk. III", " Mk. IV"]   # suffixe selon le niveau
LEVEL_DAMAGE_BONUS = 0.25                        # +25 % de dégâts par niveau


@dataclass(frozen=True)
class WeaponSpec:
    id: str
    name: str
    damage: int            # dégâts de base par balle/plomb
    fire_delay: float      # temps minimal entre deux tirs (s)
    magazine_size: int
    reload_time: float
    pellets: int = 1       # plombs par coup (fusil à pompe)
    spread: float = 0.0    # dispersion (radians, demi-angle)
    automatic: bool = True # tir maintenu possible
    hit_radius: float = 0.35
    sound: str = "player_shot"


WEAPON_SPECS = {
    "pistol": WeaponSpec(
        id="pistol", name="Pistolet", damage=20, fire_delay=0.30,
        magazine_size=12, reload_time=1.1, spread=0.01,
        automatic=False, sound="pistol_shot"),
    "shotgun": WeaponSpec(
        id="shotgun", name="Fusil à pompe", damage=9, fire_delay=0.95,
        magazine_size=6, reload_time=2.0, pellets=7, spread=0.09,
        automatic=False, sound="shotgun_shot"),
    "rifle": WeaponSpec(
        id="rifle", name="Fusil d'assaut", damage=24, fire_delay=0.13,
        magazine_size=30, reload_time=1.6, spread=0.018),
    "minigun": WeaponSpec(
        id="minigun", name="Minigun", damage=14, fire_delay=0.055,
        magazine_size=100, reload_time=2.6, spread=0.05),
}

# Ordre des emplacements (touches 1..4 / molette).
WEAPON_ORDER = ["pistol", "shotgun", "rifle", "minigun"]


@dataclass
class Weapon:
    """Une arme possédée : spec + niveau d'amélioration + état (munitions)."""

    spec: WeaponSpec
    level: int = 0         # niveau où elle a été obtenue (0 = base)

    ammo: int = field(default=0, init=False)
    cooldown: float = field(default=0.0, init=False)
    reloading: float = field(default=0.0, init=False)

    def __post_init__(self):
        self.ammo = self.spec.magazine_size

    # ------------------------------------------------------------------
    @property
    def damage(self):
        """Dégâts effectifs : les armes trouvées plus loin frappent plus fort."""
        return round(self.spec.damage * (1 + LEVEL_DAMAGE_BONUS * self.level))

    @property
    def display_name(self):
        mark = MARKS[min(self.level, len(MARKS) - 1)]
        return self.spec.name + mark

    # ------------------------------------------------------------------
    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        if self.reloading > 0.0:
            self.reloading -= dt
            if self.reloading <= 0.0:
                self.reloading = 0.0
                self.ammo = self.spec.magazine_size

    def can_fire(self):
        return self.cooldown <= 0.0 and self.reloading <= 0.0 and self.ammo > 0

    def fire(self):
        """Consomme une balle ; retourne True si le coup part."""
        if not self.can_fire():
            return False
        self.ammo -= 1
        self.cooldown = self.spec.fire_delay
        if self.ammo == 0:
            self.start_reload()    # rechargement automatique chargeur vide
        return True

    def start_reload(self):
        if self.reloading <= 0.0 and self.ammo < self.spec.magazine_size:
            self.reloading = self.spec.reload_time
