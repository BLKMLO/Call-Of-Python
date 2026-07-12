"""Point d'entrée du jeu — lance : python main.py

Machine à états :
    "menu"           → MainMenu
    "settings"       → SettingsMenu
    "game"           → Game ou SurvivalGame (partie en cours)
    "level_complete" → LevelCompleteScreen (transition vers le suivant)
    "seal"           → SealBrokenScreen (le boss abattu était le Sceau)
    "end"            → EndScreen (game over / victoire)

Progression : un niveau est gagné quand tous ses ennemis sont morts ; le
joueur passe alors au suivant en gardant son arsenal. S'il meurt, il
repart de zéro (niveau 1, pistolet seul). Abattre le Colosse du dernier
niveau brise le Sceau et ouvre le Déferlement : le mode survie par
vagues (50 vagues, submersion possible).
"""

import sys

import pygame

from coop import CoopClientGame, CoopHostGame
from game import Game
from level import LEVELS
from menu import (EndScreen, LevelCompleteScreen, MainMenu, MultiplayerMenu,
                  SealBrokenScreen, SettingsMenu)
from settings import Settings
from sounds import SoundBank
from survival import SurvivalGame


def create_window(settings):
    return pygame.display.set_mode(settings.resolution)


def set_mouse_captured(captured):
    """Capture (jeu) ou libère (menus) la souris.

    Le mode relatif (pygame-ce), quand il existe, fournit des deltas bruts
    même sous Wayland/X11 où le curseur peut buter sur le bord de la
    fenêtre malgré le grab — les deltas gardent le même signe partout
    (droite = positif), seule la fiabilité de la capture change."""
    pygame.event.set_grab(captured)
    pygame.mouse.set_visible(not captured)
    if hasattr(pygame.mouse, "set_relative_mode"):
        try:
            pygame.mouse.set_relative_mode(captured)
        except pygame.error:
            pass  # pilote sans support : le grab classique suffit


