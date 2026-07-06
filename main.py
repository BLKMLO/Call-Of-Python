"""Point d'entrée du jeu — lance : python main.py

Machine à états très simple :
    "menu"     → MainMenu
    "settings" → SettingsMenu
    "game"     → Game (la partie en cours)
    "end"      → EndScreen (game over / victoire)

Chaque état gère ses événements et son rendu ; les transitions sont les
chaînes retournées par les menus et le jeu.
"""

import sys

import pygame

from game import Game
from menu import EndScreen, MainMenu, SettingsMenu
from settings import Settings
from sounds import SoundBank


def create_window(settings):
    return pygame.display.set_mode(settings.resolution)


def set_mouse_captured(captured):
    """Capture (jeu) ou libère (menus) la souris."""
    pygame.event.set_grab(captured)
    pygame.mouse.set_visible(not captured)


def main():
    # Mixer mono 22 kHz : format des sons synthétisés dans sounds.py.
    pygame.mixer.pre_init(22050, -16, 1, 256)
    pygame.init()
    try:
        pygame.mixer.init(22050, -16, 1, 256)
    except pygame.error:
        pass  # pas de carte son : le jeu tourne en silence

    settings = Settings()
    screen = create_window(settings)
    pygame.display.set_caption("PyFPS — raycasting")
    clock = pygame.time.Clock()
    sounds = SoundBank(settings)

    main_menu = MainMenu(sounds)
    settings_menu = SettingsMenu(sounds, settings)
    end_screen = None
    game = None
    state = "menu"
    set_mouse_captured(False)

    running = True
    while running:
        dt = min(clock.tick(60) / 1000.0, 0.05)  # dt borné (fenêtre déplacée...)

        # ------------------------------------------------------------------
        # Événements
        # ------------------------------------------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if state == "menu":
                action = main_menu.handle_event(event, screen)
                if action == "play":
                    game = Game(screen, settings, sounds)
                    state = "game"
                    set_mouse_captured(True)
                elif action == "settings":
                    state = "settings"
                elif action == "quit":
                    running = False

            elif state == "settings":
                action = settings_menu.handle_event(event, screen)
                if action == "resolution":
                    screen = create_window(settings)
                elif action == "back":
                    state = "menu"

            elif state == "game":
                if game.handle_event(event) == "menu":
                    state = "menu"
                    game = None
                    set_mouse_captured(False)

            elif state == "end":
                action = end_screen.handle_event(event, screen)
                if action == "play":
                    game = Game(screen, settings, sounds)
                    state = "game"
                    set_mouse_captured(True)
                elif action == "menu":
                    state = "menu"
                elif action == "quit":
                    running = False

        # ------------------------------------------------------------------
        # Mise à jour + rendu de l'état courant
        # ------------------------------------------------------------------
        if state == "game":
            game.update(dt)
            game.draw(screen)
            if game.finished:
                end_screen = EndScreen(sounds, victory=(game.outcome == "victory"))
                state = "end"
                game = None
                set_mouse_captured(False)
        elif state == "menu":
            main_menu.draw(screen)
        elif state == "settings":
            settings_menu.draw(screen)
        elif state == "end":
            end_screen.draw(screen)

        pygame.display.flip()

    settings.save()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
