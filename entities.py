"""Entités du jeu : joueur, ennemis (3 types), objets à ramasser.

Les sprites viennent d'`assets.py` (pixel-art façon Minecraft) : chaque
ennemi possède trois poses (repos / marche / tir) affichées en billboard
par le raycaster. Le joueur porte un inventaire d'armes interchangeables.
"""

import math

import pygame

import assets
from weapons import WEAPON_ORDER, WEAPON_SPECS, Weapon


def _move_with_substeps(level, x, y, dx, dy, radius):
    """Découpe une impulsion rapide pour qu'un pic de `dt` ne saute pas un mur."""
    distance = math.hypot(dx, dy)
    steps = max(1, math.ceil(distance / max(0.08, radius * 0.5)))
    step_x, step_y = dx / steps, dy / steps
    for _ in range(steps):
        next_x, next_y = level.move_with_collisions(
            x, y, step_x, step_y, radius,
        )
        if (next_x, next_y) == (x, y):
            break
        x, y = next_x, next_y
    return x, y


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
    ADS_MULT = 0.5       # ralentissement du déplacement en visée
    ADS_ZOOM = 1.7       # grossissement de la lunette
    RADIUS = 0.25        # rayon de collision
    MAX_PITCH = 0.35     # amplitude de la visée verticale (fraction d'écran)
    SHIELD_DURATION = 3.0   # bouclier temporaire à l'arrivée sur un niveau (s)
    ROLL_DURATION = 0.55    # mouvement total : amorce + esquive + récupération
    ROLL_COOLDOWN = 0.0     # enchaînable dès la fin, jamais pendant l'action
    ROLL_SPEED = 4.55       # conserve ~2,5 cases malgré la durée ajustée
    ROLL_IFRAME_START = 0.08
    ROLL_IFRAME_END = 0.38  # 0,30 s d'i-frames au cœur du mouvement

    def __init__(self, x, y):
        super().__init__(x, y, max_health=100)
        self.pitch = 0.0        # visée verticale (fraction d'écran, +haut)
        self.aiming = False     # visée maintenue (clic droit)
        self.ads = 0.0          # transition de visée lissée (0 → 1)
        self.shield = 0.0       # secondes de bouclier (invulnérabilité) restantes
        self.weapons = [Weapon(WEAPON_SPECS["pistol"])]  # arme de départ
        self.weapon_index = 0
        self.hurt_flash = 0.0   # minuterie du flash rouge quand on est touché
        self.roll_timer = 0.0
        self.roll_cooldown = 0.0
        self.roll_invuln = 0.0
        self.roll_dx = 0.0
        self.roll_dy = 0.0
        self.roll_strafe = 0.0   # inclinaison de caméra (-gauche, +droite)
        self.roll_sequence = 0   # identifie chaque déclenchement en coop LAN

    @property
    def zoom(self):
        """Facteur de zoom courant (interpolé), 1.0 hanche → ADS_ZOOM visée."""
        return 1.0 + (self.ADS_ZOOM - 1.0) * self.ads

    @property
    def rolling(self):
        return self.roll_timer > 0.0

    @property
    def roll_progress(self):
        if not self.rolling:
            return 0.0
        return 1.0 - self.roll_timer / self.ROLL_DURATION

    @property
    def roll_invulnerable(self):
        """Fenêtre juste : vulnérable au démarrage et à la récupération."""
        if not self.rolling:
            return False
        elapsed = self.ROLL_DURATION - self.roll_timer
        return self.ROLL_IFRAME_START <= elapsed < self.ROLL_IFRAME_END

    def activate_shield(self):
        """Bouclier temporaire : le joueur est invulnérable à l'arrivée sur
        un niveau (le temps de repérer les lieux avant le premier tir)."""
        self.shield = self.SHIELD_DURATION

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
        """Tourne la vue avec la souris : horizontal = cap, vertical = tangage.

        En visée, la sensibilité est réduite proportionnellement au zoom
        (visée plus précise)."""
        factor = mouse_factor / self.zoom
        self.angle = (self.angle + mouse_dx * factor) % (2 * math.pi)
        self.pitch = max(-self.MAX_PITCH, min(
            self.MAX_PITCH, self.pitch - mouse_dy * factor * 0.55))

    def move(self, dt, keys_pressed, bindings, level):
        """Déplacement ZQSD/WASD relatif à la direction de vue, avec collisions.

        Retourne True si le joueur a effectivement bougé (pour l'animation).
        """
        if self.rolling:
            old = (self.x, self.y)
            distance = self.ROLL_SPEED * min(dt, self.roll_timer)
            self.x, self.y = _move_with_substeps(
                level, self.x, self.y,
                self.roll_dx * distance, self.roll_dy * distance,
                self.RADIUS,
            )
            moved = (self.x, self.y) != old
            if not moved:              # mur de face : pas d'i-frames sur place
                self.roll_timer = 0.0
                self.roll_invuln = 0.0
            return moved

        forward, strafe = self._movement_axes(keys_pressed, bindings)
        if forward == 0.0 and strafe == 0.0:
            return False

        # Normalise pour que la diagonale ne soit pas plus rapide.
        length = math.hypot(forward, strafe)
        speed = self.SPEED * dt / length
        if self.aiming:
            speed *= self.ADS_MULT           # on avance au ralenti en visée
        cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)
        dx = (forward * cos_a - strafe * sin_a) * speed
        dy = (forward * sin_a + strafe * cos_a) * speed
        old = (self.x, self.y)
        self.x, self.y = level.move_with_collisions(self.x, self.y, dx, dy, self.RADIUS)
        return (self.x, self.y) != old

    @staticmethod
    def _movement_axes(keys_pressed, bindings):
        forward = float(keys_pressed[bindings["avancer"]])
        forward -= float(keys_pressed[bindings["reculer"]])
        strafe = float(keys_pressed[bindings["droite"]])
        strafe -= float(keys_pressed[bindings["gauche"]])
        return forward, strafe

    def start_roll(self, keys_pressed, bindings):
        """Déclenche une roulade dans la direction tenue, en avant par défaut."""
        if not self.alive or self.rolling or self.roll_cooldown > 0.0:
            return False
        forward, strafe = self._movement_axes(keys_pressed, bindings)
        if forward == 0.0 and strafe == 0.0:
            forward = 1.0
        length = math.hypot(forward, strafe)
        forward, strafe = forward / length, strafe / length
        cos_a, sin_a = math.cos(self.angle), math.sin(self.angle)
        self.roll_dx = forward * cos_a - strafe * sin_a
        self.roll_dy = forward * sin_a + strafe * cos_a
        self.roll_strafe = strafe
        self.roll_timer = self.ROLL_DURATION
        self.roll_invuln = 0.0       # compatibilité d'état ; voir propriété ci-dessus
        self.roll_cooldown = self.ROLL_COOLDOWN
        self.roll_sequence += 1
        self.aiming = False
        return True

    def take_damage(self, amount):
        if self.shield > 0.0 or self.roll_invulnerable:
            return False              # bouclier / roulade : aucun dégât
        self.hurt_flash = 0.35
        return super().take_damage(amount)

    def update(self, dt):
        self.weapon.update(dt)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        self.shield = max(0.0, self.shield - dt)
        self.roll_timer = max(0.0, self.roll_timer - dt)
        self.roll_invuln = 0.0
        self.roll_cooldown = max(0.0, self.roll_cooldown - dt)
        # Transition de visée lissée (montée/descente de lunette).
        target = 1.0 if self.aiming else 0.0
        self.ads += (target - self.ads) * min(1.0, dt * 12)
        if abs(self.ads - target) < 0.02:
            self.ads = target


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
    USES_COVER = False     # tactique : alterne couverture et sorties pour tirer
    FLANKS = False         # manoeuvre pour attaquer par le flanc/les arrières
    IS_BOSS = False
    MELEE = False          # fonce au contact au lieu de tirer (kamikaze)
    EXPLODES = False       # explose à la mort / au contact
    EXPLOSION_RADIUS = 1.8
    EXPLOSION_DAMAGE = 34
    KEEP_DISTANCE = False  # recule si le joueur approche (sniper)
    MIN_RANGE = 0.0
    AIM_DELAY = 0.0        # anticipation avant le tir (sniper uniquement)
    CAN_ROLL = False        # le soldat entraîné est le seul à esquiver
    ROLL_DURATION = 1.0
    ROLL_COOLDOWN = 3.0
    ROLL_SPEED = 2.8

    def __init__(self, x, y, health_mult=1.0, damage_mult=1.0):
        super().__init__(x, y, max_health=round(self.MAX_HEALTH * health_mult))
        # Les nouvelles silhouettes n'occupent pas toujours les 96 pixels de
        # haut de leur toile. La taille physique porte sur le personnage
        # visible, pas sur les marges transparentes du PNG.
        target_height = type(self).SPRITE_HEIGHT
        self.SPRITE_HEIGHT = _height_for_visible_height(
            f"enemy_{self.KIND}_idle", target_height,
        )
        # Le générateur historique occupait 75 % de la toile des cadavres.
        self._dead_sprite_height = _height_for_visible_height(
            f"enemy_{self.KIND}_dead", type(self).DEAD_HEIGHT * 0.75,
        )
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
        self.aiming = False       # pose/télégraphie d'un tir en préparation
        self.aim_timer = 0.0      # temps restant avant que le tir parte
        self.last_seen = None    # dernière position connue du joueur
        self.cover_target = None # point de couverture visé
        self.roll_timer = 0.0
        self.roll_cooldown = 0.0
        self.roll_invuln = 0.0
        self.roll_dx = 0.0
        self.roll_dy = 0.0
        # Demande consommée par l'IA après la résolution complète du tir.
        # Cela évite qu'une roulade déclenchée par le premier plomb d'un
        # fusil à pompe annule artificiellement les plombs simultanés.
        self.hit_roll_request = None

    @property
    def rolling(self):
        return self.roll_timer > 0.0

    @property
    def roll_progress(self):
        if not self.rolling:
            return 0.0
        return 1.0 - self.roll_timer / self.ROLL_DURATION

    def current_sprite(self, player=None):
        """Pose selon l'état ET l'angle de vue : on voit les ennemis de
        face, de dos ou de profil selon leur orientation par rapport au
        joueur (le profil opposé est obtenu par miroir). La marche est un
        cycle à deux frames ; un ennemi qui encaisse flashe en blanc."""
        if not self.alive:
            return assets.get(f"enemy_{self.KIND}_dead")
        if self.rolling and self.KIND == "soldier":
            frame = min(2, int(self.roll_progress * 3))
            return assets.get(f"enemy_soldier_roll_{frame}")
        if self.flash_timer > 0.0:
            # Quand il tire, il fait face au joueur : pose de face armée.
            return assets.get(f"enemy_{self.KIND}_fire")
        if self.aiming and self.KIND == "sniper":
            # Le sniper avertit clairement son tir en posant un genou à terre.
            return assets.get("enemy_sniper_aim")

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
        if self.roll_invuln > 0.0:
            return False
        died = super().take_damage(amount)
        if died:
            # Le billboard devient un cadavre bas posé au sol.
            self.SPRITE_HEIGHT = self._dead_sprite_height
            self.moving = False
            self.cancel_aim()
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
        self.roll_timer = max(0.0, self.roll_timer - dt)
        self.roll_invuln = max(0.0, self.roll_invuln - dt)
        self.roll_cooldown = max(0.0, self.roll_cooldown - dt)
        if self.aiming:
            self.aim_timer = max(0.0, self.aim_timer - dt)
        self.ai_timer += dt
        if self.moving:
            self.anim_time += dt

    def cancel_aim(self):
        """Abandonne une anticipation de tir devenue invalide."""
        self.aiming = False
        self.aim_timer = 0.0

    def start_roll(self, dx, dy):
        """Démarre une esquive collisionnée ; retourne False si indisponible."""
        length = math.hypot(dx, dy)
        if (not self.alive or not self.CAN_ROLL or self.rolling
                or self.roll_cooldown > 0.0 or length < 1e-6):
            return False
        self.roll_dx, self.roll_dy = dx / length, dy / length
        self.roll_timer = self.ROLL_DURATION
        self.roll_invuln = self.ROLL_DURATION
        self.roll_cooldown = self.ROLL_COOLDOWN
        self.moving = False
        self.cancel_aim()
        return True

    def advance_roll(self, dt, level):
        """Applique l'impulsion de roulade sans permettre de traverser un mur."""
        if not self.rolling:
            return False
        old = (self.x, self.y)
        distance = self.ROLL_SPEED * min(dt, self.roll_timer)
        self.x, self.y = _move_with_substeps(
            level, self.x, self.y,
            self.roll_dx * distance, self.roll_dy * distance, self.RADIUS,
        )
        if (self.x, self.y) == old:
            self.roll_timer = 0.0
            self.roll_invuln = 0.0
            return False
        return True


