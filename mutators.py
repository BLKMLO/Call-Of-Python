"""Variations bornées de vagues, indépendantes du hasard du rendu."""

import random

MUTATORS = {
    "rapid": "ASSAUT RAPIDE : vitesse +15 %",
    "armored": "BLINDÉS : vie +20 %, vitesse -10 %",
    "crossfire": "TIRS CROISÉS : davantage de soldats",
}


def mutator_for_wave(wave, seed=101):
    if wave < 4 or wave % 10 == 0:
        return ""
    cycle = list(MUTATORS)
    random.Random(seed).shuffle(cycle)
    return cycle[((wave - 4) // 3) % len(cycle)]


def composition(kinds, mutator):
    return ["soldier" if mutator == "crossfire" and kind == "grunt" and i % 4 == 0
            else kind for i, kind in enumerate(kinds)]


def apply_mutator(enemy, mutator):
    if enemy.KIND == "boss" or getattr(enemy, "mutator", None) is not None:
        return
    enemy.mutator = mutator
    if mutator == "armored":
        enemy.max_health = round(enemy.max_health * 1.2)
        enemy.health = enemy.max_health
    factor = {"rapid": 1.15, "armored": 0.9}.get(mutator, 1.0)
    enemy._base_speed *= factor
    enemy.SPEED *= factor
