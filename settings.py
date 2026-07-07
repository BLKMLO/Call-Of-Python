"""Gestion des paramètres du jeu.

Centralise la résolution, le volume, la sensibilité de la souris et les
touches de contrôle. Les paramètres sont sauvegardés dans un fichier JSON
(`settings.json`) à côté du jeu afin d'être conservés entre deux sessions.
"""

import json
import os

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
    "sprint": pygame.K_LSHIFT,
    "recharger": pygame.K_r,
}

# L'ordre d'affichage des actions dans le menu des paramètres.
KEY_ACTIONS = ["avancer", "reculer", "gauche", "droite", "sprint", "recharger"]

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


class Settings:
    """Conteneur des paramètres, avec chargement/sauvegarde JSON."""

    def __init__(self):
        self.resolution_index = 3        # 1280x720 par défaut
        self.volume = 0.7                # volume global (0.0 → 1.0)
        self.sensitivity = 0.5           # sensibilité souris (0.1 → 1.0)
        self.keys = dict(DEFAULT_KEYS)   # keycodes pygame par action
        self.best_level = 0              # meilleur niveau atteint (affiché au menu)
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
                data = json.load(f)
            idx = int(data.get("resolution_index", self.resolution_index))
            if 0 <= idx < len(RESOLUTIONS):
                self.resolution_index = idx
            self.volume = min(1.0, max(0.0, float(data.get("volume", self.volume))))
            self.sensitivity = min(1.0, max(0.1, float(data.get("sensitivity", self.sensitivity))))
            self.best_level = max(0, int(data.get("best_level", 0)))
            for action, code in data.get("keys", {}).items():
                if action in self.keys:
                    self.keys[action] = int(code)
        except (OSError, ValueError, json.JSONDecodeError):
            pass  # premier lancement ou fichier invalide : valeurs par défaut

    def save(self):
        """Écrit les paramètres courants dans le JSON."""
        data = {
            "resolution_index": self.resolution_index,
            "volume": self.volume,
            "sensitivity": self.sensitivity,
            "best_level": self.best_level,
            "keys": self.keys,
        }
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass  # disque en lecture seule : on joue sans persistance

    def reset_keys(self):
        self.keys = dict(DEFAULT_KEYS)
