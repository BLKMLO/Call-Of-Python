"""Secours et signaux coopératifs, simulés uniquement par l'hôte."""

import math

DOWN_SECONDS = 20.0
RESPAWN_SECONDS = 6.0
REVIVE_SECONDS = 3.0


class Rescue:
    def __init__(self):
        self.downed = {}
        self.requests = {}

    def request(self, pid, players, visible):
        if pid in self.requests:
            del self.requests[pid]
            return True
        helper = players[pid]
        if not helper.alive or helper.rolling:
            return False
        for target, row in sorted(self.downed.items()):
            victim = players.get(target)
            if (victim is not None and row[0] > RESPAWN_SECONDS
                    and math.hypot(helper.x - victim.x, helper.y - victim.y) <= 1.4
                    and visible(helper.x, helper.y, victim.x, victim.y)):
                self.requests[pid] = (target, helper.health)
                return True
        return False

    def update(self, dt, players, visible):
        if not 0 <= dt <= 0.25:
            return []
        results = []
        for pid in list(self.downed):
            if pid not in players or players[pid].alive:
                del self.downed[pid]
        for pid, player in players.items():
            if not player.alive and pid not in self.downed:
                self.downed[pid] = [DOWN_SECONDS + RESPAWN_SECONDS, 0.0, -1]
        active = {}
        for pid, (target, health) in list(self.requests.items()):
            helper, victim = players.get(pid), players.get(target)
            row = self.downed.get(target)
            if (helper is None or victim is None or not helper.alive or helper.rolling
                    or helper.health < health or row is None or row[0] <= RESPAWN_SECONDS
                    or math.hypot(helper.x - victim.x, helper.y - victim.y) > 1.4
                    or not visible(helper.x, helper.y, victim.x, victim.y)):
                del self.requests[pid]
            else:
                active.setdefault(target, pid)
        for pid, row in list(self.downed.items()):
            row[0] = max(0.0, row[0] - dt)
            helper = active.get(pid, -1)
            row[1] = (row[1] + dt if row[2] == helper else dt) if helper >= 0 else 0.0
            row[2] = helper
            if row[1] + 1e-9 >= REVIVE_SECONDS or row[0] <= 1e-9:
                results.append((pid, row[1] + 1e-9 >= REVIVE_SECONDS))
                del self.downed[pid]
                self.requests = {h: value for h, value in self.requests.items() if value[0] != pid}
        return results

    def snapshot(self):
        return [[pid, round(row[0], 3), round(row[1], 3), row[2]]
                for pid, row in sorted(self.downed.items())]


class Pings:
    def __init__(self):
        self.markers = {}
        self.cooldowns = {}

    def add(self, pid, x, y):
        if (self.cooldowns.get(pid, 0) > 0 or not math.isfinite(x + y)
                or not 0 <= x <= 256 or not 0 <= y <= 256):
            return False
        self.cooldowns[pid] = 2.0
        if pid not in self.markers and len(self.markers) >= 4:
            del self.markers[next(iter(self.markers))]
        self.markers[pid] = [x, y, 5.0]
        return True

    def update(self, dt):
        for pid in list(self.cooldowns):
            self.cooldowns[pid] = max(0.0, self.cooldowns[pid] - dt)
            if self.cooldowns[pid] <= 0:
                del self.cooldowns[pid]
        for pid in list(self.markers):
            self.markers[pid][2] -= dt
            if self.markers[pid][2] <= 1e-9:
                del self.markers[pid]

    def snapshot(self):
        return [[pid, round(x, 2), round(y, 2), round(timer, 2)]
                for pid, (x, y, timer) in sorted(self.markers.items())]


def validated_rows(rows, rescue=False):
    if not isinstance(rows, list) or len(rows) > 4:
        return None
    clean, seen = [], set()
    for row in rows:
        if (not isinstance(row, list) or len(row) != 4
                or type(row[0]) is not int or not 0 <= row[0] < 2 ** 31 or row[0] in seen
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in row[1:])):
            return None
        if rescue:
            if not (0 <= row[1] <= 26 and 0 <= row[2] <= 3
                    and type(row[3]) is int and -1 <= row[3] < 2 ** 31):
                return None
        elif not (0 <= row[1] <= 256 and 0 <= row[2] <= 256 and 0 <= row[3] <= 5):
            return None
        clean.append(list(row))
        seen.add(row[0])
    return clean
