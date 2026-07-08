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
    SPRINT_MULT = 1.5    # multiplicateur de vitesse en sprint
    RADIUS = 0.25        # rayon de collision
    MAX_PITCH = 0.35     # amplitude de la visée verticale (fraction d'écran)

    def __init__(self, x, y):
        super().__init__(x, y, max_health=100)
        self.pitch = 0.0        # visée verticale (fraction d'écran, +haut)
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
    def rotate(self, mouse_dx, mouse_dy, mouse_factor):
        """Tourne la vue avec la souris : horizontal = cap, vertical = tangage."""
        self.angle = (self.angle + mouse_dx * mouse_factor) % (2 * math.pi)
        self.pitch = max(-self.MAX_PITCH, min(
            self.MAX_PITCH, self.pitch - mouse_dy * mouse_factor * 0.55))

    def move(self, dt, keys_pressed, bindings, level):
        """Déplacement ZQSD/WASD relatif à la direction de vue, avec collisions.

        Retourne True si le joueur a effectivement bougé (pour l'animation).
        """
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
            return False

        # Normalise pour que la diagonale ne soit pas plus rapide.
        length = math.hypot(forward, strafe)
        speed = self.SPEED * dt / length
        if keys_pressed[bindings["sprint"]]:
            speed *= self.SPRINT_MULT
        cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)
        dx = (forward * cos_a - strafe * sin_a) * speed
        dy = (forward * sin_a + strafe * cos_a) * speed
        old = (self.x, self.y)
        self.x, self.y = level.move_with_collisions(self.x, self.y, dx, dy, self.RADIUS)
        return (self.x, self.y) != old

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
    DEAD_HEIGHT = 0.2      # hauteur du cadavre au sol
    MAX_HEALTH = 100

    DETECT_RANGE = 11.0    # distance de détection du joueur
    ATTACK_RANGE = 7.0     # distance à laquelle il ouvre le feu
    FIRE_DELAY = 1.1       # temps entre deux tirs (s)
    DAMAGE = (6, 13)       # dégâts min/max par balle
    ACCURACY = 0.75        # chance de toucher à bout portant
    ACCURACY_FALLOFF = 0.5 # perte de précision avec la distance
    TAKES_COVER = True     # cherche un abri quand il est blessé
    IS_BOSS = False
    MELEE = False          # fonce au contact au lieu de tirer (kamikaze)
    EXPLODES = False       # explose à la mort / au contact
    EXPLOSION_RADIUS = 1.8
    EXPLOSION_DAMAGE = 34
    KEEP_DISTANCE = False  # recule si le joueur approche (sniper)
    MIN_RANGE = 0.0

    def __init__(self, x, y, health_mult=1.0, damage_mult=1.0):
        super().__init__(x, y, max_health=round(self.MAX_HEALTH * health_mult))
        self.damage_mult = damage_mult
        self.flash_timer = 0.0   # affiche la pose "tir" du sprite
        self.hurt_timer = 0.0    # flash blanc quand il encaisse une balle
        self.moving = False      # l'IA le met à jour (pose "marche")
        self.anim_time = 0.0
        self.exploded = False    # un kamikaze ne détone qu'une fois
        self.net_id = None       # identifiant réseau (coop LAN, côté hôte)
        # État piloté par ai.EnemyAI :
        self.ai_state = "idle"
        self.ai_timer = 0.0
        self.fire_cooldown = 0.0
        self.last_seen = None    # dernière position connue du joueur
        self.cover_target = None # point de couverture visé

    def current_sprite(self, player=None):
        """Pose selon l'état ET l'angle de vue : on voit les ennemis de
        face, de dos ou de profil selon leur orientation par rapport au
        joueur (le profil opposé est obtenu par miroir). La marche est un
        cycle à deux frames ; un ennemi qui encaisse flashe en blanc."""
        if not self.alive:
            return assets.get(f"enemy_{self.KIND}_dead")
        if self.flash_timer > 0.0:
            # Quand il tire, il fait face au joueur : pose de face armée.
            return assets.get(f"enemy_{self.KIND}_fire")

        if self.moving:
            pose = "walk" if int(self.anim_time * 6) % 2 == 0 else "walk2"
        else:
            pose = "idle"
        suffix, flipped = "", False
        if player is not None:
            # Angle entre la direction regardée par l'ennemi et le joueur.
            to_player = math.atan2(player.y - self.y, player.x - self.x)
            diff = (self.angle - to_player + math.pi) % (2 * math.pi) - math.pi
            if abs(diff) > 3 * math.pi / 4:
                suffix = "_back"            # il nous tourne le dos
            elif abs(diff) > math.pi / 4:
                suffix = "_side"            # profil (miroir selon le côté)
                flipped = diff > 0
        name = f"enemy_{self.KIND}_{pose}{suffix}"
        if self.hurt_timer > 0.0:
            return assets.get_tinted(name, flipped)
        return assets.get(name, flipped)

    def take_damage(self, amount):
        died = super().take_damage(amount)
        if died:
            # Le billboard devient un cadavre bas posé au sol.
            self.SPRITE_HEIGHT = self.DEAD_HEIGHT
            self.moving = False
        else:
            self.hurt_timer = 0.09   # flash blanc bref
        return died

    def roll_damage(self, rng):
        low, high = self.DAMAGE
        return round(rng.randint(low, high) * self.damage_mult)

    def hit_chance(self, dist):
        """Chance de toucher à cette distance (les snipers la surchargent
        via ACCURACY / ACCURACY_FALLOFF)."""
        return max(0.25, self.ACCURACY
                   - self.ACCURACY_FALLOFF * dist / self.ATTACK_RANGE)

    def update_timers(self, dt):
        self.flash_timer = max(0.0, self.flash_timer - dt)
        self.hurt_timer = max(0.0, self.hurt_timer - dt)
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


