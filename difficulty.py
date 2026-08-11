"""Profils de difficulte et directeur de pression du Deferlement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyProfile:
    key: str
    label: str
    enemy_health: float
    enemy_damage: float
    spawn_interval: float


DIFFICULTIES = {
    "recruit": DifficultyProfile("recruit", "Recrue", 0.82, 0.72, 1.20),
    "soldier": DifficultyProfile("soldier", "Soldat", 1.00, 1.00, 1.00),
    "veteran": DifficultyProfile("veteran", "Veteran", 1.22, 1.28, 0.86),
}
DIFFICULTY_ORDER = tuple(DIFFICULTIES)


def get_difficulty(value):
    return DIFFICULTIES.get(value, DIFFICULTIES["soldier"])


class ThreatDirector:
    """Ajuste uniquement la cadence, jamais les degats ni le nombre d'ennemis."""

    def __init__(self, difficulty):
        self.difficulty = get_difficulty(difficulty)
        self.pressure = 1.0

    def observe(self, health_ratio, alive_ratio):
        health_ratio = min(1.0, max(0.0, float(health_ratio)))
        alive_ratio = min(1.0, max(0.0, float(alive_ratio)))
        # Joueur en difficulte : relache les apparitions. Joueur dominant :
        # rapproche legerement la suivante, sans modifier la vague prevue.
        target = 1.18 - 0.32 * health_ratio + 0.18 * alive_ratio
        self.pressure += (target - self.pressure) * 0.08
        self.pressure = min(1.28, max(0.82, self.pressure))
        return self.pressure

    def interval(self, base_interval):
        return (
            float(base_interval)
            * self.difficulty.spawn_interval
            * self.pressure
        )
