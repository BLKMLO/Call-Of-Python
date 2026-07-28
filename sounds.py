"""Audio du jeu : essentiellement synthétisé en pur Python, avec quelques
fichiers réels chargeables depuis `assets/sound/`.

- Effets sonores : bruits/tonalités 16 bits générés avec `math`/`random`/
  `struct`, chargés dans des `pygame.mixer.Sound`. Le rechargement utilise
  un vrai fichier (`assets/sound/reload.*`) s'il est présent, sinon un
  clic synthétisé de repli.
- Son positionnel : le mixer est en stéréo ; les sons du monde (tirs
  ennemis, impacts) sont atténués avec la distance et panoramiqués
  gauche/droite selon leur direction par rapport au regard du joueur.
- Musique : chaque niveau possède une composition procédurale propre
  (motif, tempo et timbre), bouclée sur un canal réservé — sauf si un
  fichier personnalisé existe dans `assets/sound/` (voir
  `_custom_music_path`), auquel cas il est joué à la place.

Si le mixer n'est pas disponible (pas de carte son), tout est silencieux
mais le jeu fonctionne normalement.
"""

import math
import os
import random
import struct
from dataclasses import dataclass

import pygame

SAMPLE_RATE = 22050
HEARING_RANGE = 18.0     # distance au-delà de laquelle un son du monde est inaudible

# Dossier des fichiers audio réels (effets et musiques personnalisées),
# optionnel : tout est synthétisé par défaut si rien n'y est trouvé.
SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "assets", "sound")
AUDIO_EXTENSIONS = ("ogg", "mp3", "wav", "flac")


def _find_audio_file(stem):
    """Cherche `assets/sound/<stem>.<ext>` (première extension trouvée)."""
    for ext in AUDIO_EXTENSIONS:
        path = os.path.join(SOUND_DIR, f"{stem}.{ext}")
        if os.path.isfile(path):
            return path
    return None


def _custom_music_path(key):
    """Fichier de musique personnalisé pour la nappe `key`, si présent.

    Pour un niveau de campagne ("level0".."level4"), le nom de fichier
    attendu est le numéro affiché au joueur (1..5, `assets/sound/1.*` pour
    le niveau 1, etc.) — plus intuitif à déposer que l'index interne.
    Pour les autres nappes ("menu", "survival"), le nom de fichier est la
    clé elle-même. Absent : la nappe synthétisée sert de musique par défaut.
    """
    if key.startswith("level") and key[len("level"):].isdigit():
        stem = str(int(key[len("level"):]) + 1)
    else:
        stem = key
    return _find_audio_file(stem)


def stereo_gains(volume, pos, listener):
    """Gains (gauche, droite) d'un son du monde en `pos` pour `listener`.

    Atténuation avec la distance, panoramique selon la direction relative
    au regard : une source à droite du joueur sonne plus fort à droite.
    Retourne None si la source est trop loin pour être audible."""
    dx, dy = pos[0] - listener.x, pos[1] - listener.y
    dist = math.hypot(dx, dy)
    attenuation = max(0.0, 1.0 - dist / HEARING_RANGE)
    if attenuation <= 0.01:
        return None
    # pan dans [-1 (gauche), 1 (droite)] selon l'angle relatif au regard
    rel = math.atan2(dy, dx) - listener.angle
    pan = math.sin(rel)
    left = volume * attenuation * min(1.0, 1.0 - pan * 0.8)
    right = volume * attenuation * min(1.0, 1.0 + pan * 0.8)
    return left, right


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


def _flesh_hit(duration=0.16):
    """Impact organique sourd d'une balle dans une cible non blindée."""
    rng = random.Random(0xF1E5)
    n = int(SAMPLE_RATE * duration)
    samples = []
    low = 0.0
    phase = 0.0
    for i in range(n):
        t = i / n
        low += (rng.uniform(-1.0, 1.0) - low) * 0.09
        phase += 2 * math.pi * (105 - 45 * t) / SAMPLE_RATE
        thump = math.sin(phase) * (1 - t) ** 5
        samples.append(_clip((low * 1.2 + thump * 0.85) * (1 - t) ** 2))
    return _pack(samples)


def _armor_hit(duration=0.22):
    """Éclat métallique bref, suivi d'une résonance de plaque blindée."""
    rng = random.Random(0xA8A0)
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / n
        seconds = i / SAMPLE_RATE
        strike = rng.uniform(-1.0, 1.0) * (1 - t) ** 18
        ring = (
            math.sin(2 * math.pi * 1180 * seconds)
            + 0.55 * math.sin(2 * math.pi * 1730 * seconds)
            + 0.25 * math.sin(2 * math.pi * 2470 * seconds)
        ) * (1 - t) ** 5
        samples.append(_clip(strike * 0.8 + ring * 0.48))
    return _pack(_with_tail(samples, delay=0.045, gain=0.2))


