"""Améliorations de session : tirage isolé, choix bornés et effets idempotents.

Chaque proposition tire jusqu'à trois cartes d'arme (`WEAPON_UPGRADES`) et
une quatrième carte hors arme (`PERKS`), toujours en dernière position. Le
nombre de récompenses n'est plus limité : seul chaque bonus a un plafond
(`CAPS`). Une catégorie épuisée n'apparaît simplement plus.
"""

import math
import random
from dataclasses import replace

from weapons import WEAPON_SPECS

WEAPON_UPGRADES = {
    "damage": ("Impact", "+10 % dégâts"),
    "reload": ("Chargeur rapide", "-15 % temps de recharge"),
    "capacity": ("Réserve", "+20 % capacité du chargeur"),
    "accuracy": ("Stabilité", "-20 % dispersion"),
    "cadence": ("Mécanisme", "+8 % cadence"),
}
PERKS = {
    "grenade": ("Artificier", "+1 grenade max, stock rempli"),
    "ghost_slide": ("Glissade fantôme", "Invincible toute la glissade"),
    "vitality": ("Blindage", "+20 PV max (et rendus)"),
    "momentum": ("Élan", "+25 % distance de glissade"),
}
UPGRADES = {**WEAPON_UPGRADES, **PERKS}
# Plafonds : les effets linéaires restent positifs (recharge >= 25 % du
# temps d'origine, dispersion >= 20 %).
CAPS = {"damage": 10, "reload": 5, "capacity": 10, "accuracy": 4, "cadence": 10,
        "grenade": 4, "ghost_slide": 1, "vitality": 5, "momentum": 2}
WEAPON_CARDS = 3
CHOICE_SECONDS = 12.0
BASE_GRENADES = 2
BASE_HEALTH = 100
VITALITY_HEALTH = 20
MOMENTUM_BOOST = 0.25
MAX_GRENADES = BASE_GRENADES + CAPS["grenade"]
MAX_COUNTER = 2 ** 31 - 1     # borne réseau des compteurs (offres, crédits)


