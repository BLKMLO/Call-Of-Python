"""Gestion des paramètres du jeu.

Centralise la résolution, le volume, la sensibilité de la souris et les
touches de contrôle. Les paramètres sont sauvegardés dans un fichier JSON
(`settings.json`) à côté du jeu afin d'être conservés entre deux sessions.
"""

import json
import math
import os
from ipaddress import AddressValueError, IPv4Address

import pygame

# Résolutions proposées dans le menu des paramètres.
RESOLUTIONS = [
    (800, 600),
    (960, 540),
    (1024, 768),
    (1280, 720),
    (1600, 900),
]

# Touches par défaut (ZQSD, clavier français). Chaque action est associée à
# un keycode pygame ; toutes les touches sont re-mappables dans le menu
# des paramètres (on peut donc facilement passer en WASD).
DEFAULT_KEYS = {
    "avancer": pygame.K_z,
    "reculer": pygame.K_s,
    "gauche": pygame.K_q,
    "droite": pygame.K_d,
    "roulade": pygame.K_LSHIFT,
    "recharger": pygame.K_r,
}

# L'ordre d'affichage des actions dans le menu des paramètres.
KEY_ACTIONS = ["avancer", "reculer", "gauche", "droite", "roulade", "recharger"]

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
MAX_SETTINGS_BYTES = 64 * 1024
RESERVED_KEYS = {pygame.K_ESCAPE, pygame.K_F11}


def valid_ipv4(value):
    """Retourne une IPv4 canonique, ou ``None`` si la saisie est invalide."""
    try:
        return str(IPv4Address(str(value).strip()))
    except AddressValueError:
        return None


def _safe_float(value, default, low, high):
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return min(high, max(low, number))


def _safe_int(value, default, low, high):
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(high, max(low, number))


def _safe_bool(value, default):
    """Évite le piège bool("false") == True dans un JSON édité à la main."""
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    return default


def _valid_keycode(value):
    try:
        code = int(value)
        name = pygame.key.name(code)
    except (TypeError, ValueError, OverflowError, pygame.error):
        return None
    if not name or code == pygame.K_UNKNOWN or code in RESERVED_KEYS:
        return None
    return code


class Settings:
    """Conteneur des paramètres, avec chargement/sauvegarde JSON."""

    def __init__(self):
        self.resolution_index = 3        # 1280x720 par défaut
        self.volume = 0.7                # volume global (0.0 → 1.0)
        self.sensitivity = 0.5           # sensibilité souris (0.1 → 1.0)
        self.invert_mouse = False        # inverse les deux axes de la souris
        self.fullscreen = False          # F11 : plein écran / mode fenêtré
        self.keys = dict(DEFAULT_KEYS)   # keycodes pygame par action
        self.best_level = 0              # meilleur niveau atteint (affiché au menu)
        self.survival_unlocked = False   # le Déferlement (après la mort du Sceau)
        self.best_wave = 0               # record de vagues en survie
        self.last_ip = "127.0.0.1"       # dernière adresse rejointe (LAN)
        self.load()

    # ------------------------------------------------------------------
    # Accès pratiques
    # ------------------------------------------------------------------
    @property
    def resolution(self):
        return RESOLUTIONS[self.resolution_index]

    def key_name(self, action):
        """Nom lisible de la touche associée à une action (ex: 'Z')."""
        return pygame.key.name(self.keys[action]).upper()

    def mouse_factor(self):
        """Facteur appliqué au mouvement relatif de la souris (radians/pixel)."""
        return 0.0022 * (0.2 + self.sensitivity * 1.8)

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------
    def load(self):
        """Charge les paramètres depuis le JSON (silencieux si absent/corrompu)."""
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                raw = f.read(MAX_SETTINGS_BYTES + 1)
            if len(raw) > MAX_SETTINGS_BYTES:
                return
            data = json.loads(raw)
            if not isinstance(data, dict):
                return
            self.resolution_index = _safe_int(
                data.get("resolution_index"), self.resolution_index,
                0, len(RESOLUTIONS) - 1,
            )
            self.volume = _safe_float(data.get("volume"), self.volume, 0.0, 1.0)
            self.sensitivity = _safe_float(
                data.get("sensitivity"), self.sensitivity, 0.1, 1.0,
            )
            self.invert_mouse = _safe_bool(
                data.get("invert_mouse"), self.invert_mouse,
            )
            self.fullscreen = _safe_bool(data.get("fullscreen"), self.fullscreen)
            self.best_level = _safe_int(data.get("best_level"), 0, 0, 5)
            self.survival_unlocked = _safe_bool(
                data.get("survival_unlocked"), False,
            )
            self.best_wave = _safe_int(data.get("best_wave"), 0, 0, 999)
            self.last_ip = valid_ipv4(data.get("last_ip")) or self.last_ip

            loaded_keys = data.get("keys", {})
            if not isinstance(loaded_keys, dict):
                loaded_keys = {}
            used = set()
            for action, fallback in DEFAULT_KEYS.items():
                source = loaded_keys.get(action)
                if action == "roulade" and source is None:
                    source = loaded_keys.get("sprint")
                # Migration transparente des anciens réglages : la touche de
                # sprint devient celle de roulade au premier chargement.
                code = _valid_keycode(source)
                if code is None or code in used:
                    code = next(
                        candidate for candidate in
                        (fallback, *DEFAULT_KEYS.values())
                        if candidate not in used
                    )
                self.keys[action] = code
                used.add(code)
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass  # premier lancement ou fichier invalide : valeurs par défaut

    def save(self):
        """Écrit les paramètres courants dans le JSON."""
        data = {
            "resolution_index": self.resolution_index,
            "volume": self.volume,
            "sensitivity": self.sensitivity,
            "invert_mouse": self.invert_mouse,
            "fullscreen": self.fullscreen,
            "best_level": self.best_level,
            "survival_unlocked": self.survival_unlocked,
            "best_wave": self.best_wave,
            "last_ip": self.last_ip,
            "keys": self.keys,
        }
        temporary = SETTINGS_FILE + ".tmp"
        try:
            # Écriture atomique : une coupure pendant json.dump ne détruit pas
            # le dernier fichier de réglages encore valide.
            with open(temporary, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, SETTINGS_FILE)
        except OSError:
            pass  # disque en lecture seule : on joue sans persistance
        finally:
            try:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            except OSError:
                pass

    def reset_keys(self):
        self.keys = dict(DEFAULT_KEYS)

    def bind_key(self, action, key):
        """Assigne une touche sans doublon ; échange avec l'action en conflit."""
        code = _valid_keycode(key)
        if action not in self.keys or code is None:
            return False
        old = self.keys[action]
        conflict = next((name for name, value in self.keys.items()
                         if name != action and value == code), None)
        self.keys[action] = code
        if conflict is not None:
            self.keys[conflict] = old
        return True
