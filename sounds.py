"""Audio du jeu, synthétisé en pur Python (aucun fichier externe).

- Effets sonores : bruits/tonalités 16 bits générés avec `math`/`random`/
  `struct`, chargés dans des `pygame.mixer.Sound`.
- Son positionnel : le mixer est en stéréo ; les sons du monde (tirs
  ennemis, impacts) sont atténués avec la distance et panoramiqués
  gauche/droite selon leur direction par rapport au regard du joueur.
- Musique : une nappe d'ambiance sombre est synthétisée par niveau
  (accord bourdon + battements lents), bouclée sur un canal réservé.

Si le mixer n'est pas disponible (pas de carte son), tout est silencieux
mais le jeu fonctionne normalement.
"""

import math
import random
import struct

import pygame

SAMPLE_RATE = 22050
HEARING_RANGE = 18.0     # distance au-delà de laquelle un son du monde est inaudible


def _pack(samples):
    """Liste de flottants [-1, 1] -> buffer stéréo 16 bits (canaux identiques)."""
    out = bytearray()
    for s in samples:
        v = struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32000))
        out += v
        out += v
    return bytes(out)


# ----------------------------------------------------------------------
# Synthèse des effets
# ----------------------------------------------------------------------
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


def _shotgun(duration=0.28):
    """Détonation lourde et longue du fusil à pompe."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        env = (1 - i / n) ** 2
        noise = random.uniform(-1, 1)
        low = 0.6 * math.sin(2 * math.pi * 60 * i / SAMPLE_RATE)
        samples.append((noise * 0.8 + low) * env)
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


def _jingle(freqs, note=0.11):
    """Suite de notes (ramassage d'objet, niveau terminé)."""
    return b"".join(_tone(f, note, slide=f * 0.05) for f in freqs)


def _ambient_loop(base_freq, seed, duration=12.0):
    """Nappe d'ambiance bouclable : bourdon + quinte + octave détunée.

    Les fréquences sont arrondies à un nombre entier de cycles sur la
    durée pour que la boucle soit parfaitement raccord (pas de clic).
    """
    rng = random.Random(seed)

    def loopable(f):
        return round(f * duration) / duration

    f1 = loopable(base_freq)
    f2 = loopable(base_freq * 1.5)          # quinte
    f3 = loopable(base_freq * 2.02)         # octave légèrement détunée (battement)
    f4 = loopable(base_freq * rng.uniform(2.9, 3.1))
    n = int(SAMPLE_RATE * duration)
    two_pi = 2 * math.pi
    p1 = p2 = p3 = p4 = 0.0
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        # LFO qui boucle sur la durée totale : respiration lente de la nappe.
        lfo = 0.5 + 0.5 * math.sin(two_pi * t / duration)
        lfo2 = 0.5 + 0.5 * math.sin(two_pi * 2 * t / duration + 1.7)
        p1 += two_pi * f1 / SAMPLE_RATE
        p2 += two_pi * f2 / SAMPLE_RATE
        p3 += two_pi * f3 / SAMPLE_RATE
        p4 += two_pi * f4 / SAMPLE_RATE
        s = (0.45 * math.sin(p1)
             + 0.22 * math.sin(p2) * lfo
             + 0.18 * math.sin(p3)
             + 0.08 * math.sin(p4) * lfo2)
        samples.append(s * 0.55)
    return _pack(samples)


# Tonique de la nappe par contexte : de plus en plus grave et sombre.
MUSIC_KEYS = {
    "menu": (49.0, 1),      # G1
    "level0": (55.0, 2),    # A1
    "level1": (46.25, 3),   # F#1
    "level2": (41.2, 4),    # E1
    "level3": (36.7, 5),    # D1
}
MUSIC_VOLUME = 0.35         # part du volume global réservée à la musique


class SoundBank:
    """Charge tous les sons ; applique volume, distance et panoramique au
    moment de jouer (le curseur du menu agit donc immédiatement)."""

    def __init__(self, settings):
        self.settings = settings
        self.sounds = {}
        self.music_cache = {}
        self.music_key = None
        self.music_channel = None
        self.enabled = pygame.mixer.get_init() is not None
        if not self.enabled:
            return
        pygame.mixer.set_reserved(1)                 # canal 0 : musique
        self.music_channel = pygame.mixer.Channel(0)
        self.sounds = {
            "player_shot": pygame.mixer.Sound(buffer=_gunshot()),
            "pistol_shot": pygame.mixer.Sound(buffer=_gunshot(0.08)),
            "shotgun_shot": pygame.mixer.Sound(buffer=_shotgun()),
            "enemy_shot": pygame.mixer.Sound(buffer=_enemy_shot()),
            "player_hit": pygame.mixer.Sound(buffer=_tone(140, 0.18, slide=-60)),
            "enemy_hit": pygame.mixer.Sound(buffer=_tone(520, 0.08, slide=-120)),
            "enemy_die": pygame.mixer.Sound(buffer=_tone(300, 0.35, slide=-220)),
            "reload": pygame.mixer.Sound(buffer=_tone(700, 0.09, slide=200)),
            "click": pygame.mixer.Sound(buffer=_tone(900, 0.05)),
            "pickup": pygame.mixer.Sound(buffer=_jingle([520, 660, 880])),
            "heal": pygame.mixer.Sound(buffer=_jingle([440, 550])),
            "level_complete": pygame.mixer.Sound(
                buffer=_jingle([523, 659, 784, 1046], note=0.16)),
        }

    # ------------------------------------------------------------------
    # Effets
    # ------------------------------------------------------------------
    def play(self, name, volume_scale=1.0, pos=None, listener=None):
        """Joue un effet. Avec `pos` (x, y) et `listener` (le joueur), le
        volume décroît avec la distance et le son est panoramiqué selon la
        direction par rapport au regard."""
        if not self.enabled or name not in self.sounds:
            return
        volume = self.settings.volume * volume_scale
        left = right = volume
        if pos is not None and listener is not None:
            dx, dy = pos[0] - listener.x, pos[1] - listener.y
            dist = math.hypot(dx, dy)
            attenuation = max(0.0, 1.0 - dist / HEARING_RANGE)
            if attenuation <= 0.01:
                return
            # pan dans [-1 (gauche), 1 (droite)] selon l'angle relatif au regard
            rel = math.atan2(dy, dx) - listener.angle
            pan = math.sin(rel)
            left = volume * attenuation * min(1.0, 1.0 - pan * 0.8)
            right = volume * attenuation * min(1.0, 1.0 + pan * 0.8)
        channel = self.sounds[name].play()
        if channel is not None:
            channel.set_volume(max(0.0, left), max(0.0, right))

    # ------------------------------------------------------------------
    # Musique d'ambiance
    # ------------------------------------------------------------------
    def play_music(self, key):
        """Lance (ou continue) la nappe d'ambiance `key` ("menu", "level0"...).

        La nappe est synthétisée à la première demande puis mise en cache.
        """
        if not self.enabled or key not in MUSIC_KEYS or key == self.music_key:
            return
        if key not in self.music_cache:
            freq, seed = MUSIC_KEYS[key]
            self.music_cache[key] = pygame.mixer.Sound(
                buffer=_ambient_loop(freq, seed))
        self.music_channel.play(self.music_cache[key], loops=-1, fade_ms=600)
        self.music_key = key
        self.refresh_music_volume()

    def refresh_music_volume(self):
        """Applique le volume courant à la musique (appelé quand il change)."""
        if self.enabled and self.music_channel is not None:
            v = self.settings.volume * MUSIC_VOLUME
            self.music_channel.set_volume(v, v)

    def stop_music(self):
        if self.enabled and self.music_channel is not None:
            self.music_channel.fadeout(400)
            self.music_key = None