class SessionUpgrades:
    def __init__(self, seed=101):
        self.seed = seed
        self.levels = {}
        self.offers = []
        self.offer_id = 0
        self.remaining = 0.0
        self.credits = 0
        self.awards = set()

    @property
    def grenade_capacity(self):
        return BASE_GRENADES + self.levels.get("grenade", 0)

    def award(self, token):
        if token in self.awards:
            return False
        self.awards.add(token)
        self.credits += 1
        self._offer_next()
        return True

    def _offer_next(self):
        if self.offers or self.credits <= 0:
            return
        weapons = [key for key in sorted(WEAPON_UPGRADES)
                   if self.levels.get(key, 0) < CAPS[key]]
        perks = [key for key in sorted(PERKS) if self.levels.get(key, 0) < CAPS[key]]
        if not weapons and not perks:
            self.credits = 0          # tout est au maximum : plus rien à offrir
            return
        self.credits -= 1
        self.offer_id += 1
        rng = random.Random(self.seed + 65537 * self.offer_id)
        offers = rng.sample(weapons, min(WEAPON_CARDS, len(weapons)))
        if perks:
            offers.append(rng.choice(perks))
        self.offers = offers
        self.remaining = CHOICE_SECONDS

    def choose(self, offer_id, index):
        if (type(offer_id) is not int or type(index) is not int
                or offer_id != self.offer_id or not 0 <= index < len(self.offers)):
            return False
        key = self.offers[index]
        self.levels[key] = self.levels.get(key, 0) + 1
        self.offers = []
        self.remaining = 0.0
        self._offer_next()
        return True

    def update(self, dt):
        if (type(dt) not in (int, float) or not math.isfinite(dt)
                or not 0 <= dt <= 0.25 or not self.offers):
            return
        self.remaining = max(0.0, self.remaining - dt)
        if self.remaining <= 1e-9:
            self.choose(self.offer_id, 0)

    def apply(self, weapons):
        signature = tuple(sorted((key, value) for key, value in self.levels.items()
                                 if key in WEAPON_UPGRADES))
        for weapon in weapons:
            if getattr(weapon, "upgrade_signature", None) == signature:
                continue
            base = WEAPON_SPECS[weapon.spec.id]
            ratio = weapon.reloading / weapon.spec.reload_time
            weapon.spec = replace(
                base, damage=round(base.damage * (1 + 0.10 * self.levels.get("damage", 0))),
                reload_time=base.reload_time * (1 - 0.15 * self.levels.get("reload", 0)),
                magazine_size=round(base.magazine_size
                                    * (1 + 0.20 * self.levels.get("capacity", 0))),
                spread=base.spread * (1 - 0.20 * self.levels.get("accuracy", 0)),
                fire_delay=base.fire_delay / (1 + 0.08 * self.levels.get("cadence", 0)))
            weapon.reloading = ratio * weapon.spec.reload_time
            weapon.ammo = min(weapon.ammo, weapon.spec.magazine_size)
            weapon.upgrade_signature = signature

    def apply_player(self, player):
        """Applique les cartes hors arme au joueur ; idempotent.

        Retourne le nombre de niveaux « Artificier » gagnés depuis le
        dernier appel, pour que l'appelant remplisse le stock de grenades.
        """
        vitality = self.levels.get("vitality", 0)
        applied = getattr(player, "vitality_applied", 0)
        if vitality != applied:
            player.max_health = BASE_HEALTH + VITALITY_HEALTH * vitality
            gained = max(0, vitality - applied) * VITALITY_HEALTH
            player.health = min(player.max_health, player.health + gained)
            player.vitality_applied = vitality
        player.slide_ghost = self.levels.get("ghost_slide", 0) > 0
        player.slide_boost = 1.0 + MOMENTUM_BOOST * self.levels.get("momentum", 0)
        grenades = self.levels.get("grenade", 0)
        gained = max(0, grenades - getattr(player, "grenade_applied", 0))
        player.grenade_applied = grenades
        return gained

    def snapshot(self):
        return [self.offer_id, sorted(self.levels.items()), list(self.offers),
                round(self.remaining, 3), self.credits]

    def apply_snapshot(self, row):
        if not isinstance(row, list) or len(row) != 5:
            return False
        ident, levels, offers, remaining, credits = row
        if (type(ident) is not int or not self.offer_id <= ident <= MAX_COUNTER
                or not isinstance(levels, list) or len(levels) > len(UPGRADES)
                or not isinstance(offers, list) or not valid_offers(offers)
                or type(remaining) not in (int, float) or not math.isfinite(remaining)
                or not 0 <= remaining <= CHOICE_SECONDS
                or type(credits) is not int or not 0 <= credits <= MAX_COUNTER):
            return False
        clean = {}
        for item in levels:
            if (not isinstance(item, (list, tuple)) or len(item) != 2
                    or not isinstance(item[0], str) or item[0] not in UPGRADES
                    or item[0] in clean or type(item[1]) is not int
                    or not 1 <= item[1] <= CAPS[item[0]]):
                return False
            clean[item[0]] = item[1]
        if (any(clean.get(key, 0) < value for key, value in self.levels.items())
                or any(clean.get(key, 0) >= CAPS[key] for key in offers)
                or (not offers and remaining != 0)):
            return False
        self.offer_id, self.levels, self.offers = ident, clean, list(offers)
        self.remaining, self.credits = remaining, credits
        return True


def valid_offers(offers):
    """Au plus trois cartes d'arme distinctes, puis au plus une hors arme."""
    if len(offers) > WEAPON_CARDS + 1 or len(set(map(str, offers))) != len(offers):
        return False
    if any(not isinstance(key, str) or key not in UPGRADES for key in offers):
        return False
    perks = [i for i, key in enumerate(offers) if key in PERKS]
    return len(perks) <= 1 and all(i == len(offers) - 1 for i in perks)
