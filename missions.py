"""Mécaniques des missions de campagne au-delà de l'Entrepôt.

Tout est déclaré dans la configuration du niveau (`level.py`) et piloté
par `MissionDirector`, appelé à chaque pas par `Game` :

- `reinforcements` : renforts pendant une étape (`during`, intervalle ÷
  difficulté) ou juste après (`after`, nombre × difficulté), plafonnés
  (`max` × difficulté) ;
- `countdown` : compte à rebours tant que l'étape `until` n'est pas finie,
  échec de la mission à zéro ;
- `hostage` : otage libéré par une étape `interact`, qui suit ensuite le
  joueur ; l'étape `escort` est validée quand il atteint la zone ;
- `generators` : le Colosse reste invulnérable tant que ces étapes ne sont
  pas franchies.

Les missions de la campagne restent solo (la coop LAN ne joue que
l'Entrepôt) : aucune donnée de ce module n'est répliquée.
"""

import math
import random

from ai import find_path
from entities import RemotePlayer

HOSTAGE_HEALTH = 150
HOSTAGE_SPEED = 3.0          # un peu moins vite que le joueur (3,2)
HOSTAGE_FOLLOW = 1.3         # distance à laquelle il s'arrête derrière le joueur
HOSTAGE_LEASH = 9.0          # au-delà, il attend sur place (« attendez-moi ! »)
HOSTAGE_REPATH = 0.5         # recalcul du chemin (s)
REINFORCEMENT_CLEARANCE = 6.0  # renforts loin du joueur si possible


class Hostage(RemotePlayer):
    """Otage à escorter : billboard d'allié teinté, ciblé par l'ennemi."""

    MAX_HEALTH = HOSTAGE_HEALTH

    def __init__(self, x, y):
        super().__init__(-1, x, y)
        self.shield = 0.0
        self.elite = "hostage"      # teinte dédiée (elites.variant_sprite)
        self.following = False
        self.path = []
        self.path_timer = 0.0

    def follow(self, dt, leader, level):
        """Rejoint `leader` par le plus court chemin, sans le coller."""
        self.update_timers(dt)
        self.moving = False
        if not self.alive or not self.following:
            return
        distance = math.hypot(leader.x - self.x, leader.y - self.y)
        if distance <= HOSTAGE_FOLLOW or distance > HOSTAGE_LEASH:
            return
        self.path_timer -= dt
        if self.path_timer <= 0.0 or not self.path:
            self.path_timer = HOSTAGE_REPATH
            self.path = find_path(level, self.x, self.y, leader.x, leader.y) or []
        target = self.path[0] if self.path else (leader.x, leader.y)
        dx, dy = target[0] - self.x, target[1] - self.y
        length = math.hypot(dx, dy)
        if length < 0.15 and self.path:
            self.path.pop(0)
            return
        step = min(length, HOSTAGE_SPEED * dt)
        if length > 1e-6:
            old = (self.x, self.y)
            self.x, self.y = level.move_with_collisions(
                self.x, self.y, dx / length * step, dy / length * step, self.RADIUS)
            self.angle = math.atan2(dy, dx)
            self.moving = (self.x, self.y) != old


