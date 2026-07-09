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
#
# Les détonations sont construites en couches : un souffle de bruit blanc
# (l'explosion), un « thump » grave à fréquence descendante (le punch) et
# un claquement haute fréquence très bref (la percussion mécanique). Le
# tout passe dans un écrasement doux (tanh) qui donne du corps, puis
# reçoit une courte queue d'écho.
# ----------------------------------------------------------------------
def _clip(sample):
    """Écrasement doux : comprime les crêtes sans distorsion dure."""
    return math.tanh(sample * 1.4)


def _with_tail(samples, delay=0.055, gain=0.3):
    """Ajoute un léger écho : rend les tirs moins « secs »."""
    offset = int(SAMPLE_RATE * delay)
    out = list(samples) + [0.0] * offset
    for i, s in enumerate(samples):
        out[i + offset] += s * gain
    return out


def _layered_shot(duration, low_freq, crack_freq, noise_gain=0.9,
                  punch=1.0, tail=0.3):
    """Détonation générique à trois couches (voir commentaire de section)."""
    n = int(SAMPLE_RATE * duration)
    phase = 0.0
    samples = []
    for i in range(n):
        t = i / n
        seconds = i / SAMPLE_RATE
        noise = random.uniform(-1, 1) * (1 - t) ** 4 * noise_gain
        phase += 2 * math.pi * low_freq * (1.0 - 0.45 * t) / SAMPLE_RATE
        thump = math.sin(phase) * (1 - t) ** 2 * punch
        crack = math.sin(2 * math.pi * crack_freq * seconds) * (1 - t) ** 12
        samples.append(_clip(noise + thump * 0.9 + crack * 0.7))
    return _pack(_with_tail(samples, gain=tail))


def _gunshot(duration=0.16):
    """Fusil d'assaut / minigun : claquement sec avec du coffre."""
    return _layered_shot(duration, low_freq=68, crack_freq=1300)


def _pistol():
    """Pistolet : plus haut, plus court, moins de souffle."""
    return _layered_shot(0.11, low_freq=95, crack_freq=1900,
                         noise_gain=0.7, punch=0.8, tail=0.22)


def _shotgun(duration=0.32):
    """Fusil à pompe : détonation lourde, grave et longue."""
    return _layered_shot(duration, low_freq=48, crack_freq=900,
                         noise_gain=1.1, punch=1.35, tail=0.4)


def _enemy_shot(duration=0.16):
    """Détonation ennemie, plus sourde (entendue de l'extérieur)."""
    return _layered_shot(duration, low_freq=80, crack_freq=500,
                         noise_gain=0.55, punch=0.9, tail=0.35)


def _footstep(seed):
    """Pas feutré : bruit passé dans un passe-bas (thud sourd et court)."""
    rng = random.Random(seed)
    n = int(SAMPLE_RATE * 0.085)
    samples = []
    level = 0.0
    for i in range(n):
        t = i / n
        level += (rng.uniform(-1, 1) - level) * 0.18   # filtre passe-bas
        env = math.sin(math.pi * min(1.0, t * 3)) * (1 - t) ** 2
        samples.append(level * env * 1.6)
    return _pack(samples)


