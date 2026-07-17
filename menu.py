"""Menus du jeu : menu principal, paramètres, écran de fin de partie.

Les menus sont de simples listes de lignes cliquables, repositionnées à
chaque frame en fonction de la taille de l'écran (elles survivent donc
aux changements de résolution). Chaque menu retourne une chaîne d'action
("play", "settings", "quit", "back", ...) depuis `handle_event`.
"""

import pygame

import assets
from settings import KEY_ACTIONS, RESOLUTIONS

TITLE_COLOR = (238, 242, 240)
TEXT_COLOR = (205, 214, 216)
HOVER_COLOR = (105, 238, 174)
DIM_COLOR = (132, 148, 151)
ACCENT_COLOR = (64, 198, 137)
WARM_COLOR = (230, 151, 67)


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
    _background_cache = {}
    _panel_cache = {}

    def __init__(self, sounds):
        self.sounds = sounds

    def items(self):
        """Liste de (identifiant, libellé) ; surchargée par chaque menu."""
        return []

    def _layout(self, screen):
        """Calcule le rect (et le point de bascule gauche/droite) de chaque
        ligne pour la taille d'écran courante."""
        w, h = screen.get_size()
        rows = []
        items = self.items()
        compact = len(items) > 8
        font = self._font(h, small=compact)
        line_h = int(font.get_height() * (1.5 if compact else 1.7))
        start_y = h // 2 - (len(items) * line_h) // 2 + h // 12
        button_w = min(int(w * 0.36), 560)
        button_h = max(font.get_height() + 12, line_h - 7)
        for i, (ident, label) in enumerate(items):
            rect = pygame.Rect(0, 0, button_w, button_h)
            rect.center = (w // 2, start_y + i * line_h)
            split_x = self._bracket_split(font, label, rect)
            rows.append((ident, label, rect, split_x))
        return rows

    @staticmethod
    def _bracket_split(font, label, rect):
        """Point de bascule gauche/droite d'un bouton "<  valeur  >".

        Doit tomber entre les deux chevrons, pas au centre du texte entier :
        le préfixe du libellé ("Sensibilité souris : ") et son suffixe
        ("50 %  >") n'ont pas la même longueur, donc le milieu de la
        surface rendue ne coïncide pas avec le milieu des chevrons — sans
        quoi cliquer sur "<" pouvait à tort incrémenter la valeur."""
        if "<" not in label or ">" not in label:
            return rect.centerx
        lt = label.index("<")
        gt = label.index(">")
        text_left = rect.centerx - font.size(label)[0] // 2
        lt_x = text_left + font.size(label[:lt])[0]
        gt_x = text_left + font.size(label[:gt + 1])[0]
        return (lt_x + gt_x) // 2

    @staticmethod
    def _font(screen_h, small=False):
        size = max(20, screen_h // (34 if small else 22))
        return pygame.font.SysFont(
            "consolas,dejavusansmono,couriernew", size,
            bold=not small,
        )

    @staticmethod
    def _title_font(screen_h):
        return pygame.font.SysFont(
            "impact,arialblack,dejavusanscondensed",
            max(40, screen_h // 8), bold=True,
        )

    @classmethod
    def _background(cls, size):
        """Fond cinématique recadré en mode cover, mis en cache par taille."""
        if size in cls._background_cache:
            return cls._background_cache[size]
        w, h = size
        try:
            source = assets.get("menu_background")
        except (KeyError, pygame.error):
            source = pygame.Surface(size)
            source.fill((9, 14, 20))
        sw, sh = source.get_size()
        factor = max(w / sw, h / sh)
        scaled_size = (max(w, round(sw * factor)),
                       max(h, round(sh * factor)))
        scaled = pygame.transform.smoothscale(source, scaled_size)
        x = (scaled.get_width() - w) // 2
        y = (scaled.get_height() - h) // 2
        result = scaled.subsurface((x, y, w, h)).copy()
        veil = pygame.Surface(size, pygame.SRCALPHA)
        veil.fill((3, 8, 13, 68))
        result.blit(veil, (0, 0))
        cls._background_cache[size] = result
        return result

    @classmethod
    def _panel(cls, size):
        """Panneau central verre fumé, mis en cache par taille."""
        if size in cls._panel_cache:
            return cls._panel_cache[size]
        panel = pygame.Surface(size, pygame.SRCALPHA)
        rect = panel.get_rect()
        pygame.draw.rect(panel, (4, 10, 15, 214), rect, border_radius=10)
        pygame.draw.rect(panel, (71, 101, 104, 190), rect, 1,
                         border_radius=10)
        pygame.draw.line(panel, (*ACCENT_COLOR, 220), (1, 1),
                         (rect.width - 2, 1), 3)
        cls._panel_cache[size] = panel
        return panel

    def _draw_title(self, screen):
        w, h = screen.get_size()
        title_font = self._title_font(h)
        title_text = self.title.upper()
        shadow = title_font.render(title_text, True, (0, 0, 0))
        title = title_font.render(title_text, True, TITLE_COLOR)
        title_y = h // 8 if len(self.items()) > 8 else h // 5
        pos = title.get_rect(center=(w // 2, title_y))
        screen.blit(shadow, pos.move(3, 4))
        screen.blit(title, pos)
        line_w = min(title.get_width(), int(w * 0.32))
        line_y = pos.bottom + max(5, h // 120)
        pygame.draw.line(screen, ACCENT_COLOR,
                         (w // 2 - line_w // 2, line_y),
                         (w // 2 + line_w // 2, line_y), 2)
        if self.title == "Call of Python":
            tag_font = self._font(h, small=True)
            tag = tag_font.render("TACTICAL RAYCASTING // INCIDENT LUNAIRE",
                                  True, (160, 185, 180))
            screen.blit(tag, tag.get_rect(
                center=(w // 2, line_y + tag.get_height())))

    # ------------------------------------------------------------------
    def handle_event(self, event, screen):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for ident, _label, rect, split_x in self._layout(screen):
                if rect.collidepoint(event.pos):
                    self.sounds.play("click", volume_scale=0.5)
                    return self.on_click(ident, event.pos, rect, split_x)
        return None

    def on_click(self, ident, _pos, _rect, _split_x=None):
        """Par défaut, l'identifiant de la ligne est l'action retournée."""
        return ident

    def draw(self, screen):
        w, h = screen.get_size()
        screen.blit(self._background((w, h)), (0, 0))

        panel_w = min(int(w * 0.42), 650)
        panel_h = int(h * 0.82)
        panel_rect = pygame.Rect(0, 0, panel_w, panel_h)
        panel_rect.center = (w // 2, h // 2 + h // 40)
        screen.blit(self._panel(panel_rect.size), panel_rect)
        self._draw_title(screen)

        mouse = pygame.mouse.get_pos()
        rows = self._layout(screen)
        font = self._font(h, small=len(rows) > 8)
        for ident, label, rect, _split_x in rows:
            hovered = rect.collidepoint(mouse) and ident is not None
            if ident is not None:
                fill = (29, 59, 54, 225) if hovered else (10, 20, 26, 188)
                border = HOVER_COLOR if hovered else (62, 84, 88)
                button = pygame.Surface(rect.size, pygame.SRCALPHA)
                pygame.draw.rect(button, fill, button.get_rect(),
                                 border_radius=4)
                pygame.draw.rect(button, border, button.get_rect(), 1,
                                 border_radius=4)
                if hovered:
                    pygame.draw.rect(button, WARM_COLOR,
                                     (0, 0, 4, rect.height), border_radius=2)
                screen.blit(button, rect)
            color = HOVER_COLOR if hovered else TEXT_COLOR
            text = font.render(label, True, color)
            screen.blit(text, text.get_rect(center=rect.center))
        footer = pygame.Surface((w, max(42, h // 11)), pygame.SRCALPHA)
        footer.fill((3, 8, 12, 205))
        screen.blit(footer, (0, h - footer.get_height()))
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
            screen.blit(text, text.get_rect(center=(w // 2, h - h // 6)))

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

    def on_click(self, ident, pos, rect, split_x=None):
        s = self.settings
        center = split_x if split_x is not None else rect.centerx
        direction = 1 if pos[0] >= center else -1  # moitié droite = +
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

    def on_click(self, ident, _pos, _rect, _split_x=None):
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
