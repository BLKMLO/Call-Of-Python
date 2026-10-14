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
    # Facteur appliqué au délai de submersion à chaque nouvelle vague du
    # Déferlement : -3 % (Recrue), -6 % (Soldat), -10 % (Vétéran).
    wave_timeout_decay: float
    # Confort du joueur. Soldat garde exactement les valeurs historiques.
    clear_heal: int            # PV rendus par vague nettoyée (Déferlement)
    level_heal: int            # PV rendus en passant au niveau suivant
    spawn_shield: float        # bouclier d'arrivée (s)
    lifepack_every: int        # le pack de vie revient toutes les N vagues
    enemy_count: float         # multiplicateur du nombre d'ennemis par vague
    boss_tempo: float          # multiplicateur du temps de repos du Colosse
    reinforcement_cap: float   # multiplicateur des renforts de mission
    countdown_mult: float      # multiplicateur des comptes à rebours de mission
    summary: str               # résumé affiché dans le menu principal


DIFFICULTIES = {
    "recruit": DifficultyProfile(
        "recruit", "Recrue", 0.82, 0.72, 1.20, 0.97,
        clear_heal=20, level_heal=55, spawn_shield=4.0, lifepack_every=1,
        enemy_count=0.8, boss_tempo=1.2, reinforcement_cap=0.75, countdown_mult=1.25,
        summary="Ennemis moins nombreux, soins généreux"),
    "soldier": DifficultyProfile(
        "soldier", "Soldat", 1.00, 1.00, 1.00, 0.94,
        clear_heal=12, level_heal=40, spawn_shield=3.0, lifepack_every=2,
        enemy_count=1.0, boss_tempo=1.0, reinforcement_cap=1.0, countdown_mult=1.0,
        summary="L'expérience prévue"),
    "veteran": DifficultyProfile(
        "veteran", "Vétéran", 1.22, 1.28, 0.86, 0.90,
        clear_heal=6, level_heal=25, spawn_shield=2.0, lifepack_every=3,
        enemy_count=1.25, boss_tempo=0.75, reinforcement_cap=1.5, countdown_mult=0.8,
        summary="Hordes denses, Colosse enragé, peu de soins"),
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
