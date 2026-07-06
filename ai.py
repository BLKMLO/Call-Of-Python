"""Intelligence artificielle des ennemis.

Machine à états simple, volontairement séparée des entités pour pouvoir
la réutiliser (ou la spécialiser) sur de futurs types d'ennemis :

    idle   : immobile, scrute ; passe en chasse s'il voit le joueur.
    chase  : se dirige vers le joueur (ou sa dernière position connue).
    attack : à portée avec ligne de vue : s'arrête et tire.
    cover  : quand ses PV sont bas, cherche un point hors de vue du joueur.

L'IA retourne une liste d'événements ("enemy_shot", "player_hit"...) que
`game.py` transforme en sons et effets visuels.
"""

import math
import random

from raycaster import has_line_of_sight


class EnemyAI:
    """Pilote un ennemi. Une instance par ennemi (garde peu d'état propre)."""

    LOSE_SIGHT_TIME = 3.0    # temps avant d'abandonner la poursuite (s)
    COVER_HEALTH = 35        # seuil de PV déclenchant la recherche de couverture
    COVER_DURATION = 2.6     # temps passé à couvert avant de repartir (s)

    def __init__(self, enemy):
        self.enemy = enemy
        self.lost_timer = 0.0
        self.took_cover = False  # une seule retraite par ennemi

    # ------------------------------------------------------------------
    def update(self, dt, player, level):
        """Fait avancer l'IA d'un pas de temps ; retourne les événements produits."""
        enemy = self.enemy
        events = []
        if not enemy.alive or not player.alive:
            return events

        enemy.update_timers(dt)
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
        if state != "cover" and not self.took_cover and enemy.health <= self.COVER_HEALTH:
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
        elif state == "chase":
            if sees_player and dist < enemy.ATTACK_RANGE:
                enemy.ai_state = "attack"
            elif not sees_player and self.lost_timer > self.LOSE_SIGHT_TIME:
                enemy.ai_state = "idle"
                enemy.last_seen = None
        elif state == "attack":
            if not sees_player or dist > enemy.ATTACK_RANGE * 1.2:
                enemy.ai_state = "chase"

        # --- comportements -------------------------------------------------
        state = enemy.ai_state
        if state == "chase":
            target = (player.x, player.y) if sees_player else enemy.last_seen
            if target is not None:
                self._move_towards(dt, target, level)
        elif state == "attack":
            enemy.angle = math.atan2(player.y - enemy.y, player.x - enemy.x)
            events += self._try_shoot(player, dist)
        elif state == "cover":
            if enemy.cover_target is not None:
                self._move_towards(dt, enemy.cover_target, level)
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

    # ------------------------------------------------------------------
    # Actions élémentaires
    # ------------------------------------------------------------------
    def _move_towards(self, dt, target, level):
        """Avance en ligne droite vers la cible, en glissant le long des murs."""
        enemy = self.enemy
        dx, dy = target[0] - enemy.x, target[1] - enemy.y
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            return
        enemy.angle = math.atan2(dy, dx)
        step = enemy.SPEED * dt / dist
        enemy.x, enemy.y = level.move_with_collisions(
            enemy.x, enemy.y, dx * step, dy * step, enemy.RADIUS
        )

    def _try_shoot(self, player, dist):
        """Tire sur le joueur si le temps de recharge est écoulé."""
        enemy = self.enemy
        if enemy.fire_cooldown > 0.0:
            return []
        enemy.fire_cooldown = enemy.FIRE_DELAY * random.uniform(0.85, 1.3)
        enemy.flash_timer = 0.12
        events = [("enemy_shot", enemy)]
        # Précision décroissante avec la distance : de ~75 % au contact
        # à ~25 % à la portée maximale.
        hit_chance = max(0.25, 0.75 - 0.5 * dist / enemy.ATTACK_RANGE)
        if random.random() < hit_chance:
            damage = random.randint(*enemy.DAMAGE)
            player.take_damage(damage)
            events.append(("player_hit", damage))
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