class Kamikaze(Enemy):
    """Fanatique au gilet explosif : fragile mais très rapide, il fonce
    sur le joueur et explose au contact — ou quand on l'abat (les
    explosions blessent aussi les autres ennemis : visez la grappe)."""
    KIND = "kamikaze"
    SPEED = 3.4            # plus vite que la marche du joueur (3.2)
    MAX_HEALTH = 40
    DAMAGE = (0, 0)        # ne tire jamais
    TAKES_COVER = False
    MELEE = True
    EXPLODES = True


class Sniper(Enemy):
    """Tireur d'élite : mortel de loin, il recule si on s'approche."""
    KIND = "sniper"
    SPEED = 1.5
    MAX_HEALTH = 70
    DETECT_RANGE = 14.0
    ATTACK_RANGE = 12.0
    FIRE_DELAY = 2.3
    DAMAGE = (18, 30)
    ACCURACY = 0.9         # redoutable même à longue portée...
    ACCURACY_FALLOFF = 0.25
    KEEP_DISTANCE = True
    MIN_RANGE = 5.0        # ... mais fébrile au corps à corps


class Boss(Enemy):
    """Le Colosse : boss du dernier niveau. Énorme, implacable, ne se
    cache jamais — il avance."""
    KIND = "boss"
    SPEED = 1.15
    RADIUS = 0.38
    MAX_HEALTH = 550
    SPRITE_HEIGHT = 0.95
    DEAD_HEIGHT = 0.26
    DAMAGE = (12, 20)
    FIRE_DELAY = 0.55
    ATTACK_RANGE = 8.0
    DETECT_RANGE = 14.0
    TAKES_COVER = False
    IS_BOSS = True


class RemotePlayer(Enemy):
    """Coéquipier du multijoueur LAN : rendu comme un billboard directionnel
    (uniforme bleu), piloté par le réseau — aucune IA attachée."""
    KIND = "ally"
    MAX_HEALTH = 100

    def __init__(self, pid, x, y):
        super().__init__(x, y)
        self.pid = pid


ENEMY_TYPES = {"grunt": Grunt, "soldier": Soldier, "heavy": Heavy,
               "kamikaze": Kamikaze, "sniper": Sniper, "boss": Boss}


# Décors : sprite, hauteur monde du billboard. Tous bloquent le passage
# (leur case est infranchissable) mais laissent passer balles et regards.
PROP_SPECS = {
    "car":      {"sprite": "prop_car",      "height": 0.5},
    "bench":    {"sprite": "prop_bench",    "height": 0.34},
    "tribune":  {"sprite": "prop_tribune",  "height": 0.62},
    "labtable": {"sprite": "prop_labtable", "height": 0.5},
    "rock":     {"sprite": "prop_rock",     "height": 0.3},
}


class Prop:
    """Décor statique rendu en billboard (voiture, pupitre, paillasse,
    rocher lunaire...). Le sens est alterné selon la case pour varier."""

    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        self.kind = kind
        spec = PROP_SPECS[kind]
        self.sprite_name = spec["sprite"]
        self.SPRITE_HEIGHT = spec["height"]
        self.flipped = (int(x) + int(y)) % 2 == 1

    def current_sprite(self, player=None):
        return assets.get(self.sprite_name, self.flipped)


class Pickup:
    """Objet posé au sol (arme, trousse de soins ou pack de vie caché),
    rendu en billboard flottant qui oscille doucement.

    Les packs de vie ("lifepack") sont rares et cachés : ils n'apparaissent
    pas sur la minimap, soignent entièrement, et scintillent de particules
    vertes qui les trahissent quand on passe à proximité."""

    SPRITE_HEIGHT = 0.34

    def __init__(self, x, y, kind, level_index):
        self.x = x
        self.y = y
        self.kind = kind              # "weapon:<id>", "medkit" ou "lifepack"
        self.level_index = level_index
        self.taken = False
        self.hidden = kind == "lifepack"     # absent de la minimap
        self.bob = (x * 7 + y * 13) % 6.28  # phase d'oscillation propre
        if kind in ("medkit", "lifepack"):
            self.sprite_name = "pickup_" + kind
        else:
            self.sprite_name = "pickup_" + kind.split(":", 1)[1]

    def current_sprite(self, player=None):
        return assets.get(self.sprite_name)

    def bob_offset(self, time_s):
        """Décalage vertical (unités monde) pour l'oscillation."""
        return 0.06 * math.sin(time_s * 2.5 + self.bob)
