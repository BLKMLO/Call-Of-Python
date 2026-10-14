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

import math
from dataclasses import dataclass, field

MARKS = ["", " Mk. II", " Mk. III", " Mk. IV"]   # suffixe selon le niveau
LEVEL_DAMAGE_BONUS = 0.25                        # +25 % de dégâts par niveau

# Minigun : munitions illimitées, mais le canon chauffe (demande du 14/10).
# Nombre de tirs avant surchauffe = HEAT_SHOTS_RATIO × capacité (100 → 70),
# refroidissement complet = COOL_TIME_RATIO × temps de recharge
# (2,6 s → 2,21 s) : les cartes « Réserve » et « Chargeur rapide » gardent
# donc un effet sur le minigun.
HEAT_SHOTS_RATIO = 0.7
COOL_TIME_RATIO = 0.85
COOL_DELAY = 0.3          # le canon refroidit 0,3 s après le dernier tir
SPIN_UP_TIME = 0.4        # lancement des canons avant le premier tir (s)
TRIGGER_MEMORY = 0.12     # gâchette considérée « tenue » depuis la dernière demande
HEAVY_FIRE_WINDOW = 0.2   # ralentissement tant qu'on a tiré il y a moins de 0,2 s
HEAVY_MOVE_MULT = 0.65    # vitesse de déplacement en tirant au minigun

# Spécialisation des armes selon la cible (voir `shot_damage`).
MINIGUN_ARMOR_MULT = 0.6  # le minigun ricoche sur le blindage
PISTOL_ARMOR_MULT = 1.4   # balles perforantes
PISTOL_ADS_MULT = 1.75    # tir précis en visée (lunette au moins à 90 %)
SHOTGUN_CLOSE_RANGE = 2.0 # bonus à bout portant (m)
SHOTGUN_CLOSE_MULT = 1.5
SHIELD_BLOCK = 0.15       # part des dégâts qui traverse un bouclier de face
SHIELD_ARC = math.radians(60)   # demi-angle couvert par le bouclier


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
    heat: bool = False     # munitions illimitées + surchauffe (minigun)


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
        magazine_size=100, reload_time=2.6, spread=0.05, heat=True),
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
    # Surchauffe (armes `heat`) : 0 froid → 1 surchauffe.
    heat: float = field(default=0.0, init=False)
    overheated: bool = field(default=False, init=False)
    spin: float = field(default=0.0, init=False)
    trigger_timer: float = field(default=0.0, init=False)
    since_shot: float = field(default=10.0, init=False)
    heat_mult: float = field(default=1.0, init=False)   # carte « Refroidissement »

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

    @property
    def reload_progress(self):
        """Progression visuelle de la recharge, bornée entre 0 et 1.

        La valeur vaut 0 hors recharge, démarre à 0 quand la recharge est
        déclenchée et atteint 1 juste avant que le chargeur soit rempli.
        """
        if (self.spec.heat or self.reloading <= 0.0
                or self.spec.reload_time <= 0.0):
            return 0.0
        return max(0.0, min(
            1.0,
            1.0 - self.reloading / self.spec.reload_time,
        ))

    # ------------------------------------------------------------------
    @property
    def heat_per_shot(self):
        return self.heat_mult / max(1.0, HEAT_SHOTS_RATIO * self.spec.magazine_size)

    @property
    def firing_heavy(self):
        """Vrai juste après un tir d'arme lourde (déplacement ralenti)."""
        return self.spec.heat and self.since_shot < HEAVY_FIRE_WINDOW

    def pull_trigger(self):
        """Gâchette tenue localement : lance les canons du minigun.

        Renvoie True quand l'arme est prête à tirer. Seuls les tirs locaux
        (joueur solo, client LAN) passent par ici : l'hôte valide les tirs
        distants avec `fire()` seul, après le lancement fait chez le client."""
        if not self.spec.heat:
            return True
        self.trigger_timer = TRIGGER_MEMORY
        return self.spin >= 1.0

    def update(self, dt):
        self.cooldown = max(0.0, self.cooldown - dt)
        if self.spec.heat:
            self.since_shot += dt
            if self.trigger_timer > 0.0:
                self.trigger_timer = max(0.0, self.trigger_timer - dt)
                self.spin = min(1.0, self.spin + dt / SPIN_UP_TIME)
            else:
                self.spin = max(0.0, self.spin - dt / SPIN_UP_TIME)
            if self.overheated or self.since_shot >= COOL_DELAY:
                cool_time = max(0.1, COOL_TIME_RATIO * self.spec.reload_time)
                self.heat = max(0.0, self.heat - dt / cool_time)
                if self.overheated and self.heat <= 0.0:
                    self.overheated = False
            return
        if self.reloading > 0.0:
            self.reloading -= dt
            if self.reloading <= 0.0:
                self.reloading = 0.0
                self.ammo = self.spec.magazine_size

    def can_fire(self):
        if self.spec.heat:
            return self.cooldown <= 0.0 and not self.overheated
        return self.cooldown <= 0.0 and self.reloading <= 0.0 and self.ammo > 0

    def fire(self):
        """Consomme une balle (ou chauffe le canon) ; True si le coup part."""
        if not self.can_fire():
            return False
        if self.spec.heat:
            self.cooldown = self.spec.fire_delay
            self.since_shot = 0.0
            self.heat = min(1.0, self.heat + self.heat_per_shot)
            if self.heat >= 1.0 - 1e-9:
                self.heat = 1.0
                self.overheated = True
            return True
        self.ammo -= 1
        self.cooldown = self.spec.fire_delay
        if self.ammo == 0:
            self.start_reload()    # rechargement automatique chargeur vide
        return True

    def start_reload(self):
        if self.spec.heat:
            return                  # munitions illimitées : rien à recharger
        if self.reloading <= 0.0 and self.ammo < self.spec.magazine_size:
            self.reloading = self.spec.reload_time


