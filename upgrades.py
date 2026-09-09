"""Améliorations de session : tirage isolé, choix bornés et effets idempotents."""

import math
import random
from dataclasses import replace

from weapons import WEAPON_SPECS

UPGRADES = {
    "damage": ("Impact", "+10 % dégâts"),
    "reload": ("Chargeur rapide", "-15 % temps de recharge"),
    "capacity": ("Réserve", "+20 % capacité du chargeur"),
    "accuracy": ("Stabilité", "-20 % dispersion"),
    "cadence": ("Mécanisme", "+8 % cadence"),
}
CHOICE_SECONDS = 12.0
MAX_CHOICES = 6


class SessionUpgrades:
    def __init__(self, seed=101):
        self.seed = seed
        self.levels = {}
        self.offers = []
        self.offer_id = 0
        self.remaining = 0.0
        self.credits = 0
        self.awards = set()

    def award(self, token):
        if token in self.awards or len(self.awards) >= MAX_CHOICES:
            return False
        self.awards.add(token)
        self.credits += 1
        self._offer_next()
        return True

    def _offer_next(self):
        if self.offers or self.credits <= 0:
            return
        self.credits -= 1
        self.offer_id += 1
        pool = [key for key in sorted(UPGRADES) if self.levels.get(key, 0) < 2]
        self.offers = random.Random(self.seed + 65537 * self.offer_id).sample(pool, 3)
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
        signature = tuple(sorted(self.levels.items()))
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

    def snapshot(self):
        return [self.offer_id, sorted(self.levels.items()), list(self.offers),
                round(self.remaining, 3), self.credits]

    def apply_snapshot(self, row):
        if not isinstance(row, list) or len(row) != 5:
            return False
        ident, levels, offers, remaining, credits = row
        if (type(ident) is not int or not self.offer_id <= ident <= MAX_CHOICES
                or not isinstance(levels, list) or len(levels) > len(UPGRADES)
                or not isinstance(offers, list) or len(offers) not in (0, 3)
                or any(not isinstance(key, str) or key not in UPGRADES for key in offers)
                or len(set(offers)) != len(offers)
                or type(remaining) not in (int, float) or not math.isfinite(remaining)
                or not 0 <= remaining <= CHOICE_SECONDS
                or type(credits) is not int or not 0 <= credits <= MAX_CHOICES):
            return False
        clean = {}
        for item in levels:
            if (not isinstance(item, (list, tuple)) or len(item) != 2
                    or not isinstance(item[0], str) or item[0] not in UPGRADES
                    or item[0] in clean or type(item[1]) is not int or not 1 <= item[1] <= 2):
                return False
            clean[item[0]] = item[1]
        if (sum(clean.values()) > MAX_CHOICES
                or any(clean.get(key, 0) < value for key, value in self.levels.items())
                or any(clean.get(key, 0) >= 2 for key in offers)
                or (not offers and remaining != 0)):
            return False
        self.offer_id, self.levels, self.offers = ident, clean, list(offers)
        self.remaining, self.credits = remaining, credits
        return True
