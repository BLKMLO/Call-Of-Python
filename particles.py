"""Système de particules en espace monde.

Chaque particule est un petit carré coloré positionné en 3D (x, y sur la
grille + z = hauteur, 0 = sol, 1 = plafond). Le raycaster les projette à
l'écran comme les sprites, en respectant le z-buffer des murs.

Effets fournis : sang (impact sur un ennemi), gerbe de mort, poussière
d'impact sur un mur (teintée de la couleur de la texture touchée).
"""

import math
import random


class Particle:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "life", "color", "size")

    def __init__(self, x, y, z, vx, vy, vz, life, color, size):
        self.x, self.y, self.z = x, y, z
        self.vx, self.vy, self.vz = vx, vy, vz
        self.life = life
        self.color = color
        self.size = size  # taille en unités monde (fraction de mur)


class ParticleSystem:
    MAX_PARTICLES = 500
    GRAVITY = 2.6

    def __init__(self):
        self.items = []

    # ------------------------------------------------------------------
    # Émetteurs
    # ------------------------------------------------------------------
    def _burst(self, x, y, z, n, colors, speed, size, life, upward=0.6):
        for _ in range(n):
            ang = random.uniform(0, 2 * math.pi)
            v = random.uniform(0.2, 1.0) * speed
            self.items.append(Particle(
                x, y, z,
                math.cos(ang) * v, math.sin(ang) * v,
                random.uniform(-0.2, upward) * speed,
                life * random.uniform(0.6, 1.2),
                random.choice(colors),
                size * random.uniform(0.7, 1.4),
            ))
        # borne dure : les plus anciennes disparaissent d'abord
        if len(self.items) > self.MAX_PARTICLES:
            del self.items[: len(self.items) - self.MAX_PARTICLES]

    def spawn_blood(self, x, y):
        """Giclée de sang quand un ennemi est touché."""
        self._burst(x, y, 0.55, 10,
                    [(148, 22, 26), (110, 14, 18), (176, 34, 34)],
                    speed=1.6, size=0.035, life=0.5)

    def spawn_death(self, x, y):
        """Grosse gerbe quand un ennemi meurt."""
        self._burst(x, y, 0.5, 26,
                    [(148, 22, 26), (96, 12, 16), (60, 60, 66)],
                    speed=2.4, size=0.045, life=0.9)

    def spawn_wall_dust(self, x, y, color):
        """Éclats de poussière à l'impact d'une balle sur un mur."""
        dark = tuple(max(0, c - 40) for c in color)
        self._burst(x, y, 0.5, 7, [color, dark],
                    speed=1.1, size=0.03, life=0.4, upward=0.9)

    def spawn_portal(self, x, y):
        """Déchirure incandescente : un ennemi de la horde surgit."""
        self._burst(x, y, 0.4, 18,
                    [(255, 150, 40), (200, 60, 30), (120, 30, 60)],
                    speed=1.4, size=0.04, life=0.8, upward=1.6)

    # ------------------------------------------------------------------
    def update(self, dt):
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.z += p.vz * dt
            p.vz -= self.GRAVITY * dt
            if p.z <= 0.02:            # au sol : la particule s'y dépose
                p.z = 0.02
                p.vx *= 0.4
                p.vy *= 0.4
                p.vz = 0.0
            alive.append(p)
        self.items = alive