def _possessed_hit(duration=0.30):
    """Souffle humide et sifflant, comme une flamme alien qu'on étouffe."""
    rng = random.Random(0xA11E)
    n = int(SAMPLE_RATE * duration)
    samples = []
    hiss = 0.0
    phase = 0.0
    for i in range(n):
        t = i / n
        noise = rng.uniform(-1.0, 1.0)
        hiss += (noise - hiss) * (0.48 - 0.30 * t)
        phase += 2 * math.pi * (310 - 210 * t) / SAMPLE_RATE
        extinguish = math.sin(phase) * math.sin(math.pi * t)
        envelope = (1 - t) ** 1.8
        samples.append(_clip((hiss * 0.75 + extinguish * 0.25) * envelope))
    return _pack(samples)


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


@dataclass(frozen=True)
class MusicProfile:
    """Identité musicale déterministe d'un écran ou d'un niveau."""

    root: float
    tempo: int
    pattern: tuple
    style: str
    seed: int
    title: str


# Chaque contexte possède désormais un rythme, un motif et un timbre propres.
# Le nombre de temps produit en 12 secondes reste un multiple du motif, ce qui
# garantit une boucle sans rupture.
MUSIC_PROFILES = {
    "menu": MusicProfile(
        49.0, 60, (0, 7, 3, 10), "cinematic", 1, "Aux portes du Sceau",
    ),
    "level0": MusicProfile(
        55.0, 80, (0, 0, 3, 0, 7, 0, 3, -2),
        "industrial", 2, "Acier dormant",
    ),
    "level1": MusicProfile(
        58.27, 120, (0, 3, 7, 10, 7, 3, 12, 10),
        "urban", 7, "Métropole assiégée",
    ),
    "level2": MusicProfile(
        43.65, 60, (0, 7, 3, 10), "solemn", 8, "Pouvoir vacant",
    ),
    "level3": MusicProfile(
        41.2, 100, (0, 0, 7, 3), "military", 4, "Dernière ligne",
    ),
    "level4": MusicProfile(
        34.65, 80, (0, 1, 6, 1, 0, 8, 6, 1),
        "laboratory", 9, "Le Sceau respire",
    ),
    "survival": MusicProfile(
        32.7, 60, (0, 6, 1, 11), "alien", 6, "Déferlement lunaire",
    ),
}
# Alias historique : plusieurs appels et tests itèrent déjà sur MUSIC_KEYS.
MUSIC_KEYS = MUSIC_PROFILES
MUSIC_VOLUME = 0.35         # gain de mixage appliqué au curseur musique


def _music_loop(key, duration=12.0):
    """Compose une boucle musicale propre au contexte demandé.

    Toutes les couches sont périodiques : les drones font un nombre entier de
    cycles sur la boucle et les notes rythmiques démarrent/finissent à volume
    nul. Aucun fichier temporaire ni dépendance audio externe n'est requis.
    """
    profile = MUSIC_PROFILES[key]
    if not math.isfinite(duration) or duration <= 0.0:
        raise ValueError("La durée musicale doit être finie et positive")

    pattern_len = len(profile.pattern)
    nominal_beats = max(pattern_len, round(duration * profile.tempo / 60))
    beats = max(
        pattern_len,
        round(nominal_beats / pattern_len) * pattern_len,
    )
    beat_duration = duration / beats
    rng = random.Random(profile.seed)
    two_pi = 2 * math.pi

    def loopable(freq):
        return max(1.0, round(freq * duration) / duration)

    def beat_loopable(freq):
        return max(1.0, round(freq * beat_duration) / beat_duration)

    root = loopable(profile.root)
    fifth = loopable(profile.root * 1.5)
    octave = loopable(profile.root * 2.0)
    color_ratio = {
        "cinematic": 1.25,
        "industrial": 1.414,
        "urban": 1.875,
        "solemn": 1.2,
        "military": 1.5,
        "laboratory": 1.05946,
        "alien": 1.414,
    }[profile.style]
    color = loopable(profile.root * color_ratio)
    shimmer = loopable(profile.root * rng.uniform(5.7, 7.3))

    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        beat_pos = t / beat_duration
        beat_index = int(beat_pos)
        beat_phase = beat_pos - beat_index
        local = beat_phase * beat_duration
        interval = profile.pattern[beat_index % pattern_len]
        note_freq = beat_loopable(
            profile.root * 2 ** (interval / 12.0),
        )

        breathe = 0.72 + 0.28 * math.sin(two_pi * t / duration)
        slow_lfo = math.sin(two_pi * 2 * t / duration + 0.4)
        drone = (
            0.34 * math.sin(two_pi * root * t)
            + 0.16 * math.sin(two_pi * fifth * t) * breathe
            + 0.10 * math.sin(two_pi * octave * t + 0.25 * slow_lfo)
        )
        note_env = math.sin(math.pi * beat_phase) ** 2
        note = math.sin(two_pi * note_freq * local) * note_env
        impact = (1.0 - beat_phase) ** 6

        if profile.style == "industrial":
            metal = (
                math.sin(two_pi * 420 * local)
                + 0.55 * math.sin(two_pi * 713 * local)
            ) * impact
            sample = drone * 0.74 + note * 0.25 + metal * 0.12
        elif profile.style == "urban":
            sub = math.sin(two_pi * root * local) * impact
            sample = drone * 0.55 + note * 0.36 + sub * 0.18
        elif profile.style == "solemn":
            bell = math.sin(two_pi * shimmer * local) * impact
            sample = drone * 0.88 + note * 0.18 + bell * 0.075
        elif profile.style == "military":
            kick = math.sin(
                two_pi * (62.0 - 24.0 * beat_phase) * local,
            ) * impact
            snare = 0.0
            if beat_index % 2:
                snare = (
                    math.sin(two_pi * 937 * local)
                    + 0.5 * math.sin(two_pi * 1543 * local)
                ) * impact
            sample = drone * 0.61 + note * 0.22 + kick * 0.24 + snare * 0.08
        elif profile.style == "laboratory":
            glass = (
                math.sin(two_pi * shimmer * local)
                + 0.45 * math.sin(two_pi * shimmer * 1.5 * local)
            ) * impact
            sample = (
                drone * 0.63
                + math.sin(two_pi * color * t) * 0.16
                + note * 0.18
                + glass * 0.08
            )
        elif profile.style == "alien":
            warped = math.sin(
                two_pi * color * t + 0.9 * math.sin(
                    two_pi * 3 * t / duration,
                ),
            )
            sample = drone * 0.7 + warped * 0.19 + note * 0.13
        else:  # cinematic — menu
            pulse = math.sin(two_pi * root * local) * impact
            sample = drone * 0.82 + note * 0.17 + pulse * 0.13

        samples.append(math.tanh(sample * 1.2) * 0.58)
    return _pack(samples)


