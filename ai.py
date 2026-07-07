"""Intelligence artificielle des ennemis.

Machine à états, volontairement séparée des entités pour être partagée
par tous les types d'ennemis (y compris le boss) :

    idle   : patrouille localement ; passe en chasse s'il voit le joueur
             ou s'il est alerté (coup de feu, cri d'un allié).
    chase  : poursuit le joueur via un pathfinding BFS sur la grille
             (contourne murs et piliers), ou en ligne directe à vue.
    attack : à portée avec ligne de vue : strafe latéralement et tire.
    cover  : blessé, il se replie vers un point hors de vue du joueur
             (sauf les ennemis avec TAKES_COVER=False, comme le boss).

L'IA retourne une liste d'événements ("enemy_shot", "player_hit",
"spotted"...) que `game.py` transforme en sons, effets et alertes.
"""

import math
import random
from collections import deque

from raycaster import has_line_of_sight


def find_path(level, sx, sy, tx, ty):
    """Plus court chemin (BFS) entre deux cases ; liste de centres de cases.

    Retourne [] si départ et arrivée sont sur la même case, None si aucun
    chemin n'existe. La grille est petite : le BFS est instantané.
    """
    start = (int(sx), int(sy))
    goal = (int(tx), int(ty))
    if start == goal:
        return []
    prev = {start: None}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        x, y = current
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (x + dx, y + dy)
            # blocks_path traite les portes comme traversables : elles
            # s'ouvriront automatiquement à l'approche de l'ennemi.
            if nxt not in prev and not level.blocks_path(nxt[0] + 0.5, nxt[1] + 0.5):
                prev[nxt] = current
                queue.append(nxt)
    if goal not in prev:
        return None
    path = []
    current = goal
    while current != start:
        path.append((current[0] + 0.5, current[1] + 0.5))
        current = prev[current]
    path.reverse()
    return path


