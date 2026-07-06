"""Sons du jeu, synthétisés en pur Python (aucun fichier audio externe).

Les échantillons 16 bits mono sont générés avec `math`/`random`/`struct`
puis chargés dans des `pygame.mixer.Sound`. Si le mixer n'est pas
disponible (pas de carte son), le jeu fonctionne simplement en silence.
"""

import math
import random
import struct

import pygame

SAMPLE_RATE = 22050


def _pack(samples):
    """Convertit une liste de flottants [-1, 1] en buffer 16 bits signés."""
    return b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000)) for s in samples
    )


def _gunshot(duration=0.12):
    """Bruit blanc à décroissance rapide : détonation du fusil."""
    n = int(SAMPLE_RATE * duration)
    return _pack(
        random.uniform(-1, 1) * (1 - i / n) ** 3 for i in range(n)
    )


def _enemy_shot(duration=0.14):
    """Détonation plus sourde (mélange bruit + basse fréquence)."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        env = (1 - i / n) ** 2.5
        noise = random.uniform(-0.6, 0.6)
        low = 0.5 * math.sin(2 * math.pi * 90 * i / SAMPLE_RATE)
        samples.append((noise + low) * env)
    return _pack(samples)


def _tone(freq, duration, slide=0.0):
    """Bip sinusoïdal, avec un éventuel glissement de fréquence."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    phase = 0.0
    for i in range(n):
        f = freq + slide * (i / n)
        phase += 2 * math.pi * f / SAMPLE_RATE
        env = (1 - i / n) ** 1.5
        samples.append(math.sin(phase) * env * 0.7)
    return _pack(samples)


class SoundBank:
    """Charge tous les sons et applique le volume des paramètres au moment
    de jouer (le curseur du menu agit donc immédiatement)."""

    def __init__(self, settings):
        self.settings = settings
        self.sounds = {}
        self.enabled = pygame.mixer.get_init() is not None
        if not self.enabled:
            return
        self.sounds = {
            "player_shot": pygame.mixer.Sound(buffer=_gunshot()),
            "enemy_shot": pygame.mixer.Sound(buffer=_enemy_shot()),
            "player_hit": pygame.mixer.Sound(buffer=_tone(140, 0.18, slide=-60)),
            "enemy_hit": pygame.mixer.Sound(buffer=_tone(520, 0.08, slide=-120)),
            "enemy_die": pygame.mixer.Sound(buffer=_tone(300, 0.35, slide=-220)),
            "reload": pygame.mixer.Sound(buffer=_tone(700, 0.09, slide=200)),
            "click": pygame.mixer.Sound(buffer=_tone(900, 0.05)),
        }

    def play(self, name, volume_scale=1.0):
        if not self.enabled or name not in self.sounds:
            return
        sound = self.sounds[name]
        sound.set_volume(self.settings.volume * volume_scale)
        sound.play()
