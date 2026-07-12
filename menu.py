"""Menus du jeu : menu principal, paramètres, écran de fin de partie.

Les menus sont de simples listes de lignes cliquables, repositionnées à
chaque frame en fonction de la taille de l'écran (elles survivent donc
aux changements de résolution). Chaque menu retourne une chaîne d'action
("play", "settings", "quit", "back", ...) depuis `handle_event`.
"""

import pygame

from settings import KEY_ACTIONS, RESOLUTIONS

TITLE_COLOR = (235, 235, 240)
TEXT_COLOR = (205, 205, 210)
HOVER_COLOR = (255, 210, 90)
DIM_COLOR = (130, 130, 140)


def format_stats(stats):
    """Ligne de bilan : éliminations, précision, temps de jeu."""
    if stats is None:
        return None
    accuracy = (100.0 * stats["hits"] / stats["shots"]) if stats["shots"] else 0.0
    minutes, seconds = divmod(int(stats["time"]), 60)
    return (f"Éliminations : {stats['kills']}   "
            f"Précision : {accuracy:.0f} %   "
            f"Temps : {minutes} min {seconds:02d} s")


class MenuBase:
    """Mécanique commune : lignes centrées, survol à la souris, clic."""

    title = ""

    def __init__(self, sounds):
        self.sounds = sounds

    def items(self):
        """Liste de (identifiant, libellé) ; surchargée par chaque menu."""
        return []

    def _layout(self, screen):
        """Calcule le rect de chaque ligne pour la taille d'écran courante."""
        w, h = screen.get_size()
        font = self._font(h)
        rows = []
        items = self.items()
        line_h = int(font.get_height() * 1.7)
        start_y = h // 2 - (len(items) * line_h) // 2 + h // 12
        for i, (ident, label) in enumerate(items):
            surf = font.render(label, True, TEXT_COLOR)
            rect = surf.get_rect(center=(w // 2, start_y + i * line_h))
            rows.append((ident, label, rect))
        return rows

    @staticmethod
    def _font(screen_h, small=False):
        size = max(20, screen_h // (34 if small else 22))
        return pygame.font.Font(None, size)

    @staticmethod
    def _title_font(screen_h):
        return pygame.font.Font(None, max(40, screen_h // 8))

    # ------------------------------------------------------------------
    def handle_event(self, event, screen):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for ident, _label, rect in self._layout(screen):
                if rect.collidepoint(event.pos):
                    self.sounds.play("click", volume_scale=0.5)
                    return self.on_click(ident, event.pos, rect)
        return None

    def on_click(self, ident, _pos, _rect):
        """Par défaut, l'identifiant de la ligne est l'action retournée."""
        return ident

    def draw(self, screen):
        w, h = screen.get_size()
        screen.fill((18, 18, 24))
        title = self._title_font(h).render(self.title, True, TITLE_COLOR)
        screen.blit(title, title.get_rect(center=(w // 2, h // 5)))

        mouse = pygame.mouse.get_pos()
        font = self._font(h)
        for ident, label, rect in self._layout(screen):
            hovered = rect.collidepoint(mouse) and ident is not None
            color = HOVER_COLOR if hovered else TEXT_COLOR
            screen.blit(font.render(label, True, color), rect)
        self._draw_footer(screen)

    def _draw_footer(self, screen):
        pass


class MainMenu(MenuBase):
    title = "Call of Python"

    def __init__(self, sounds, settings):
        super().__init__(sounds)
        self.settings = settings

    def items(self):
        rows = [("play", "Jouer")]
        if self.settings.survival_unlocked:
            rows.append(("survival", "Le Déferlement (survie)"))
        rows += [("multiplayer", "Multijoueur LAN (coop)"),
                 ("settings", "Paramètres"), ("quit", "Quitter")]
        return rows

    def draw(self, screen):
        super().draw(screen)
        parts = []
        if self.settings.best_level > 0:
            parts.append(f"Meilleur niveau : {self.settings.best_level}")
        if self.settings.best_wave > 0:
            parts.append(f"Record du Déferlement : vague {self.settings.best_wave}")
        if parts:
            w, h = screen.get_size()
            font = self._font(h, small=True)
            text = font.render("   —   ".join(parts), True, DIM_COLOR)
            screen.blit(text, text.get_rect(center=(w // 2, h // 5 + h // 9)))

    def _draw_footer(self, screen):
        w, h = screen.get_size()
        font = self._font(h, small=True)
        hint = font.render(
            "ZQSD : déplacement (re-mappable)   Souris : visée   Clic : tir   "
            "Maj : sprint   1-4 : armes",
            True, DIM_COLOR)
        screen.blit(hint, hint.get_rect(center=(w // 2, h - h // 14)))


class SettingsMenu(MenuBase):
    """Paramètres : résolution, volume, sensibilité, touches.

    Un clic sur la moitié gauche d'une ligne "< valeur >" décrémente,
    sur la moitié droite incrémente. Un clic sur une ligne de touche
    passe en mode capture : la prochaine touche pressée est assignée.
    """

    title = "Paramètres"

    def __init__(self, sounds, settings):
        super().__init__(sounds)
        self.settings = settings
        self.waiting_action = None  # action en cours de re-mappage

    def items(self):
        s = self.settings
        rows = [
            ("resolution", f"Résolution :  <  {s.resolution[0]} x {s.resolution[1]}  >"),
            ("volume", f"Volume :  <  {int(s.volume * 100)} %  >"),
            ("sensitivity", f"Sensibilité souris :  <  {int(s.sensitivity * 100)} %  >"),
            ("invert_mouse", f"Souris inversée :  <  {'Oui' if s.invert_mouse else 'Non'}  >"),
            (None, ""),  # séparateur
        ]
        for action in KEY_ACTIONS:
            if self.waiting_action == action:
                label = f"{action.capitalize()} :  [appuyez sur une touche]"
            else:
                label = f"{action.capitalize()} :  {s.key_name(action)}"
            rows.append((f"key:{action}", label))
        rows.append(("reset_keys", "Réinitialiser les touches"))
        rows.append(("back", "Retour"))
        return rows

    def handle_event(self, event, screen):
        # Mode capture d'une nouvelle touche.
        if self.waiting_action is not None and event.type == pygame.KEYDOWN:
            if event.key != pygame.K_ESCAPE:  # Échap annule le re-mappage
                self.settings.keys[self.waiting_action] = event.key
                self.settings.save()
            self.waiting_action = None
            self.sounds.play("click", volume_scale=0.5)
            return None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "back"
        return super().handle_event(event, screen)

    def on_click(self, ident, pos, rect):
        s = self.settings
        direction = 1 if pos[0] >= rect.centerx else -1  # moitié droite = +
        if ident == "resolution":
            s.resolution_index = (s.resolution_index + direction) % len(RESOLUTIONS)
            s.save()
            return "resolution"  # main.py recrée la fenêtre
        if ident == "volume":
            s.volume = round(min(1.0, max(0.0, s.volume + 0.1 * direction)), 2)
            s.save()
        elif ident == "sensitivity":
            s.sensitivity = round(min(1.0, max(0.1, s.sensitivity + 0.1 * direction)), 2)
            s.save()
        elif ident == "invert_mouse":
            s.invert_mouse = not s.invert_mouse   # bascule (les deux moitiés)
            s.save()
        elif ident == "reset_keys":
            s.reset_keys()
            s.save()
        elif ident == "back":
            return "back"
        elif ident and ident.startswith("key:"):
            self.waiting_action = ident.split(":", 1)[1]
        return None

    def _draw_footer(self, screen):
        w, h = screen.get_size()
        font = self._font(h, small=True)
        hint = font.render(
            "Cliquez à gauche/droite d'une valeur pour la modifier — "
            "cliquez sur une touche pour la re-mapper",
            True, DIM_COLOR)
        screen.blit(hint, hint.get_rect(center=(w // 2, h - h // 14)))


class EndScreen(MenuBase):
    """Écran de fin : game over (retour au niveau 1) ou victoire.

    En mode survie, "Rejouer" relance le Déferlement et le sous-titre
    affiche la vague atteinte.
    """

    def __init__(self, sounds, victory, title=None, subtitle=None,
                 survival=False, stats=None):
        super().__init__(sounds)
        self.victory = victory
        self.survival = survival
        self.stats_line = format_stats(stats)
        self.title = title or ("VICTOIRE !" if victory else "GAME OVER")
        if subtitle is not None:
            self.subtitle = subtitle
        elif victory:
            self.subtitle = "Tous les niveaux sont terminés, félicitations !"
        else:
            self.subtitle = "Vous avez été abattu — vous repartez de zéro."

    def items(self):
        if self.survival:
            label = "Rejouer le Déferlement"
            action = "survival"
        else:
            label = "Rejouer" if self.victory else "Recommencer (niveau 1)"
            action = "play"
        return [(action, label), ("menu", "Menu principal"), ("quit", "Quitter")]

    def draw(self, screen):
        super().draw(screen)
        w, h = screen.get_size()
        font = self._font(h, small=True)
        surf = font.render(self.subtitle, True, DIM_COLOR)
        screen.blit(surf, surf.get_rect(center=(w // 2, h // 5 + h // 9)))
        if self.stats_line:
            stat = font.render(self.stats_line, True, (200, 180, 130))
            screen.blit(stat, stat.get_rect(
                center=(w // 2, h // 5 + h // 9 + int(font.get_height() * 1.5))))


class MultiplayerMenu(MenuBase):
    """Multijoueur LAN : héberger une partie du Déferlement en coop, ou
    rejoindre un hôte en saisissant son adresse IP."""

    title = "Multijoueur LAN"

    def __init__(self, sounds, settings):
        super().__init__(sounds)
        self.settings = settings
        self.editing = False    # saisie de l'adresse en cours
        self.error = ""         # dernier message d'erreur réseau

    def items(self):
        if self.editing:
            ip_label = f"Adresse de l'hôte : {self.settings.last_ip}_"
        else:
            ip_label = f"Adresse de l'hôte : {self.settings.last_ip}"
        return [
            ("host", "Héberger (Le Déferlement en coop)"),
            ("ip", ip_label),
            ("join", "Rejoindre cette adresse"),
            ("back", "Retour"),
        ]

    def handle_event(self, event, screen):
        if self.editing and event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                             pygame.K_ESCAPE):
                self.editing = False
                self.settings.save()
            elif event.key == pygame.K_BACKSPACE:
                self.settings.last_ip = self.settings.last_ip[:-1]
            elif event.unicode and (event.unicode.isdigit()
                                    or event.unicode == "."):
                if len(self.settings.last_ip) < 15:   # xxx.xxx.xxx.xxx
                    self.settings.last_ip += event.unicode
            return None
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            return "back"
        return super().handle_event(event, screen)

    def on_click(self, ident, _pos, _rect):
        if ident == "ip":
            self.editing = True
            self.error = ""
            return None
        self.editing = False
        return ident

    def _draw_footer(self, screen):
        w, h = screen.get_size()
        font = self._font(h, small=True)
        if self.error:
            surf = font.render(self.error, True, (230, 110, 90))
            screen.blit(surf, surf.get_rect(center=(w // 2, h - h // 9)))
        hint = font.render(
            "L'hôte fait tourner la partie ; les autres le rejoignent par "
            "son adresse IP locale (port 5577).", True, DIM_COLOR)
        screen.blit(hint, hint.get_rect(center=(w // 2, h - h // 14)))


class SealBrokenScreen(MenuBase):
    """Révélation après la mort du Colosse : il était le Sceau."""

    title = "LE SCEAU EST BRISÉ"

    LORE = [
        "Le Colosse s'effondre... et le laboratoire tremble encore.",
        "Trop tard, vous comprenez : il n'était pas leur champion.",
        "Il était le Sceau — et son portail lunaire est grand ouvert.",
        "Sur la Lune, le Déferlement gronde. Tenez 50 vagues.",
    ]

    def items(self):
        return [("survival", "Affronter le Déferlement"),
                ("menu", "Fuir (menu principal)")]

    def draw(self, screen):
        super().draw(screen)
        w, h = screen.get_size()
        font = self._font(h, small=True)
        y = h // 5 + h // 12
        for line in self.LORE:
            surf = font.render(line, True, (200, 160, 130))
            screen.blit(surf, surf.get_rect(center=(w // 2, y)))
            y += int(font.get_height() * 1.35)


class LevelCompleteScreen(MenuBase):
    """Transition entre deux niveaux : annonce le suivant + bilan chiffré."""

    def __init__(self, sounds, finished_index, next_name, stats=None):
        super().__init__(sounds)
        self.title = f"Niveau {finished_index + 1} terminé !"
        self.next_name = next_name
        self.stats_line = format_stats(stats)

    def items(self):
        return [("continue", "Continuer"), ("menu", "Menu principal")]

    def draw(self, screen):
        super().draw(screen)
        w, h = screen.get_size()
        font = self._font(h, small=True)
        text = (f"Prochain niveau : {self.next_name} — "
                "vous gardez vos armes et récupérez de la vie.")
        surf = font.render(text, True, DIM_COLOR)
        screen.blit(surf, surf.get_rect(center=(w // 2, h // 5 + h // 9)))
        if self.stats_line:
            stat = font.render(self.stats_line, True, (200, 180, 130))
            screen.blit(stat, stat.get_rect(
                center=(w // 2, h // 5 + h // 9 + int(font.get_height() * 1.5))))