class Grunt(Enemy):
    """Milicien : faible mais très mobile, tout en gardant un tir lent."""
    KIND = "grunt"
    SPEED = 2.55          # +50 %, FIRE_DELAY reste volontairement inchangé
    MAX_HEALTH = 80
    DAMAGE = (5, 10)
    FIRE_DELAY = 1.3


class Soldier(Enemy):
    """Soldat entraîné : l'ennemi de référence — assez malin pour se mettre
    à couvert entre deux tirs et pour manoeuvrer par le flanc quand il perd
    le joueur de vue au lieu de foncer bêtement vers sa dernière position."""
    KIND = "soldier"
    USES_COVER = True
    FLANKS = True
    CAN_ROLL = True


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
    """Tireur d'élite : mortel de loin, il recule si on s'approche. Le plus
    discipliné des ennemis : il se planque après chaque tir et ne ressort
    qu'un instant pour retirer, ce qui le rend dur à repérer et à toucher."""
    KIND = "sniper"
    SPEED = 1.5
    MAX_HEALTH = 70
    DETECT_RANGE = 14.0
    ATTACK_RANGE = 12.0
    FIRE_DELAY = 2.3
    DAMAGE = (17, 28)      # légèrement réduit (~5 %) pour l'équilibrage
    ACCURACY = 0.9         # redoutable même à longue portée...
    ACCURACY_FALLOFF = 0.25
    KEEP_DISTANCE = True
    MIN_RANGE = 5.0        # ... mais fébrile au corps à corps
    USES_COVER = True
    AIM_DELAY = 0.75       # télégraphie brève : lisible sans rendre le tir poussif