class MissionDirector:
    def __init__(self, game, config, difficulty):
        self.game = game
        self.config = config
        self.difficulty = difficulty
        rein = config.get("reinforcements") or {}
        self.reinforcements = rein
        self.reinforcement_budget = round(rein.get("max", 0) * difficulty.reinforcement_cap)
        self.reinforcements_sent = 0
        self.during_timer = 0.0
        self._after_done = set()
        countdown = config.get("countdown")
        self.countdown = (countdown["seconds"] * difficulty.countdown_mult
                          if countdown else None)
        self.hostage = None
        self._hostage_cfg = config.get("hostage")
        self.generators = tuple(config.get("generators", ()))
        self.failure = ""
        self._last_index = game.mission.index
        self._sealed_message = 0.0
        self._rng = random.Random(4049 + game.level_index)

    # ------------------------------------------------------------------
    @property
    def step_ids(self):
        return [step.id for step in self.game.mission.steps]

    def _index_of(self, step_id):
        ids = self.step_ids
        return ids.index(step_id) if step_id in ids else -1

    @property
    def boss_sealed(self):
        """Le Colosse reste protégé tant qu'un générateur tourne."""
        if not self.generators:
            return False
        last = max(self._index_of(g) for g in self.generators)
        return self.game.mission.index <= last

    def countdown_active(self):
        if self.countdown is None:
            return False
        return self.game.mission.index <= self._index_of(self.config["countdown"]["until"])

    # ------------------------------------------------------------------
    def update(self, dt):
        game = self.game
        mission = game.mission
        step = mission.current
        # Étapes franchies depuis le dernier pas (interaction ou zone).
        while self._last_index < mission.index:
            self._on_step_done(mission.steps[self._last_index].id)
            self._last_index += 1

        self._sync_boss_seal()
        if self.hostage is not None:
            self.hostage.follow(dt, game.player, game.level)
            if not self.hostage.alive and not self.failure:
                self.failure = "L'otage a été abattu."
        if step is not None and step.kind == "escort" and self.hostage is not None:
            if (self.hostage.alive
                    and math.hypot(self.hostage.x - step.x, self.hostage.y - step.y)
                    <= step.radius):
                mission.advance()
        if self.countdown_active():
            self.countdown = max(0.0, self.countdown - dt)
            if self.countdown <= 0.0 and not self.failure:
                self.failure = self.config["countdown"].get(
                    "failure", "Le compte à rebours est écoulé.")
        self._update_during(dt, step)

    def _on_step_done(self, step_id):
        game = self.game
        if self._hostage_cfg and step_id == self._hostage_cfg["release"]:
            x, y = self._hostage_cfg["x"], self._hostage_cfg["y"]
            self.hostage = Hostage(x, y)
            self.hostage.following = True
            game.hud.show_message("Otage libéré : escortez-le jusqu'à l'extraction !")
        after = self.reinforcements.get("after", {})
        if step_id in after and step_id not in self._after_done:
            self._after_done.add(step_id)
            count = max(1, round(after[step_id] * self.difficulty.reinforcement_cap))
            if self.spawn_reinforcements(count):
                game.hud.show_message("Alerte : des renforts arrivent !")
        if step_id in self.generators:
            remaining = sum(1 for g in self.generators
                            if self._index_of(g) >= game.mission.index)
            if remaining:
                game.hud.show_message(f"Générateur coupé — encore {remaining}.")
            else:
                game.hud.announce("BOUCLIER DU COLOSSE TOMBÉ")

    def _update_during(self, dt, step):
        during = self.reinforcements.get("during", {})
        if step is None or step.id not in during:
            self.during_timer = 0.0
            return
        every, count = during[step.id]
        # Plus de difficulté = renforts plus fréquents (6 s → 8 s / 4 s).
        every /= self.difficulty.reinforcement_cap
        self.during_timer += dt
        if self.during_timer >= every:
            self.during_timer -= every
            self.spawn_reinforcements(count)

    def _sync_boss_seal(self):
        sealed = self.boss_sealed
        for enemy in self.game.enemies:
            if enemy.IS_BOSS:
                enemy.invulnerable = sealed and enemy.alive

    # ------------------------------------------------------------------
    def spawn_reinforcements(self, count):
        """Fait entrer `count` renforts (dans la limite du budget)."""
        rein = self.reinforcements
        points = list(rein.get("points", ()))
        kinds = list(rein.get("kinds", ("grunt",)))
        count = min(count, self.reinforcement_budget - self.reinforcements_sent)
        if count <= 0 or not points:
            return 0
        game = self.game
        player = game.player
        far = [p for p in points
               if math.hypot(p[0] - player.x, p[1] - player.y) >= REINFORCEMENT_CLEARANCE]
        pool = far or sorted(points, key=lambda p: -math.hypot(p[0] - player.x,
                                                              p[1] - player.y))[:1]
        level = game.level
        mult_hp = level.config["enemy_health_mult"]
        mult_dmg = level.config["enemy_damage_mult"]
        spawned = 0
        for _ in range(count):
            x, y = self._rng.choice(pool)
            if not level.can_stand(x, y, 0.3):
                continue
            kind = kinds[(self.reinforcements_sent + spawned) % len(kinds)]
            game.spawn_enemy(kind, x, y, mult_hp, mult_dmg)
            game.ais[-1].alert((player.x, player.y))
            game.particles.spawn_portal(x, y)
            spawned += 1
        self.reinforcements_sent += spawned
        return spawned

    # ------------------------------------------------------------------
    def status_lines(self):
        """Lignes supplémentaires du panneau d'objectif (HUD)."""
        lines = []
        if self.countdown_active():
            minutes, seconds = divmod(math.ceil(self.countdown), 60)
            color = (235, 90, 70) if self.countdown < 30 else (238, 166, 75)
            label = self.config["countdown"].get("label", "Temps restant")
            lines.append((f"{label} : {minutes}:{seconds:02d}", color))
        if self.hostage is not None and self.hostage.alive:
            frac = self.hostage.health / self.hostage.max_health
            distance = math.hypot(self.hostage.x - self.game.player.x,
                                  self.hostage.y - self.game.player.y)
            state = "vous suit" if distance <= HOSTAGE_LEASH else "vous attend !"
            lines.append((f"Otage : {round(frac * 100)} % — {state}",
                          (130, 220, 160) if frac > 0.4 else (235, 90, 70)))
        if self.boss_sealed:
            lines.append(("Colosse invulnérable : coupez les générateurs",
                          (120, 200, 255)))
        return lines
