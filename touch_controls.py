"""Commandes tactiles activées uniquement lorsqu'un écran tactile est présent.

Le stick gauche pilote le déplacement, un glissement sur la moitié droite
oriente la caméra et des boutons dédiés couvrent tir, visée, roulade,
rechargement, changement d'arme, pause et retour menu.
"""

import math
from typing import ClassVar

import pygame

FINGER_EVENTS = (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP)


def detect_touchscreen():
    """Retourne True si SDL expose au moins un périphérique tactile."""
    try:
        from pygame._sdl2 import touch
        return touch.get_num_devices() > 0
    except (ImportError, AttributeError, OSError, pygame.error, RuntimeError):
        return False


class TouchControls:
    """État multi-touch indépendant de la souris et du clavier."""

    MOVE_CENTER = (0.16, 0.72)
    MOVE_RADIUS = 0.115
    DEADZONE = 0.16

    BUTTON_LAYOUT: ClassVar = {
        "fire": (0.88, 0.75, 0.082, "TIR"),
        "aim": (0.76, 0.61, 0.064, "VISÉE"),
        "roll": (0.69, 0.75, 0.068, "ROUL."),
        "reload": (0.90, 0.54, 0.055, "R"),
        "weapon": (0.62, 0.64, 0.055, "ARME"),
        "pause": (0.96, 0.33, 0.044, "II"),
        "menu": (0.04, 0.33, 0.044, "M"),
    }

    def __init__(self, size, detected=None):
        self.enabled = (detect_touchscreen() if detected is None
                        else bool(detected))
        self.size = (0, 0)
        self.move_finger = None
        self.look_finger = None
        self.finger_positions = {}
        self.fire_fingers = set()
        self.aim_fingers = set()
        self.look_dx = 0.0
        self.look_dy = 0.0
        self.move_x = 0.0
        self.move_y = 0.0
        self._overlay = None
        self._font = None
        self._buttons = {}
        self.resize(size)

    @property
    def fire_held(self):
        return bool(self.fire_fingers)

    @property
    def aim_held(self):
        return bool(self.aim_fingers)

    def resize(self, size):
        self.size = tuple(size)
        width, height = self.size
        self._overlay = pygame.Surface(self.size, pygame.SRCALPHA)
        self._font = pygame.font.SysFont(
            "consolas", max(12, min(width, height) // 38), bold=True,
        )
        scale = min(width, height)
        self._buttons = {
            action: (round(x * width), round(y * height),
                     max(20, round(radius * scale)), label)
            for action, (x, y, radius, label) in self.BUTTON_LAYOUT.items()
        }

    def reset(self):
        """Libère tous les doigts lors d'une perte de focus ou d'une pause."""
        self.move_finger = None
        self.look_finger = None
        self.finger_positions.clear()
        self.fire_fingers.clear()
        self.aim_fingers.clear()
        self.look_dx = self.look_dy = 0.0
        self.move_x = self.move_y = 0.0

    def handle_event(self, event):
        """Met à jour l'état et retourne les actions ponctuelles déclenchées."""
        if event.type not in FINGER_EVENTS:
            return ()
        self.enabled = True       # couvre connexion/hot-plug après le démarrage
        finger_id = getattr(event, "finger_id", 0)
        x = max(0.0, min(1.0, float(getattr(event, "x", 0.0))))
        y = max(0.0, min(1.0, float(getattr(event, "y", 0.0))))

        if event.type == pygame.FINGERDOWN:
            self.finger_positions[finger_id] = (x, y)
            action = self._button_at(x, y)
            if action == "fire":
                self.fire_fingers.add(finger_id)
                return ("fire_down",)
            if action == "aim":
                self.aim_fingers.add(finger_id)
                return ("aim_down",)
            if action in ("roll", "reload", "weapon", "pause", "menu"):
                return (action,)
            if x < 0.46 and y > 0.34 and self.move_finger is None:
                self.move_finger = finger_id
                self._set_move(x, y)
            elif self.look_finger is None:
                self.look_finger = finger_id
            return ()

        old_x, old_y = self.finger_positions.get(finger_id, (x, y))
        self.finger_positions[finger_id] = (x, y)
        if event.type == pygame.FINGERMOTION:
            if finger_id == self.move_finger:
                self._set_move(x, y)
            elif finger_id == self.look_finger:
                width, height = self.size
                self.look_dx += (x - old_x) * width * 0.85
                self.look_dy += (y - old_y) * height * 0.85
            return ()

        actions = []
        if finger_id == self.move_finger:
            self.move_finger = None
            self.move_x = self.move_y = 0.0
        if finger_id == self.look_finger:
            self.look_finger = None
        if finger_id in self.fire_fingers:
            self.fire_fingers.discard(finger_id)
            actions.append("fire_up")
        if finger_id in self.aim_fingers:
            self.aim_fingers.discard(finger_id)
            actions.append("aim_up")
        self.finger_positions.pop(finger_id, None)
        return tuple(actions)

    def _button_at(self, x, y):
        px, py = x * self.size[0], y * self.size[1]
        for action, (cx, cy, radius, _label) in self._buttons.items():
            if math.hypot(px - cx, py - cy) <= radius:
                return action
        return None

    def _set_move(self, x, y):
        dx = (x - self.MOVE_CENTER[0]) / self.MOVE_RADIUS
        dy = (y - self.MOVE_CENTER[1]) / self.MOVE_RADIUS
        length = math.hypot(dx, dy)
        if length > 1.0:
            dx, dy = dx / length, dy / length
            length = 1.0
        if length < self.DEADZONE:
            self.move_x = self.move_y = 0.0
            return
        scale = (length - self.DEADZONE) / (1.0 - self.DEADZONE)
        self.move_x = dx / length * scale
        self.move_y = dy / length * scale

    def movement_axes(self):
        """Axes compatibles avec Player : avant positif, droite positive."""
        return -self.move_y, self.move_x

    def consume_look(self):
        delta = (self.look_dx, self.look_dy)
        self.look_dx = self.look_dy = 0.0
        return delta

    def draw(self, screen, paused=False):
        if not self.enabled:
            return
        if screen.get_size() != self.size:
            self.resize(screen.get_size())
        overlay = self._overlay
        overlay.fill((0, 0, 0, 0))
        width, height = self.size
        scale = min(width, height)

        center = (round(self.MOVE_CENTER[0] * width),
                  round(self.MOVE_CENTER[1] * height))
        radius = max(32, round(self.MOVE_RADIUS * scale))
        pygame.draw.circle(overlay, (5, 18, 20, 112), center, radius)
        pygame.draw.circle(overlay, (70, 238, 161, 155), center, radius, 2)
        knob = (
            round(center[0] + self.move_x * radius * 0.62),
            round(center[1] + self.move_y * radius * 0.62),
        )
        pygame.draw.circle(overlay, (102, 255, 185, 178),
                           knob, max(16, radius // 3))

        for action, (cx, cy, button_radius, label) in self._buttons.items():
            held = ((action == "fire" and self.fire_held)
                    or (action == "aim" and self.aim_held)
                    or (paused and action == "pause"))
            fill = ((42, 214, 127, 188) if held
                    else (5, 18, 20, 132))
            pygame.draw.circle(overlay, fill, (cx, cy), button_radius)
            pygame.draw.circle(overlay, (88, 255, 174, 190),
                               (cx, cy), button_radius, 2)
            text = self._font.render(label, True, (226, 255, 238))
            overlay.blit(text, text.get_rect(center=(cx, cy)))
        screen.blit(overlay, (0, 0))
