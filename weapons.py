"""Armes du jeu.

Une arme est décrite par ses statistiques (dégâts, cadence, chargeur...).
Le tir lui-même est un "hitscan" : il est résolu instantanément dans
`game.py` (pas de projectile simulé). Pour ajouter une nouvelle arme, il
suffit de créer une autre instance de `Weapon` et de la donner au joueur.
"""

from dataclasses import dataclass, field


@dataclass
class Weapon:
    name: str = "Fusil d'assaut"
    damage: int = 25            # dégâts par balle
    fire_delay: float = 0.14    # temps minimal entre deux tirs (s) → ~7 tirs/s
    magazine_size: int = 30     # taille du chargeur
    reload_time: float = 1.6    # durée du rechargement (s)
    hit_radius: float = 0.35    # rayon "touchable" d'un ennemi (en cases)
    automatic: bool = True      # tir maintenu possible

    # État courant (non configurable)
    ammo: int = field(default=30, init=False)
    cooldown: float = field(default=0.0, init=False)
    reloading: float = field(default=0.0, init=False)

    def __post_init__(self):
        self.ammo = self.magazine_size

    # ------------------------------------------------------------------
    def update(self, dt):
        """Fait avancer les minuteries (cadence et rechargement)."""
        self.cooldown = max(0.0, self.cooldown - dt)
        if self.reloading > 0.0:
            self.reloading -= dt
            if self.reloading <= 0.0:
                self.reloading = 0.0
                self.ammo = self.magazine_size

    def can_fire(self):
        return self.cooldown <= 0.0 and self.reloading <= 0.0 and self.ammo > 0

    def fire(self):
        """Consomme une balle ; retourne True si le coup part."""
        if not self.can_fire():
            return False
        self.ammo -= 1
        self.cooldown = self.fire_delay
        if self.ammo == 0:
            self.start_reload()  # rechargement automatique chargeur vide
        return True

    def start_reload(self):
        if self.reloading <= 0.0 and self.ammo < self.magazine_size:
            self.reloading = self.reload_time