class SoundBank:
    """Charge tous les sons ; applique volume, distance et panoramique au
    moment de jouer (le curseur des effets agit donc immédiatement)."""

    def __init__(self, settings):
        self.settings = settings
        self.sounds = {}
        self.music_cache = {}
        self.music_key = None
        self.music_channel = None
        self._last_music_volume = None
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
            "flesh_hit": pygame.mixer.Sound(buffer=_flesh_hit()),
            "armor_hit": pygame.mixer.Sound(buffer=_armor_hit()),
            "possessed_hit": pygame.mixer.Sound(buffer=_possessed_hit()),
            # Alias conservé pour d'éventuels appels externes anciens.
            "enemy_hit": pygame.mixer.Sound(buffer=_flesh_hit()),
            "enemy_die": pygame.mixer.Sound(buffer=_tone(300, 0.35, slide=-220)),
            "reload": self._load_reload_sound(),
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

    @staticmethod
    def _load_reload_sound():
        """`assets/sound/reload.*` si présent, sinon le clic synthétisé."""
        path = _find_audio_file("reload")
        if path is not None:
            try:
                return pygame.mixer.Sound(path)
            except pygame.error:
                pass  # fichier illisible : repli sur le son synthétisé
        return pygame.mixer.Sound(buffer=_reload_clack())

    # ------------------------------------------------------------------
    # Effets
    # ------------------------------------------------------------------
    def play(self, name, volume_scale=1.0, pos=None, listener=None):
        """Joue un effet. Avec `pos` (x, y) et `listener` (le joueur), le
        volume décroît avec la distance et le son est panoramiqué selon la
        direction par rapport au regard."""
        if not self.enabled or name not in self.sounds:
            return
        volume = self.settings.sound_volume * volume_scale
        left = right = volume
        if pos is not None and listener is not None:
            gains = stereo_gains(volume, pos, listener)
            if gains is None:
                return
            left, right = gains
        channel = self.sounds[name].play()
        if channel is not None:
            channel.set_volume(max(0.0, left), max(0.0, right))

    # ------------------------------------------------------------------
    # Musique d'ambiance
    # ------------------------------------------------------------------
    def play_music(self, key):
        """Lance (ou continue) la nappe d'ambiance `key` ("menu", "level0"...).

        Un fichier personnalisé dans `assets/sound/` (voir
        `_custom_music_path`) est utilisé s'il existe ; sinon la nappe est
        synthétisée à la première demande puis mise en cache.
        """
        if not self.enabled or key not in MUSIC_KEYS or key == self.music_key:
            return
        if key not in self.music_cache:
            custom = _custom_music_path(key)
            sound = None
            if custom is not None:
                try:
                    sound = pygame.mixer.Sound(custom)
                except pygame.error:
                    sound = None  # fichier illisible : repli sur la synthèse
            if sound is None:
                sound = pygame.mixer.Sound(buffer=_music_loop(key))
            self.music_cache[key] = sound
        self.music_channel.play(self.music_cache[key], loops=-1, fade_ms=600)
        self.music_key = key
        self.refresh_music_volume()

    def refresh_music_volume(self):
        """Applique le volume courant à la musique (appelé quand il change)."""
        if self.enabled and self.music_channel is not None:
            v = self.settings.music_volume * MUSIC_VOLUME
            if v != self._last_music_volume:
                self.music_channel.set_volume(v, v)
                self._last_music_volume = v

    def stop_music(self):
        if self.enabled and self.music_channel is not None:
            self.music_channel.fadeout(400)
            self.music_key = None
