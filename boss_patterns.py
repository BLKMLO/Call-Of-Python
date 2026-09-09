"""Séquences du Colosse : annonce, attaque verrouillée et récupération."""

import math


class BossPattern:
    def __init__(self):
        self.state = "idle"
        self.kind = "charge"
        self.timer = 3.0
        self.x = self.y = self.angle = 0.0
        self.cycle = 0
        self.hits = set()

    def step(self, dt, boss, target, visible):
        if not boss.alive:
            self.state = "idle"
            return False, []
        if type(dt) not in (int, float) or not math.isfinite(dt) or not 0 <= dt <= .25:
            return self.state != "idle", []
        self.timer -= dt
        if self.state == "idle":
            if (self.timer <= 1e-9 and target.alive
                    and math.hypot(target.x - boss.x, target.y - boss.y) <= 10
                    and visible(boss.x, boss.y, target.x, target.y)):
                self.kind = "slam" if boss.phase >= 2 and self.cycle % 2 else "charge"
                self.cycle += 1
                self.x, self.y = target.x, target.y
                self.angle = math.atan2(target.y - boss.y, target.x - boss.x)
                self.hits.clear()
                self.state, self.timer = "warn", 1.2
                return True, ["warn"]
            return False, []
        if self.state == "warn" and self.timer <= 1e-9:
            self.state, self.timer = ("recover", 1.2) if self.kind == "slam" else ("charge", .65)
            return True, ["slam"] if self.kind == "slam" else []
        if self.state == "charge":
            if self.timer <= 1e-9:
                self.state, self.timer = "recover", 1.2
            return True, ["move"]
        if self.state == "recover" and self.timer <= 1e-9:
            self.state, self.timer = "idle", 4.5 - .5 * boss.phase
        return True, []

    def snapshot(self):
        return [self.state, self.kind, round(self.x, 2), round(self.y, 2),
                round(max(0, self.timer), 3)]

    def apply_snapshot(self, row):
        if (not isinstance(row, list) or len(row) != 5
                or row[0] not in ("idle", "warn", "charge", "recover")
                or row[1] not in ("charge", "slam")
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in row[2:])
                or not 0 <= row[2] <= 256 or not 0 <= row[3] <= 256 or not 0 <= row[4] <= 10):
            return False
        self.state, self.kind, self.x, self.y, self.timer = row
        return True