def armored(enemy):
    """Blindage d'origine (lourd, Colosse), même en variante possédée."""
    return getattr(type(enemy), "IMPACT_TYPE", "flesh") == "armor"


def shot_damage(weapon, enemy, distance, ads=0.0, shooter_angle=None,
                close_range=SHOTGUN_CLOSE_RANGE):
    """Dégâts d'une balle/plomb selon l'arme et la cible.

    - Minigun : ×0,6 contre le blindage.
    - Pistolet : ×1,4 contre le blindage, ×1,75 en visée complète.
    - Fusil à pompe : ×1,5 à bout portant (≤ 2 m, 3,5 m avec la carte).
    - Bouclier frontal levé : seuls 15 % passent (angle de tir ≤ 60°).
    """
    damage = float(weapon.damage)
    wid = weapon.spec.id
    if wid == "minigun" and armored(enemy):
        damage *= MINIGUN_ARMOR_MULT
    elif wid == "pistol":
        if armored(enemy):
            damage *= PISTOL_ARMOR_MULT
        if ads >= 0.9:
            damage *= PISTOL_ADS_MULT
    elif wid == "shotgun" and distance <= close_range:
        damage *= SHOTGUN_CLOSE_MULT
    if shooter_angle is not None and shield_blocks(enemy, shooter_angle):
        damage *= SHIELD_BLOCK
    return max(1, round(damage))


def shield_blocks(enemy, shooter_angle):
    """Vrai si le bouclier levé de `enemy` fait face au tir.

    `shooter_angle` est la direction ennemi → tireur."""
    if not getattr(enemy, "shielded", False) or getattr(enemy, "stun_timer", 0.0) > 0.0:
        return False
    delta = (shooter_angle - enemy.angle + math.pi) % (2 * math.pi) - math.pi
    return abs(delta) <= SHIELD_ARC
