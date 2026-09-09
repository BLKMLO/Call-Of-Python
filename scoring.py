"""Score autoritaire, crédits uniques et grade relatif au niveau terminé."""

POINTS = {"grunt": 100, "soldier": 150, "heavy": 220, "sniper": 180,
          "kamikaze": 80, "commander": 450, "boss": 1500}


def enemy_points(enemy):
    return POINTS.get(enemy.KIND, 100) + (100 if enemy.elite else 0)


class ScoreBook:
    def __init__(self, total=0, target=3000):
        self.total = int(total)
        self.segment = 0
        self.target = max(1, int(target))
        self.objectives = 0
        self.revives = 0
        self.previous_life = {}
        self.awards = set()
        self.victory = False

    def add(self, amount):
        self.total = max(0, self.total + amount)
        self.segment = max(0, self.segment + amount)

    def award(self, token, points):
        if token in self.awards or len(self.awards) >= 64:
            return False
        self.awards.add(token)
        self.add(points)
        return True

    def rescue(self):
        if self.revives < 4:
            self.revives += 1
            self.add(250)

    def observe(self, enemies, mission_index, players, outcome):
        for enemy in enemies:
            if not enemy.alive and not getattr(enemy, "score_credited", False):
                enemy.score_credited = True
                self.add(enemy_points(enemy))
        if mission_index > self.objectives:
            self.add(500 * (mission_index - self.objectives))
            self.objectives = mission_index
        for pid, alive in players.items():
            if self.previous_life.get(pid, True) and not alive:
                self.add(-150)
        self.previous_life = dict(players)
        if outcome == "victory":
            self.victory = True
            self.award("victory", 500)

    @property
    def grade(self):
        ratio = self.segment / self.target
        if self.victory and ratio >= .9:
            return "S"
        if self.victory and ratio >= .75:
            return "A"
        return "B" if ratio >= .5 else "C" if ratio >= .25 else "D"

    def snapshot(self):
        return [self.total, self.segment, self.target, self.revives, self.grade]


def valid_score(row):
    return (isinstance(row, list) and len(row) == 5
            and all(type(v) is int and 0 <= v <= 10 ** 9 for v in row[:4])
            and row[2] > 0 and row[3] <= 4 and row[4] in ("S", "A", "B", "C", "D"))
