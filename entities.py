"""Entités du jeu : joueur et ennemis.

Les deux héritent d'`Entity` (position, vie, dégâts). Les sprites des
ennemis sont dessinés procéduralement (aucun fichier image externe) :
une silhouette de soldat, avec une variante "en train de tirer".
"""

import math

import pygame

from weapons import Weapon


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
    """Le personnage jouable : déplacement clavier, visée souris, tir."""

    SPEED = 3.2          # vitesse de déplacement (cases / s)
    RADIUS = 0.25        # rayon de collision

    def __init__(self, x, y):
        super().__init__(x, y, max_health=100)
        self.weapon = Weapon()
        self.hurt_flash = 0.0   # minuterie du flash rouge quand on est touché

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
    """Ennemi de base : soldat au corps-à-distance, piloté par `ai.EnemyAI`.

    Pour créer un nouveau type d'ennemi, hériter de cette classe et ajuster
    les constantes (vitesse, dégâts, portées) et/ou les couleurs du sprite.
    """

    SPEED = 1.9            # vitesse de déplacement (cases / s)
    RADIUS = 0.3           # rayon de collision et de "hitbox"
    SPRITE_HEIGHT = 0.72   # hauteur du billboard (en unités monde)

    DETECT_RANGE = 11.0    # distance de détection du joueur
    ATTACK_RANGE = 7.0     # distance à laquelle il ouvre le feu
    FIRE_DELAY = 1.1       # temps entre deux tirs (s)
    DAMAGE = (6, 13)       # dégâts min/max par balle

    BODY_COLOR = (72, 92, 60)     # treillis vert
    ACCENT_COLOR = (46, 58, 38)

    _sprite_cache = {}

    def __init__(self, x, y):
        super().__init__(x, y, max_health=100)
        self.flash_timer = 0.0   # affiche la variante "tir" du sprite
        # L'état de l'IA est stocké sur l'ennemi mais piloté par ai.EnemyAI,
        # ce qui permet de partager une même IA entre plusieurs types.
        self.ai_state = "idle"
        self.ai_timer = 0.0
        self.fire_cooldown = 0.0
        self.last_seen = None    # dernière position connue du joueur
        self.cover_target = None # point de couverture visé

    # ------------------------------------------------------------------
    # Sprites procéduraux
    # ------------------------------------------------------------------
    @classmethod
    def _build_sprites(cls):
        """Dessine les deux poses (normale / en train de tirer) une seule fois."""
        poses = []
        for firing in (False, True):
            surf = pygame.Surface((64, 96), pygame.SRCALPHA)
            body, accent = cls.BODY_COLOR, cls.ACCENT_COLOR
            skin = (196, 158, 122)
            # jambes
            pygame.draw.rect(surf, accent, (22, 62, 8, 30))
            pygame.draw.rect(surf, accent, (34, 62, 8, 30))
            # torse
            pygame.draw.rect(surf, body, (18, 30, 28, 36), border_radius=4)
            # tête + casque
            pygame.draw.circle(surf, skin, (32, 20), 9)
            pygame.draw.rect(surf, accent, (22, 8, 20, 9), border_radius=3)
            # bras + arme pointée vers le joueur
            pygame.draw.rect(surf, body, (12, 36, 10, 16), border_radius=3)
            pygame.draw.rect(surf, (30, 30, 32), (8, 40, 26, 6))
            if firing:
                # éclair de bouche : signale au joueur qu'on lui tire dessus
                pygame.draw.circle(surf, (255, 220, 90), (6, 43), 7)
                pygame.draw.circle(surf, (255, 255, 200), (6, 43), 3)
            poses.append(surf)
        return poses

    def current_sprite(self):
        if type(self) not in Enemy._sprite_cache:
            Enemy._sprite_cache[type(self)] = self._build_sprites()
        normal, firing = Enemy._sprite_cache[type(self)]
        return firing if self.flash_timer > 0.0 else normal

    # ------------------------------------------------------------------
    def update_timers(self, dt):
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.ai_timer += dt
