"""Entités du jeu : joueur, ennemis (3 types), objets à ramasser.

Les sprites viennent d'`assets.py` (pixel-art façon Minecraft) : chaque
ennemi possède trois poses (repos / marche / tir) affichées en billboard
par le raycaster. Le joueur porte un inventaire d'armes interchangeables.
"""

import math

import pygame

import assets
from weapons import WEAPON_ORDER, WEAPON_SPECS, Weapon


class Entity:
    """Base commune : position, angle de vue, points de vie."""

    def __init__(self, x, y, max_health):
        self.x = x
        self.y = y
        self.angle = 0.0
        self.max_health = max_health
        self.health = max_health

    @property
    def alive(self):
        return self.health > 0

    def take_damage(self, amount):
        """Inflige des dégâts ; retourne True si l'entité vient de mourir."""
        was_alive = self.alive
        self.health = max(0, self.health - amount)
        return was_alive and not self.alive

    def distance_to(self, other):
        return math.hypot(other.x - self.x, other.y - self.y)


class Player(Entity):
    """Le personnage jouable : déplacement clavier, visée souris, arsenal."""

    SPEED = 3.2          # vitesse de déplacement (cases / s)
    RADIUS = 0.25        # rayon de collision

    def __init__(self, x, y):
        super().__init__(x, y, max_health=100)
        self.weapons = [Weapon(WEAPON_SPECS["pistol"])]  # arme de départ
        self.weapon_index = 0
        self.hurt_flash = 0.0   # minuterie du flash rouge quand on est touché

    # ------------------------------------------------------------------
    # Arsenal
    # ------------------------------------------------------------------
    @property
    def weapon(self):
        return self.weapons[self.weapon_index]

    def add_weapon(self, weapon_id, level):
        """Ramasse une arme : nouvelle, amélioration, ou simple recharge.

        Retourne "new", "upgrade" ou "ammo" pour le retour visuel/sonore.
        """
        for i, owned in enumerate(self.weapons):
            if owned.spec.id != weapon_id:
                continue
            if level > owned.level:            # même arme, meilleur niveau
                self.weapons[i] = Weapon(WEAPON_SPECS[weapon_id], level)
                self.weapon_index = i
                return "upgrade"
            owned.ammo = owned.spec.magazine_size
            owned.reloading = 0.0
            return "ammo"
        self.weapons.append(Weapon(WEAPON_SPECS[weapon_id], level))
        # garde l'arsenal trié selon l'ordre des emplacements (touches 1..4)
        self.weapons.sort(key=lambda w: WEAPON_ORDER.index(w.spec.id))
        self.weapon_index = next(
            i for i, w in enumerate(self.weapons) if w.spec.id == weapon_id)
        return "new"

    def select_weapon(self, slot):
        """Sélectionne l'emplacement `slot` (0..3) si l'arme est possédée."""
        for i, owned in enumerate(self.weapons):
            if WEAPON_ORDER.index(owned.spec.id) == slot:
                self.weapon_index = i
                return True
        return False

    def cycle_weapon(self, direction):
        self.weapon_index = (self.weapon_index + direction) % len(self.weapons)

    # ------------------------------------------------------------------
    def rotate(self, mouse_dx, mouse_factor):
        """Tourne la vue selon le mouvement horizontal de la souris."""
        self.angle = (self.angle + mouse_dx * mouse_factor) % (2 * math.pi)

    def move(self, dt, keys_pressed, bindings, level):
        """Déplacement ZQSD/WASD relatif à la direction de vue, avec collisions."""
        forward = 0.0
        strafe = 0.0
        if keys_pressed[bindings["avancer"]]:
            forward += 1.0
        if keys_pressed[bindings["reculer"]]:
            forward -= 1.0
        if keys_pressed[bindings["droite"]]:
            strafe += 1.0
        if keys_pressed[bindings["gauche"]]:
            strafe -= 1.0
        if forward == 0.0 and strafe == 0.0:
            return

        # Normalise pour que la diagonale ne soit pas plus rapide.
        length = math.hypot(forward, strafe)
        speed = self.SPEED * dt / length
        cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)
        dx = (forward * cos_a - strafe * sin_a) * speed
        dy = (forward * sin_a + strafe * cos_a) * speed
        self.x, self.y = level.move_with_collisions(self.x, self.y, dx, dy, self.RADIUS)

    def take_damage(self, amount):
        self.hurt_flash = 0.35
        return super().take_damage(amount)

    def update(self, dt):
        self.weapon.update(dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)