class Boss(Enemy):
    """Le Colosse : boss du dernier niveau. Énorme, implacable, ne se
    cache jamais — il avance."""
    KIND = "boss"
    SPEED = 1.15
    RADIUS = 0.38
    MAX_HEALTH = 1650      # un vrai colosse : bien plus coriace (x3)
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
    ROLL_DURATION = Player.ROLL_DURATION
    ROLL_COOLDOWN = Player.ROLL_COOLDOWN
    ROLL_IFRAME_START = Player.ROLL_IFRAME_START
    ROLL_IFRAME_END = Player.ROLL_IFRAME_END

    def __init__(self, pid, x, y):
        super().__init__(x, y)
        self.pid = pid
        self.shield = Player.SHIELD_DURATION

    def take_damage(self, amount):
        if self.shield > 0.0 or self.roll_invulnerable:
            return False
        # L'ennemi générique protège toute sa roulade ; le coéquipier suit
        # volontairement la fenêtre plus courte du joueur.
        self.roll_invuln = 0.0
        return super().take_damage(amount)

    @property
    def roll_invulnerable(self):
        if not self.rolling:
            return False
        elapsed = self.ROLL_DURATION - self.roll_timer
        return self.ROLL_IFRAME_START <= elapsed < self.ROLL_IFRAME_END

    def update_timers(self, dt):
        super().update_timers(dt)
        self.shield = max(0.0, self.shield - dt)