class EnemyAI:
    """Pilote un ennemi. Une instance par ennemi."""

    LOSE_SIGHT_TIME = 3.0    # temps sans contact avant d'abandonner (s)
    GIVE_UP_TIME = 14.0      # abandon inconditionnel de l'enquête (s)
    COVER_HEALTH = 35        # seuil de PV déclenchant la recherche de couverture
    COVER_DURATION = 2.6     # temps passé à couvert avant de repartir (s)
    REPATH_TIME = 0.6        # fréquence de recalcul du chemin (s)

    def __init__(self, enemy):
        self.enemy = enemy
        self.lost_timer = 0.0
        self.took_cover = False   # une seule retraite par ennemi
        # Navigation
        self.path = None          # liste de waypoints (centres de cases)
        self.path_timer = 0.0
        self.path_goal = None     # case visée par le chemin courant
        # Strafe en combat
        self.strafe_dir = random.choice((-1, 1))
        self.strafe_timer = random.uniform(0.6, 1.6)
        # Patrouille
        self.wander_target = None
        self.wander_timer = random.uniform(1.0, 4.0)

    # ------------------------------------------------------------------
    def update(self, dt, player, level):
        """Fait avancer l'IA d'un pas de temps ; retourne les événements produits."""
        enemy = self.enemy
        events = []
        if not enemy.alive or not player.alive:
            enemy.moving = False
            return events

        enemy.moving = False  # remis à True par les déplacements (pose "marche")
        enemy.update_timers(dt)
        self.path_timer += dt
        dist = enemy.distance_to(player)
        sees_player = (
            dist < enemy.DETECT_RANGE
            and has_line_of_sight(level, enemy.x, enemy.y, player.x, player.y)
        )
        if sees_player:
            enemy.last_seen = (player.x, player.y)
            self.lost_timer = 0.0
        else:
            self.lost_timer += dt

        # --- transitions ---------------------------------------------------
        state = enemy.ai_state
        if (state != "cover" and enemy.TAKES_COVER and not self.took_cover
                and enemy.health <= self.COVER_HEALTH):
            # Blessé : on tente une retraite vers un point hors de vue.
            cover = self._find_cover(player, level)
            if cover is not None:
                enemy.cover_target = cover
                enemy.ai_state = "cover"
                enemy.ai_timer = 0.0
                self.took_cover = True
                state = "cover"

        if state == "idle":
            if sees_player:
                enemy.ai_state = "chase"
                events.append(("spotted", enemy))  # crie pour alerter les alliés
        elif state == "chase":
            if sees_player and dist < enemy.ATTACK_RANGE and not enemy.MELEE:
                enemy.ai_state = "attack"
            elif not sees_player:
                # N'abandonne l'enquête qu'une fois arrivé sur la dernière
                # position connue (ou après un délai maximal si elle est
                # inaccessible), pas simplement au bout de quelques secondes.
                reached = (enemy.last_seen is None or math.hypot(
                    enemy.last_seen[0] - enemy.x,
                    enemy.last_seen[1] - enemy.y) < 0.6)
                if ((reached and self.lost_timer > self.LOSE_SIGHT_TIME)
                        or self.lost_timer > self.GIVE_UP_TIME):
                    enemy.ai_state = "idle"
                    enemy.last_seen = None
                    self.path = None
        elif state == "attack":
            if not sees_player or dist > enemy.ATTACK_RANGE * 1.2:
                enemy.ai_state = "chase"

        # --- comportements -------------------------------------------------
        state = enemy.ai_state
        if state == "idle":
            self._wander(dt, level)
        elif state == "chase":
            target = (player.x, player.y) if sees_player else enemy.last_seen
            if target is not None:
                self._navigate_towards(dt, target, level)
        elif state == "attack":
            enemy.angle = math.atan2(player.y - enemy.y, player.x - enemy.x)
            if enemy.KEEP_DISTANCE and dist < enemy.MIN_RANGE:
                self._back_away(dt, player, level)   # le sniper se replie
            else:
                self._strafe(dt, player, level)
            events += self._try_shoot(player, dist)

        # Kamikaze : au contact, il se déclenche (game.py gère l'explosion).
        if (enemy.MELEE and enemy.EXPLODES and enemy.ai_state == "chase"
                and dist < enemy.EXPLOSION_RADIUS * 0.5):
            events.append(("explode", enemy))
        elif state == "cover":
            if enemy.cover_target is not None:
                self._navigate_towards(dt, enemy.cover_target, level)
                reached = math.hypot(enemy.cover_target[0] - enemy.x,
                                     enemy.cover_target[1] - enemy.y) < 0.3
            else:
                reached = True
            if reached or enemy.ai_timer > self.COVER_DURATION:
                enemy.ai_state = "chase"
            elif sees_player and dist < enemy.ATTACK_RANGE:
                # On riposte quand même si le joueur nous suit à couvert.
                events += self._try_shoot(player, dist)

        return events

    def alert(self, position):
        """Alerte extérieure (coup de feu, cri d'un allié) : part enquêter."""
        enemy = self.enemy
        if enemy.alive and enemy.ai_state == "idle":
            enemy.ai_state = "chase"
            enemy.last_seen = position
            self.path = None
            self.lost_timer = 0.0

    # ------------------------------------------------------------------
    # Déplacements
    # ------------------------------------------------------------------
    def _move_towards(self, dt, target, level, speed_mult=1.0):
        """Avance en ligne droite vers la cible, en glissant le long des murs."""
        enemy = self.enemy
        dx, dy = target[0] - enemy.x, target[1] - enemy.y
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            return
        enemy.angle = math.atan2(dy, dx)
        step = enemy.SPEED * speed_mult * dt / dist
        enemy.x, enemy.y = level.move_with_collisions(
            enemy.x, enemy.y, dx * step, dy * step, enemy.RADIUS
        )
        enemy.moving = True

    def _navigate_towards(self, dt, target, level, speed_mult=1.0):
        """Rejoint la cible : tout droit si elle est en vue, sinon en
        suivant un chemin BFS recalculé périodiquement."""
        enemy = self.enemy
        if has_line_of_sight(level, enemy.x, enemy.y, target[0], target[1]):
            self.path = None
            self._move_towards(dt, target, level, speed_mult)
            return

        goal = (int(target[0]), int(target[1]))
        if (self.path is None or self.path_goal != goal
                or self.path_timer > self.REPATH_TIME):
            self.path = find_path(level, enemy.x, enemy.y, target[0], target[1])
            self.path_goal = goal
            self.path_timer = 0.0
        if not self.path:
            return  # inaccessible : on reste sur place
        waypoint = self.path[0]
        if math.hypot(waypoint[0] - enemy.x, waypoint[1] - enemy.y) < 0.35:
            self.path.pop(0)
            if not self.path:
                return
            waypoint = self.path[0]
        self._move_towards(dt, waypoint, level, speed_mult)

    def _back_away(self, dt, player, level):
        """Recule face au joueur (sniper trop près) sans lui tourner le dos."""
        enemy = self.enemy
        away = math.atan2(enemy.y - player.y, enemy.x - player.x)
        step = enemy.SPEED * 0.8 * dt
        old = (enemy.x, enemy.y)
        enemy.x, enemy.y = level.move_with_collisions(
            enemy.x, enemy.y, math.cos(away) * step, math.sin(away) * step,
            enemy.RADIUS)
        if (enemy.x, enemy.y) != old:
            enemy.moving = True
        enemy.angle = math.atan2(player.y - enemy.y, player.x - enemy.x)

    def _strafe(self, dt, player, level):
        """Pas latéraux pendant le combat : plus dur à toucher."""
        enemy = self.enemy
        self.strafe_timer -= dt
        if self.strafe_timer <= 0.0:
            self.strafe_dir = -self.strafe_dir
            self.strafe_timer = random.uniform(0.6, 1.6)
        side = math.atan2(player.y - enemy.y, player.x - enemy.x) \
            + self.strafe_dir * math.pi / 2
        step = enemy.SPEED * 0.55 * dt
        old = (enemy.x, enemy.y)
        enemy.x, enemy.y = level.move_with_collisions(
            enemy.x, enemy.y, math.cos(side) * step, math.sin(side) * step,
            enemy.RADIUS)
        if (enemy.x, enemy.y) == old:
            self.strafe_dir = -self.strafe_dir  # bloqué par un mur : demi-tour
        else:
            enemy.moving = True
            enemy.angle = math.atan2(player.y - enemy.y, player.x - enemy.x)

    def _wander(self, dt, level):
        """Patrouille locale : petites marches aléatoires autour du poste."""
        enemy = self.enemy
        self.wander_timer -= dt
        if self.wander_target is None:
            if self.wander_timer <= 0.0:
                # choisit une case praticable proche
                for _ in range(8):
                    ang = random.uniform(0, 2 * math.pi)
                    r = random.uniform(1.0, 2.5)
                    tx = enemy.x + math.cos(ang) * r
                    ty = enemy.y + math.sin(ang) * r
                    if level.can_stand(tx, ty, enemy.RADIUS):
                        self.wander_target = (tx, ty)
                        self.wander_timer = 4.0  # délai max de trajet
                        break
                else:
                    self.wander_timer = random.uniform(2.0, 5.0)
            return
        self._move_towards(dt, self.wander_target, level, speed_mult=0.45)
        arrived = math.hypot(self.wander_target[0] - enemy.x,
                             self.wander_target[1] - enemy.y) < 0.3
        if arrived or self.wander_timer <= 0.0:
            self.wander_target = None
            self.wander_timer = random.uniform(2.0, 5.0)

    # ------------------------------------------------------------------
    # Combat
    # ------------------------------------------------------------------
    def _try_shoot(self, player, dist):
        """Tire sur le joueur si le temps de recharge est écoulé."""
        enemy = self.enemy
        if enemy.fire_cooldown > 0.0 or enemy.MELEE:
            return []
        enemy.fire_cooldown = enemy.FIRE_DELAY * random.uniform(0.85, 1.3)
        enemy.flash_timer = 0.12
        events = [("enemy_shot", enemy)]
        # Précision propre au type d'ennemi, décroissante avec la distance
        # (le sniper reste précis de loin mais paie le corps à corps).
        if random.random() < enemy.hit_chance(dist):
            damage = enemy.roll_damage(random)  # tient compte du niveau
            player.take_damage(damage)
            events.append(("player_hit", (enemy, player)))
        return events

    def _find_cover(self, player, level):
        """Cherche un point proche, praticable et hors de vue du joueur.

        On échantillonne des directions autour de l'ennemi (les plus
        éloignées du joueur d'abord) à plusieurs distances, et on garde le
        premier point sans ligne de vue avec le joueur.
        """
        enemy = self.enemy
        away = math.atan2(enemy.y - player.y, enemy.x - player.x)
        offsets = sorted(
            [i * (2 * math.pi / 12) for i in range(12)],
            key=lambda a: abs((a + math.pi) % (2 * math.pi) - math.pi),
        )
        for radius in (2.0, 3.0, 4.0):
            for offset in offsets:
                angle = away + offset
                cx = enemy.x + math.cos(angle) * radius
                cy = enemy.y + math.sin(angle) * radius
                if not level.can_stand(cx, cy, enemy.RADIUS):
                    continue
                if not has_line_of_sight(level, cx, cy, player.x, player.y):
                    return (cx, cy)
        return None