def _reload_clack():
    """Rechargement en deux temps : chargeur éjecté... puis claqué."""
    def click(freq, dur, vol):
        n = int(SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / n
            out.append((math.sin(2 * math.pi * freq * i / SAMPLE_RATE) * 0.5
                        + random.uniform(-0.5, 0.5)) * (1 - t) ** 6 * vol)
        return out
    silence = [0.0] * int(SAMPLE_RATE * 0.13)
    return _pack(click(620, 0.05, 0.7) + silence + click(380, 0.07, 1.0))


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


def _explosion(duration=0.6):
    """Déflagration d'un kamikaze : souffle grave + gravats + écho."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    phase = 0.0
    for i in range(n):
        t = i / n
        env = (1 - t) ** 1.6
        phase += 2 * math.pi * (55 - 25 * t) / SAMPLE_RATE
        samples.append(_clip((math.sin(phase) * 0.9
                              + random.uniform(-0.9, 0.9) * (1 - t) ** 3) * env))
    return _pack(_with_tail(samples, delay=0.09, gain=0.4))


def _door_slide(duration=0.35):
    """Chuintement pneumatique d'une porte coulissante."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / n
        env = math.sin(math.pi * t) * 0.5          # monte puis redescend
        samples.append(random.uniform(-1, 1) * env * (0.4 + 0.3 * t))
    return _pack(samples)


def _spawn_whoosh(duration=0.45):
    """Déchirure grave : un ennemi de la horde surgit."""
    n = int(SAMPLE_RATE * duration)
    samples = []
    phase = 0.0
    for i in range(n):
        t = i / n
        f = 320 - 240 * t                          # sifflement descendant
        phase += 2 * math.pi * f / SAMPLE_RATE
        env = math.sin(math.pi * t)
        samples.append((math.sin(phase) * 0.5
                        + random.uniform(-0.35, 0.35)) * env)
    return _pack(samples)


def _horn():
    """Cor de guerre grave : une nouvelle vague déferle."""
    parts = []
    for f, dur in ((110.0, 0.35), (82.4, 0.5)):
        n = int(SAMPLE_RATE * dur)
        phase = 0.0
        samples = []
        for i in range(n):
            t = i / n
            phase += 2 * math.pi * f / SAMPLE_RATE
            env = min(1.0, t * 8) * (1 - t) ** 0.7
            # onde riche (fondamentale + harmoniques) façon cuivre
            s = (math.sin(phase) + 0.5 * math.sin(2 * phase)
                 + 0.25 * math.sin(3 * phase))
            samples.append(s * env * 0.5)
        parts.append(_pack(samples))
    return b"".join(parts)


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


# Tonique de la nappe par contexte : de plus en plus grave et sombre au
# fil de la campagne, jusqu'à l'abîme lunaire du Déferlement.
MUSIC_KEYS = {
    "menu": (49.0, 1),       # G1
    "level0": (55.0, 2),     # A1  — Entrepôt
    "level1": (58.27, 7),    # A#1 — Métropole (rumeur urbaine)
    "level2": (43.65, 8),    # F1  — Gouvernement (solennel)
    "level3": (41.2, 4),     # E1  — Base militaire
    "level4": (34.65, 9),    # C#1 — Laboratoire, l'assaut final
    "survival": (32.7, 6),   # C1  — la Lune, le Déferlement
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
        # Assez de canaux pour une horde qui tire de partout, plus le
        # canal 0 réservé à la musique.
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(1)
        self.music_channel = pygame.mixer.Channel(0)
        self.sounds = {
            "player_shot": pygame.mixer.Sound(buffer=_gunshot()),
            "pistol_shot": pygame.mixer.Sound(buffer=_pistol()),
            "shotgun_shot": pygame.mixer.Sound(buffer=_shotgun()),
            "enemy_shot": pygame.mixer.Sound(buffer=_enemy_shot()),
            "player_hit": pygame.mixer.Sound(buffer=_tone(140, 0.18, slide=-60)),
            "enemy_hit": pygame.mixer.Sound(buffer=_tone(520, 0.08, slide=-120)),
            "enemy_die": pygame.mixer.Sound(buffer=_tone(300, 0.35, slide=-220)),
            "reload": pygame.mixer.Sound(buffer=_reload_clack()),
            "click": pygame.mixer.Sound(buffer=_tone(900, 0.05)),
            "step": pygame.mixer.Sound(buffer=_footstep(1)),
            "step2": pygame.mixer.Sound(buffer=_footstep(2)),
            "pickup": pygame.mixer.Sound(buffer=_jingle([520, 660, 880])),
            "heal": pygame.mixer.Sound(buffer=_jingle([440, 550])),
            "level_complete": pygame.mixer.Sound(
                buffer=_jingle([523, 659, 784, 1046], note=0.16)),
            "door": pygame.mixer.Sound(buffer=_door_slide()),
            "spawn": pygame.mixer.Sound(buffer=_spawn_whoosh()),
            "wave": pygame.mixer.Sound(buffer=_horn()),
            "explosion": pygame.mixer.Sound(buffer=_explosion()),
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
