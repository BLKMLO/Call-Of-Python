"""Point d'entrée du jeu — lance : python main.py

Machine à états :
    "menu"           → MainMenu
    "settings"       → SettingsMenu
    "game"           → Game (le niveau en cours)
    "level_complete" → LevelCompleteScreen (transition vers le suivant)
    "end"            → EndScreen (game over / victoire finale)

Progression : un niveau est gagné quand tous ses ennemis sont morts ; le
joueur passe alors au suivant en gardant son arsenal. S'il meurt, il
repart de zéro (niveau 1, pistolet seul).
"""

import sys

import pygame

from game import Game
from level import LEVELS
from menu import EndScreen, LevelCompleteScreen, MainMenu, SettingsMenu
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
    transition = None    # LevelCompleteScreen ou EndScreen courant
    game = None
    state = "menu"
    set_mouse_captured(False)

    def start_level(index, carry=None):
        """Crée le Game du niveau `index` et passe en état de jeu."""
        nonlocal game, state
        game = Game(screen, settings, sounds, index, carry_player=carry)
        state = "game"
        set_mouse_captured(True)

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
                    start_level(0)
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

            elif state in ("level_complete", "end"):
                action = transition.handle_event(event, screen)
                if action == "continue":     # niveau suivant, joueur conservé
                    start_level(game.level_index + 1, carry=game.player)
                elif action == "play":       # nouvelle partie de zéro
                    start_level(0)
                elif action == "menu":
                    state = "menu"
                    game = None
                elif action == "quit":
                    running = False

        # ------------------------------------------------------------------
        # Mise à jour + rendu de l'état courant
        # ------------------------------------------------------------------
        if state == "game":
            game.update(dt)
            game.draw(screen)
            if game.finished:
                set_mouse_captured(False)
                if game.outcome == "dead":
                    transition = EndScreen(sounds, victory=False)
                    state = "end"
                elif game.level_index + 1 < len(LEVELS):
                    transition = LevelCompleteScreen(
                        sounds, game.level_index,
                        LEVELS[game.level_index + 1]["name"])
                    state = "level_complete"
                else:                        # dernier niveau gagné
                    transition = EndScreen(sounds, victory=True)
                    state = "end"
        elif state == "menu":
            main_menu.draw(screen)
        elif state == "settings":
            settings_menu.draw(screen)
        elif state in ("level_complete", "end"):
            transition.draw(screen)

        pygame.display.flip()

    settings.save()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
