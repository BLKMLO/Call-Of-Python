"""Entree manette SDL standardisee pour Xbox, PlayStation et compatibles."""

from __future__ import annotations

import math

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except (ImportError, pygame.error):
    sdl_controller = None

DEADZONE = 0.18
LOOK_PIXELS_PER_TICK = 22.0

ACTION_BUTTONS = {
    pygame.CONTROLLER_BUTTON_A: "roll",
    pygame.CONTROLLER_BUTTON_X: "reload",
    pygame.CONTROLLER_BUTTON_Y: "weapon",
    pygame.CONTROLLER_BUTTON_START: "pause",
}


def _axis_value(raw, deadzone=DEADZONE):
    value = max(-1.0, min(1.0, float(raw) / 32767.0))
    magnitude = abs(value)
    if magnitude <= deadzone:
        return 0.0
    scaled = (magnitude - deadzone) / (1.0 - deadzone)
    return math.copysign(scaled, value)


class GamepadInput:
    """Premier controleur SDL reconnu, avec branchement a chaud."""

    def __init__(self):
        self.controller = None
        self._buttons = {}
        self._actions = []
        self._fire_was_held = False
        self._open_first()

    @property
    def connected(self):
        try:
            return self.controller is not None and self.controller.attached()
        except pygame.error:
            return False

    def _open_first(self):
        if sdl_controller is None:
            return
        try:
            if not sdl_controller.get_init():
                sdl_controller.init()
            for index in range(sdl_controller.get_count()):
                if sdl_controller.is_controller(index):
                    self.controller = sdl_controller.Controller(index)
                    self._buttons.clear()
                    return
        except pygame.error:
            self.controller = None

    def handle_event(self, event):
        if event.type in (pygame.CONTROLLERDEVICEADDED, pygame.JOYDEVICEADDED):
            if not self.connected:
                self._open_first()
        elif event.type in (
                pygame.CONTROLLERDEVICEREMOVED, pygame.JOYDEVICEREMOVED):
            if not self.connected:
                self.close()
                self._open_first()

    def _axis(self, axis):
        if not self.connected:
            return 0.0
        try:
            return _axis_value(self.controller.get_axis(axis))
        except pygame.error:
            return 0.0

    def _button(self, button):
        if not self.connected:
            return False
        try:
            return bool(self.controller.get_button(button))
        except pygame.error:
            return False

    def update(self):
        self._actions.clear()
        if not self.connected:
            return
        for button, action in ACTION_BUTTONS.items():
            pressed = self._button(button)
            if pressed and not self._buttons.get(button, False):
                self._actions.append(action)
            self._buttons[button] = pressed
        firing = self.fire_held
        if firing and not self._fire_was_held:
            self._actions.append("fire")
        self._fire_was_held = firing

    def consume_actions(self):
        actions = tuple(self._actions)
        self._actions.clear()
        self._fire_was_held = False
        return actions

    def movement_axes(self):
        return (
            -self._axis(pygame.CONTROLLER_AXIS_LEFTY),
            self._axis(pygame.CONTROLLER_AXIS_LEFTX),
        )

    def look_delta(self):
        return (
            self._axis(pygame.CONTROLLER_AXIS_RIGHTX) * LOOK_PIXELS_PER_TICK,
            self._axis(pygame.CONTROLLER_AXIS_RIGHTY) * LOOK_PIXELS_PER_TICK,
        )

    @property
    def fire_held(self):
        return (
            self._button(pygame.CONTROLLER_BUTTON_RIGHTSHOULDER)
            or self._axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT) > 0.2
        )

    @property
    def aim_held(self):
        return self._axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT) > 0.2

    def rumble(self, low=0.35, high=0.55, duration_ms=90):
        if not self.connected:
            return False
        try:
            return bool(self.controller.rumble(low, high, duration_ms))
        except pygame.error:
            return False

    def close(self):
        if self.controller is not None:
            try:
                self.controller.quit()
            except pygame.error:
                pass
        self.controller = None
        self._buttons.clear()
        self._actions.clear()