def main():
    # Mixer stéréo 22 kHz : format des sons synthétisés dans sounds.py
    # (la stéréo permet le panoramique gauche/droite des sons du monde).
    pygame.mixer.pre_init(22050, -16, 2, 256)
    pygame.init()
    try:
        pygame.mixer.init(22050, -16, 2, 256)
    except pygame.error:
        pass  # pas de carte son : le jeu tourne en silence

    settings = Settings()
    screen = create_window(settings)
    pygame.display.set_caption("Call of Python")
    clock = pygame.time.Clock()
    sounds = SoundBank(settings)

    main_menu = MainMenu(sounds, settings)
    settings_menu = SettingsMenu(sounds, settings)
    mp_menu = MultiplayerMenu(sounds, settings)
    transition = None    # LevelCompleteScreen ou EndScreen courant
    game = None
    state = "menu"
    set_mouse_captured(False)
    sounds.play_music("menu")

    def leave_game():
        """Ferme proprement la partie courante (sockets de la coop)."""
        nonlocal game
        if game is not None and hasattr(game, "close"):
            game.close()
        game = None

    def start_level(index, carry=None, stats=None):
        """Crée le Game du niveau `index` et passe en état de jeu."""
        nonlocal game, state
        leave_game()
        game = Game(screen, settings, sounds, index, carry_player=carry,
                    carry_stats=stats)
        state = "game"
        set_mouse_captured(True)
        sounds.play_music(f"level{index}")
        if index + 1 > settings.best_level:     # mémorise la progression
            settings.best_level = index + 1
            settings.save()

    def start_survival(carry=None):
        """Lance le Déferlement (mode survie par vagues)."""
        nonlocal game, state
        leave_game()
        game = SurvivalGame(screen, settings, sounds, carry_player=carry)
        state = "game"
        set_mouse_captured(True)
        sounds.play_music("survival")

    def start_multiplayer(host):
        """Héberge ou rejoint une partie coop du Déferlement en LAN."""
        nonlocal game, state
        leave_game()
        try:
            if host:
                game = CoopHostGame(screen, settings, sounds)
            else:
                game = CoopClientGame(screen, settings, sounds,
                                      settings.last_ip)
        except OSError as error:
            mp_menu.error = f"Erreur réseau : {error}"
            return
        state = "game"
        set_mouse_captured(True)
        sounds.play_music("survival")

    def end_survival():
        """Écran de fin du Déferlement, avec record de vagues."""
        nonlocal transition, state
        wave = game.wave
        settings.best_wave = max(settings.best_wave, wave)
        settings.save()
        if game.outcome == "victory":
            transition = EndScreen(
                sounds, victory=True, title="LÉGENDE", survival=True,
                subtitle="Vous avez brisé le Déferlement : 50 vagues repoussées.",
                stats=game.stats)
        else:
            transition = EndScreen(
                sounds, victory=False, title="SUBMERGÉ", survival=True,
                subtitle=(f"La horde vous a englouti à la vague {wave} "
                          f"(record : vague {settings.best_wave})."),
                stats=game.stats)
        state = "end"
        sounds.play_music("menu")

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
                elif action == "survival":
                    start_survival()
                elif action == "multiplayer":
                    mp_menu.error = ""
                    state = "mp_menu"
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

            elif state == "mp_menu":
                action = mp_menu.handle_event(event, screen)
                if action == "host":
                    start_multiplayer(host=True)
                elif action == "join":
                    settings.save()
                    start_multiplayer(host=False)
                elif action == "back":
                    state = "menu"

            elif state == "game":
                if game.handle_event(event) == "menu":
                    leave_game()
                    state = "menu"
                    set_mouse_captured(False)
                    sounds.play_music("menu")

            elif state in ("level_complete", "seal", "end"):
                action = transition.handle_event(event, screen)
                if action == "continue":     # niveau suivant, joueur conservé
                    start_level(game.level_index + 1, carry=game.player,
                                stats=game.stats)
                elif action == "survival":   # le Déferlement (arsenal conservé
                    carry = game.player if state == "seal" else None
                    start_survival(carry=carry)  # depuis le Sceau)
                elif action == "play":       # nouvelle partie de zéro
                    start_level(0)
                elif action == "menu":
                    leave_game()
                    state = "menu"
                    sounds.play_music("menu")
                elif action == "quit":
                    running = False

        # ------------------------------------------------------------------
        # Mise à jour + rendu de l'état courant
        # ------------------------------------------------------------------
        sounds.refresh_music_volume()   # suit le réglage de volume en direct

        if state == "game":
            game.update(dt)
            game.draw(screen)
            if getattr(game, "disconnected", False):
                # Hôte injoignable ou connexion perdue : retour au menu LAN.
                leave_game()
                mp_menu.error = "Impossible de joindre l'hôte (ou connexion perdue)."
                state = "mp_menu"
                set_mouse_captured(False)
                sounds.play_music("menu")
            elif game.finished:
                set_mouse_captured(False)
                if isinstance(game, (SurvivalGame, CoopClientGame)):
                    end_survival()
                elif game.outcome == "dead":
                    transition = EndScreen(sounds, victory=False,
                                           stats=game.stats)
                    state = "end"
                    sounds.play_music("menu")
                elif game.level_index + 1 < len(LEVELS):
                    transition = LevelCompleteScreen(
                        sounds, game.level_index,
                        LEVELS[game.level_index + 1]["name"],
                        stats=game.stats)
                    state = "level_complete"
                else:
                    # Le Colosse est tombé... et le Sceau avec lui.
                    settings.survival_unlocked = True
                    settings.save()
                    transition = SealBrokenScreen(sounds)
                    state = "seal"
                    sounds.play_music("survival")
        elif state == "menu":
            main_menu.draw(screen)
        elif state == "settings":
            settings_menu.draw(screen)
        elif state == "mp_menu":
            mp_menu.draw(screen)
        elif state in ("level_complete", "seal", "end"):
            transition.draw(screen)

        pygame.display.flip()

    leave_game()
    settings.save()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
