"""Objectifs déclaratifs : simulation pure, aucune autorité côté client."""

import math
from dataclasses import dataclass

KINDS = frozenset(("interact", "reach", "defend", "eliminate"))


@dataclass(frozen=True)
class Objective:
    id: str
    label: str
    kind: str
    x: float
    y: float
    radius: float = 1.2
    duration: float = 0.0

    def __post_init__(self):
        if (not isinstance(self.id, str) or not self.id.isidentifier()
                or len(self.id) > 32 or not isinstance(self.label, str)
                or not 1 <= len(self.label) <= 64 or self.kind not in KINDS):
            raise ValueError("Objectif inconnu ou libellé invalide")
        if any(type(v) not in (int, float) or not math.isfinite(v)
               for v in (self.x, self.y, self.radius, self.duration)):
            raise ValueError("Coordonnées non finies")
        if not (0 <= self.x <= 256 and 0 <= self.y <= 256
                and 0.25 <= self.radius <= 4 and 0 <= self.duration <= 120):
            raise ValueError("Objectif hors bornes")


class Mission:
    """Séquence bornée et idempotente. Distance et visibilité vérifiées localement."""

    def __init__(self, definitions=()):
        if len(definitions) > 16:
            raise ValueError("Trop d'objectifs")
        self.steps = tuple(Objective(**row) for row in definitions)
        if len({step.id for step in self.steps}) != len(self.steps):
            raise ValueError("Identifiant dupliqué")
        self.index = 0
        self.elapsed = 0.0

    @property
    def current(self):
        return self.steps[self.index] if self.index < len(self.steps) else None

    @property
    def complete(self):
        return bool(self.steps) and self.current is None

    def advance(self):
        if self.current is not None:
            self.index += 1
            self.elapsed = 0.0

    @staticmethod
    def in_range(actor, step, visible):
        return (actor.alive and not getattr(actor, "rolling", False)
                and math.hypot(actor.x - step.x, actor.y - step.y) <= step.radius
                and visible(actor.x, actor.y, step.x, step.y))

    def interact(self, actor, visible):
        step = self.current
        if step and step.kind == "interact" and self.in_range(actor, step, visible):
            self.advance()
            return True
        return False

    def update(self, dt, actors, visible, enemies_alive):
        if type(dt) not in (int, float) or not math.isfinite(dt) or not 0 <= dt <= 0.25:
            return
        step = self.current
        if step is None or step.kind == "interact":
            return
        present = any(self.in_range(actor, step, visible) for actor in actors)
        if step.kind == "eliminate":
            if not enemies_alive:
                self.advance()
        elif step.kind == "reach" and present:
            self.advance()
        elif step.kind == "defend":
            self.elapsed = self.elapsed + dt if present else 0.0
            if self.elapsed + 1e-9 >= step.duration:
                self.advance()

    def snapshot(self):
        return [self.index, round(self.elapsed, 3)]

    def apply_snapshot(self, row):
        """Lecture atomique, sans faire confiance à la structure reçue."""
        if (not isinstance(row, list) or len(row) != 2
                or type(row[0]) is not int or not self.index <= row[0] <= len(self.steps)
                or type(row[1]) not in (int, float) or not math.isfinite(row[1])
                or not 0 <= row[1] <= 120):
            return False
        step = self.steps[row[0]] if row[0] < len(self.steps) else None
        if row[1] > (step.duration if step and step.kind == "defend" else 0):
            return False
        self.index, self.elapsed = row
        return True