ENEMY_TYPES = {"grunt": Grunt, "soldier": Soldier, "heavy": Heavy,
               "kamikaze": Kamikaze, "sniper": Sniper, "boss": Boss}


def _height_for_visible_width(sprite_name, target_width):
    """Hauteur de projection qui donne au contenu opaque la largeur voulue.

    Les PNG générés conservent des toiles historiques parfois beaucoup plus
    larges que leur dessin visible. La projection ne doit donc pas utiliser
    la toile transparente comme mesure physique de l'objet.
    """
    sprite = assets.get(sprite_name)
    bounds = sprite.get_bounding_rect(min_alpha=8)
    if bounds.width <= 0:
        return 0.1
    return target_width * sprite.get_height() / bounds.width


def _height_for_visible_height(sprite_name, target_height):
    """Hauteur de projection qui donne au contenu opaque la hauteur voulue."""
    sprite = assets.get(sprite_name)
    bounds = sprite.get_bounding_rect(min_alpha=8)
    if bounds.height <= 0:
        return target_height
    return target_height * sprite.get_height() / bounds.height


# Décors : largeur physique visée du dessin opaque, en unités monde. Ces
# valeurs reprennent l'emprise des anciens sprites procéduraux et permettent
# aux nouvelles illustrations de garder la bonne échelle sans être déformées.
# Tous bloquent leur case mais laissent passer balles et regards.
PROP_SPECS = {
    "car":      {"sprite": "prop_car",      "width": 1.10},
    "bench":    {"sprite": "prop_bench",    "width": 0.46},
    "tribune":  {"sprite": "prop_tribune",  "width": 0.57},
    "labtable": {"sprite": "prop_labtable", "width": 1.00},
    "rock":     {"sprite": "prop_rock",      "width": 0.47},
    "alien_crystal": {"sprite": "prop_alien_crystal", "width": 0.88},
    "fissure":  {"sprite": "prop_fissure",  "width": 0.60},
    "portal":   {"sprite": "prop_portal",   "width": 0.67},
}

