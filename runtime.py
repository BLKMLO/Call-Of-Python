"""Primitives de boucle temps reel independantes de pygame."""

from __future__ import annotations

from dataclasses import dataclass

SIMULATION_HZ = 60
SIMULATION_STEP = 1.0 / SIMULATION_HZ
MAX_FRAME_TIME = 0.25
MAX_STEPS_PER_FRAME = 8


@dataclass
class FixedStepClock:
    """Accumulateur a pas fixe avec protection contre la spirale de retard."""

    step: float = SIMULATION_STEP
    max_frame_time: float = MAX_FRAME_TIME
    max_steps: int = MAX_STEPS_PER_FRAME
    accumulator: float = 0.0
    dropped_time: float = 0.0

    def advance(self, frame_time):
        """Retourne le nombre de pas a simuler pour la duree de rendu recue."""
        try:
            frame_time = float(frame_time)
        except (TypeError, ValueError, OverflowError):
            frame_time = 0.0
        frame_time = max(0.0, min(frame_time, self.max_frame_time))
        self.accumulator += frame_time
        steps = min(int(self.accumulator / self.step), self.max_steps)
        self.accumulator -= steps * self.step
        if steps == self.max_steps and self.accumulator >= self.step:
            self.dropped_time += self.accumulator - (self.accumulator % self.step)
            self.accumulator %= self.step
        return steps

    @property
    def alpha(self):
        """Fraction residuelle disponible pour une future interpolation rendu."""
        return min(1.0, max(0.0, self.accumulator / self.step))