class Enemy(Entity):
    """Ennemi de base, piloté par `ai.EnemyAI`.

    Les sous-classes (`Grunt`, `Soldier`, `Heavy`) ne changent que les
    statistiques et la clé de sprite — l'IA est partagée.
    """

    KIND = "soldier"       # préfixe des sprites : enemy_<KIND>_<pose>.png
    SPEED = 1.9            # vitesse de déplacement (cases / s)
    RADIUS = 0.3           # rayon de collision et de "hitbox"
    SPRITE_HEIGHT = 0.72   # hauteur du billboard (en unités monde)
    MAX_HEALTH = 100

    DETECT_RANGE = 11.0    # distance de détection du joueur
    ATTACK_RANGE = 7.0     # distance à laquelle il ouvre le feu
    FIRE_DELAY = 1.1       # temps entre deux tirs (s)
    DAMAGE = (6, 13)       # dégâts min/max par balle

    def __init__(self, x, y, health_mult=1.0, damage_mult=1.0):
        super().__init__(x, y, max_health=round(self.MAX_HEALTH * health_mult))
        self.damage_mult = damage_mult
        self.flash_timer = 0.0   # affiche la pose "tir" du sprite
        self.moving = False      # l'IA le met à jour (pose "marche")
        self.anim_time = 0.0
        # État piloté par ai.EnemyAI :
        self.ai_state = "idle"
        self.ai_timer = 0.0
        self.fire_cooldown = 0.0
        self.last_seen = None    # dernière position connue du joueur
        self.cover_target = None # point de couverture visé

    def current_sprite(self):
        """Pose selon l'état : tir > marche (alternée) > repos."""
        if self.flash_timer > 0.0:
            pose = "fire"
        elif self.moving and int(self.anim_time * 5) % 2 == 0:
            pose = "walk"
        else:
            pose = "idle"
        return assets.get(f"enemy_{self.KIND}_{pose}")

    def roll_damage(self, rng):
        low, high = self.DAMAGE
        return round(rng.randint(low, high) * self.damage_mult)

    def update_timers(self, dt):
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.ai_timer += dt
        if self.moving:
            self.anim_time += dt


class Grunt(Enemy):
    """Milicien : faible et lent, mais tenace."""
    KIND = "grunt"
    SPEED = 1.7
    MAX_HEALTH = 80
    DAMAGE = (5, 10)
    FIRE_DELAY = 1.3


class Soldier(Enemy):
    """Soldat entraîné : l'ennemi de référence."""
    KIND = "soldier"


class Heavy(Enemy):
    """Soldat lourd : lent, blindé, frappe fort."""
    KIND = "heavy"
    SPEED = 1.3
    MAX_HEALTH = 180
    SPRITE_HEIGHT = 0.8
    DAMAGE = (10, 18)
    FIRE_DELAY = 0.9
    ATTACK_RANGE = 6.0


ENEMY_TYPES = {"grunt": Grunt, "soldier": Soldier, "heavy": Heavy}


class Pickup:
    """Objet posé au sol (arme ou trousse de soins), rendu en billboard
    flottant qui oscille doucement."""

    SPRITE_HEIGHT = 0.34

    def __init__(self, x, y, kind, level_index):
        self.x = x
        self.y = y
        self.kind = kind              # "weapon:<id>" ou "medkit"
        self.level_index = level_index
        self.taken = False
        self.bob = (x * 7 + y * 13) % 6.28  # phase d'oscillation propre
        if kind == "medkit":
            self.sprite_name = "pickup_medkit"
        else:
            self.sprite_name = "pickup_" + kind.split(":", 1)[1]

    def current_sprite(self):
        return assets.get(self.sprite_name)

    def bob_offset(self, time_s):
        """Décalage vertical (unités monde) pour l'oscillation."""
        return 0.06 * math.sin(time_s * 2.5 + self.bob)