PORTAL_FRAMES = tuple(f"prop_portal_{i}" for i in range(4))
PORTAL_FRAME_MS = 110       # ~9 i/s : vif, sans scintillement agressif

# Largeur visible historique des objets ramassables. Les armes longues
# restent comparables entre elles, sans que le pistolet ou les soins occupent
# soudain toute une case à cause d'un cadrage PNG différent.
PICKUP_WIDTHS = {
    "pistol": 0.19,
    "shotgun": 0.30,
    "rifle": 0.30,
    "minigun": 0.30,
    "medkit": 0.26,
    "lifepack": 0.34,
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
        self.SPRITE_HEIGHT = _height_for_visible_width(
            self.sprite_name, spec["width"],
        )
        self.flipped = (int(x) + int(y)) % 2 == 1
        self.v_offset = 0.0

    def current_sprite(self, player=None):
        if self.kind == "portal":
            # Les quatre PNG sont précalculés et mis en cache par assets.get :
            # l'animation ne fait donc aucune transformation coûteuse en jeu.
            ticks = pygame.time.get_ticks()
            frame = (ticks // PORTAL_FRAME_MS) % len(PORTAL_FRAMES)
            # Anneau sans support : lévitation lente au-dessus du régolithe.
            self.v_offset = 0.11 + 0.018 * math.sin(
                ticks * 0.003,
            )
            return assets.get(PORTAL_FRAMES[frame])
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
        pickup_id = kind.split(":", 1)[-1]
        self.SPRITE_HEIGHT = _height_for_visible_width(
            self.sprite_name, PICKUP_WIDTHS[pickup_id],
        )

    def current_sprite(self, player=None):
        return assets.get(self.sprite_name)

    def bob_offset(self, time_s):
        """Décalage vertical (unités monde) pour l'oscillation."""
        return 0.06 * math.sin(time_s * 2.5 + self.bob)
