"""Menus du jeu : menu principal, paramètres, écran de fin de partie.

Les menus sont de simples listes de lignes cliquables, repositionnées à
chaque frame en fonction de la taille de l'écran (elles survivent donc
aux changements de résolution). Chaque menu retourne une chaîne d'action
("play", "settings", "quit", "back", ...) depuis `handle_event`.
"""

import math
from typing import ClassVar

import pygame

import assets
from difficulty import get_difficulty
from settings import KEY_ACTIONS, RESOLUTIONS, valid_ipv4
from ui_style import STYLE_CACHE, STYLE_LIMIT, glow_surface, styled_text, tracked, tracked_width
from version import GAME_VERSION

ACTION_LABELS = {"roulade": "Glissade"}

TITLE_COLOR = (238, 242, 240)
TEXT_COLOR = (205, 214, 216)
HOVER_COLOR = (105, 238, 174)
DIM_COLOR = (132, 148, 151)
ACCENT_COLOR = (64, 198, 137)
WARM_COLOR = (230, 151, 67)
SELECTED_TEXT = (6, 20, 15)
DANGER_COLOR = (226, 72, 64)
GOLD_COLOR = (244, 196, 84)
UI_FONTS = "bahnschrift,dejavusans,arial,liberationsans"
# Thème des menus selon la difficulté : vert (Recrue), ambre (Soldat),
# rouge (Vétéran). `tint` colore l'illustration de fond (None = intacte).
THEMES = {
    "recruit": {"accent": ACCENT_COLOR, "hover": HOVER_COLOR, "warm": WARM_COLOR,
                "tint": None, "chevrons": 1},
    "soldier": {"accent": (222, 156, 58), "hover": (250, 198, 108),
                "warm": (96, 188, 222), "tint": (255, 178, 92), "chevrons": 2},
    "veteran": {"accent": (212, 62, 56), "hover": (246, 112, 100),
                "warm": (240, 196, 90), "tint": (255, 84, 70), "chevrons": 3},
}
_theme_key = "soldier"


def set_theme(difficulty):
    """Choisit le thème des menus d'après la clé de difficulté."""
    global _theme_key
    _theme_key = difficulty if difficulty in THEMES else "soldier"


def theme(name):
    return THEMES[_theme_key][name]


GRADE_COLORS = {"S": GOLD_COLOR, "A": HOVER_COLOR, "B": (120, 200, 230),
                "C": (214, 214, 200), "D": DIM_COLOR}

# Les menus demandent plusieurs polices par frame : SysFont reconstruit
# l'objet Font à chaque appel, on les mutualise donc pour toute la session.
_FONT_CACHE = {}


def _sysfont(names, size, bold=False):
    """`pygame.font.SysFont` mis en cache par (noms, taille, graisse)."""
    key = (names, size, bold)
    font = _FONT_CACHE.get(key)
    if font is None:
        font = pygame.font.SysFont(names, size, bold=bold)
        _FONT_CACHE[key] = font
    return font


def _keycap_strip(pairs, height, max_width):
    """Bandeau d'aides façon jeu : [TOUCHE] ACTION, centré, mis en cache."""
    key = ("keycaps", tuple(pairs), height, max_width, _theme_key)
    cached = STYLE_CACHE.get(key)
    if cached is not None:
        return cached
    size = max(11, height // 50)
    while True:
        font = _sysfont(UI_FONTS, size, bold=True)
        pad_x, gap, inner = max(6, size // 2), max(16, size * 2), max(6, size // 2)
        cap_h = font.get_height() + 6
        widths = [font.size(k)[0] + pad_x * 2 + inner + font.size(a)[0]
                  for k, a in pairs]
        total = sum(widths) + gap * (len(pairs) - 1)
        if total <= max_width or size <= 9:
            break
        size -= 1
    surface = pygame.Surface((max(1, total), cap_h), pygame.SRCALPHA)
    x = 0
    for (cap, action), width in zip(pairs, widths, strict=True):
        cap_w = font.size(cap)[0] + pad_x * 2
        rect = pygame.Rect(x, 0, cap_w, cap_h)
        pygame.draw.rect(surface, (18, 38, 34, 235), rect, border_radius=3)
        pygame.draw.rect(surface, (*theme("accent"), 200), rect, 1, border_radius=3)
        pygame.draw.line(surface, (*theme("accent"), 255), (rect.left + 2, rect.bottom - 1),
                         (rect.right - 3, rect.bottom - 1), 2)
        glyph = font.render(cap, True, TITLE_COLOR)
        surface.blit(glyph, glyph.get_rect(center=rect.center))
        label = font.render(action, True, DIM_COLOR)
        surface.blit(label, (rect.right + inner, (cap_h - label.get_height()) // 2))
        x += width + gap
    if len(STYLE_CACHE) >= STYLE_LIMIT:
        STYLE_CACHE.clear()
    STYLE_CACHE[key] = surface
    return surface


def stat_cards(stats):
    """Bilan découpé en cartes (libellé, valeur, couleur) pour les écrans
    de fin ; `None` si aucune statistique n'est disponible."""
    if stats is None:
        return None
    accuracy = (100.0 * stats["hits"] / stats["shots"]) if stats["shots"] else 0.0
    minutes, seconds = divmod(int(stats["time"]), 60)
    cards = []
    if "score" in stats:
        grade = stats.get("grade", "D")
        cards += [("SCORE", str(stats["score"]), GOLD_COLOR),
                  ("GRADE", grade, GRADE_COLORS.get(grade, TEXT_COLOR))]
    cards += [("ÉLIM.", str(stats["kills"]), TITLE_COLOR),
              ("PRÉCISION", f"{accuracy:.0f} %", TITLE_COLOR),
              ("TEMPS", f"{minutes}:{seconds:02d}", TITLE_COLOR)]
    return cards


def format_stats(stats):
    """Ligne de bilan : éliminations, précision, temps de jeu."""
    if stats is None:
        return None
    accuracy = (100.0 * stats["hits"] / stats["shots"]) if stats["shots"] else 0.0
    minutes, seconds = divmod(int(stats["time"]), 60)
    score = (f"Score : {stats['score']} · Grade {stats.get('grade', 'D')} · "
             if "score" in stats else "")
    return (score + f"Éliminations : {stats['kills']} · "
            f"Précision : {accuracy:.0f} % · "
            f"Temps : {minutes} min {seconds:02d} s")


class MenuBase:
    """Mécanique commune : boutons latéraux, survol à la souris, clic."""

    title = ""
    kicker = ""                    # petite ligne « // ... » au-dessus du titre
    title_color = TITLE_COLOR
    glow_color = None              # halo du titre (None = thème ; rouge/or en fin)
    menu_vertical_offset = 0.0
    nav_hints = (("FLÈCHES", "NAVIGUER"), ("ENTRÉE", "VALIDER"),
                 ("ÉCHAP", "RETOUR"))
    _background_cache = {}
    _panel_cache = {}
    _button_cache: ClassVar[dict] = {}
    _glow_cache: ClassVar[dict] = {}

    def __init__(self, sounds):
        self.sounds = sounds
        self.selected = None
        self.keyboard_focus = False

    def items(self):
        """Liste de (identifiant, libellé) ; surchargée par chaque menu."""
        return []

    @staticmethod
    def _display(label):
        """Libellé tel qu'affiché : capitales, comme un menu de jeu."""
        return label.upper()

    def _layout(self, screen):
        """Calcule le rect (et le point de bascule gauche/droite) de chaque
        ligne pour la taille d'écran courante."""
        w, h = screen.get_size()
        rows = []
        items = self.items()
        compact = len(items) > 8
        font = self._font(h, small=compact)
        line_h = (font.get_height() + 6 if compact
                  else int(font.get_height() * 1.7))
        start_y = (h // 2 - (len(items) * line_h) // 2 + h // 12
                   + int(h * self.menu_vertical_offset))
        button_w = min(int(w * 0.36), 560)
        button_h = (font.get_height() + 4 if compact
                    else max(font.get_height() + 12, line_h - 7))
        if compact:
            panel = self._panel_rect(screen)
            button_w = panel.width - 32
            title_font = self._title_font(h, self.title, panel.width - 28)
            top = h // 8 + title_font.get_height() // 2 + 12
            bottom = h - max(42, h // 11) - 8
            line_h = min(line_h, (bottom - top) // len(items))
            button_h = min(button_h, line_h - 2)
            start_y = top + button_h // 2
        placed = []
        for i, (ident, label) in enumerate(items):
            rect = pygame.Rect(0, 0, button_w, button_h)
            rect.center = (self._content_center_x(screen),
                           start_y + i * line_h)
            placed.append((ident, label, rect))
        row_font = self._shared_font(h, placed, compact)
        for ident, label, rect in placed:
            split_x = self._bracket_split(row_font, self._display(label), rect)
            rows.append((ident, label, rect, split_x))
        return rows

    def _shared_font(self, height, rows, compact):
        """Une seule taille par menu (la plus petite qui fait tout tenir) :
        des lignes de tailles différentes faisaient « diapositive »."""
        fonts = [self._row_font(height, row[1], row[2], compact) for row in rows]
        if not fonts:
            return self._font(height, small=compact)
        return min(fonts, key=lambda font: font.get_height())

    def _row_font(self, height, label, rect, compact):
        font = self._font(height, small=compact)
        available = rect.right - self._button_text_left(rect) - self._button_skew(rect)
        size = font.get_height()
        text = self._display(label)
        while font.size(text)[0] > available and size > 10:
            size -= 1
            font = _sysfont("bahnschrift,dejavusans,arial,liberationsans", size, bold=True)
        return font

    @classmethod
    def _bracket_split(cls, font, label, rect):
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
        text_left = cls._button_text_left(rect)
        lt_x = text_left + font.size(label[:lt])[0]
        gt_x = text_left + font.size(label[:gt + 1])[0]
        return (lt_x + gt_x) // 2

    @staticmethod
    def _button_skew(rect):
        return max(10, min(24, rect.height // 3))

    @classmethod
    def _button_points(cls, rect):
        """Sommets du parallélogramme commun à tous les boutons."""
        skew = cls._button_skew(rect)
        return [
            (rect.left + skew, rect.top),
            (rect.right, rect.top),
            (rect.right - skew, rect.bottom - 1),
            (rect.left, rect.bottom - 1),
        ]

    @classmethod
    def _button_contains(cls, rect, point):
        """Collision exacte, sans coins transparents cliquables."""
        x, y = point
        if not (rect.left <= x < rect.right and rect.top <= y < rect.bottom):
            return False
        skew = cls._button_skew(rect)
        ratio = (y - rect.top) / max(1, rect.height - 1)
        left = rect.left + skew * (1.0 - ratio)
        right = rect.right - skew * ratio
        return left <= x <= right

    @classmethod
    def _button_text_left(cls, rect):
        return rect.left + cls._button_skew(rect) + max(10, rect.height // 4)

    @classmethod
    def _button_surface(cls, size, hovered):
        """Fond parallélogramme mis en cache par taille et état.

        Au repos : plaque sombre avec un liseré à gauche. Sélectionné :
        barre pleine couleur accent, reflet en haut et tranche chaude —
        la ligne « s'allume » comme dans un menu de jeu."""
        key = (size, bool(hovered), _theme_key)
        surface = cls._button_cache.get(key)
        if surface is not None:
            return surface
        surface = pygame.Surface(size, pygame.SRCALPHA)
        rect = surface.get_rect()
        points = cls._button_points(rect)
        if hovered:
            pygame.draw.polygon(surface, (*theme("accent"), 240), points)
            highlight = [points[0], points[1],
                         (points[1][0] - cls._button_skew(rect) * 0.4, rect.height * 0.4),
                         (points[0][0] - cls._button_skew(rect) * 0.4, rect.height * 0.4)]
            pygame.draw.polygon(surface, (255, 255, 255, 46), highlight)
            # Le contour n'apparaît qu'au survol, comme demandé.
            pygame.draw.polygon(surface, theme("hover"), points, 2)
            pygame.draw.line(surface, theme("warm"), points[0], points[3], 4)
        else:
            pygame.draw.polygon(surface, (6, 14, 19, 178), points)
            pygame.draw.line(surface, (*theme("accent"), 120), points[0], points[3], 2)
        cls._button_cache[key] = surface
        return surface

    @classmethod
    def _button_glow(cls, size):
        """Halo pulsé derrière le bouton sélectionné (mis en cache)."""
        glow = cls._glow_cache.get((size, _theme_key))
        if glow is None:
            shape = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.polygon(shape, (255, 255, 255, 255),
                                cls._button_points(shape.get_rect()))
            glow = glow_surface(shape, theme("hover"), max(4, size[1] // 4))
            cls._glow_cache[(size, _theme_key)] = glow
        return glow

    @staticmethod
    def _font(screen_h, small=False):
        size = (max(16, screen_h // 38) if small
                else max(20, screen_h // 22))
        return _sysfont(
            "bahnschrift,dejavusans,arial,liberationsans", size,
            bold=True,
        )

    @staticmethod
    def _title_font(screen_h, text="", max_width=None):
        """Police de titre lisible, avec réduction si le texte est long."""
        size = max(36, screen_h // 11)
        while True:
            font = _sysfont(
                "dejavusans,arial,liberationsans", size, bold=True,
            )
            if (max_width is None or not text
                    or font.size(text)[0] <= max_width or size <= 28):
                return font
            size -= 2

    @classmethod
    def _background(cls, size):
        """Fond cinématique recadré en mode cover, mis en cache par taille."""
        key = (size, _theme_key)
        if key in cls._background_cache:
            return cls._background_cache[key]
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
        tint = theme("tint")
        if tint is not None:
            # Monochrome teinté (ambre/rouge) puis un peu d'original : le
            # portail vert vire à la couleur de la difficulté.
            original = result.copy()
            result = pygame.transform.grayscale(result)
            result.fill(tint, special_flags=pygame.BLEND_RGB_MULT)
            result.blit(result, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
            original.set_alpha(40)
            result.blit(original, (0, 0))
        veil = pygame.Surface(size, pygame.SRCALPHA)
        veil.fill((3, 8, 13, 40))
        # Fondu sombre depuis la gauche (zone de menu) : l'illustration
        # reste intacte à droite, sans cadre « diapositive ».
        fade_w = int(w * 0.62)
        for col in range(0, fade_w, 2):
            t = 1.0 - col / fade_w
            pygame.draw.line(veil, (2, 6, 10, int(40 + 175 * t * t)),
                             (col, 0), (col, h), 2)
        # Vignette haut/bas et lignes de balayage discrètes (écran CRT).
        band = max(20, h // 6)
        for row in range(band):
            alpha = int(150 * (1.0 - row / band) ** 2)
            pygame.draw.line(veil, (0, 0, 0, alpha), (0, row), (w, row))
            pygame.draw.line(veil, (0, 0, 0, alpha), (0, h - 1 - row), (w, h - 1 - row))
        for row in range(0, h, 3):
            pygame.draw.line(veil, (0, 0, 0, 34), (0, row), (w, row))
        result.blit(veil, (0, 0))
        cls._background_cache[key] = result
        return result

    @classmethod
    def _panel(cls, size):
        """Cadre tactique façon HUD : voile léger, coins en équerre et
        coin biseauté, plutôt qu'une boîte arrondie. Mis en cache."""
        key = (size, _theme_key)
        if key in cls._panel_cache:
            return cls._panel_cache[key]
        panel = pygame.Surface(size, pygame.SRCALPHA)
        w, h = size
        cut = max(12, min(w, h) // 14)
        outline = [(cut, 0), (w - 1, 0), (w - 1, h - 1 - cut),
                   (w - 1 - cut, h - 1), (0, h - 1), (0, cut)]
        pygame.draw.polygon(panel, (3, 9, 13, 150), outline)
        pygame.draw.polygon(panel, (71, 101, 104, 70), outline, 1)
        arm = max(18, min(w, h) // 9)
        bright = (*theme("accent"), 235)
        # Équerres en haut à droite et en bas à gauche, biseaux soulignés.
        pygame.draw.lines(panel, bright, False,
                          [(w - 1 - arm, 1), (w - 2, 1), (w - 2, arm)], 3)
        pygame.draw.lines(panel, bright, False,
                          [(1, h - 1 - arm), (1, h - 2), (arm, h - 2)], 3)
        pygame.draw.line(panel, (*theme("warm"), 235), (0, cut), (cut, 0), 3)
        pygame.draw.line(panel, (*theme("warm"), 235), (w - 1, h - 1 - cut),
                         (w - 1 - cut, h - 1), 3)
        # Graduations sur le bord gauche (instrument de visée).
        for y in range(cut + arm, h - arm * 2, max(8, h // 40)):
            pygame.draw.line(panel, (*theme("accent"), 70), (3, y), (8, y), 1)
        cls._panel_cache[key] = panel
        return panel

    @staticmethod
    def _content_center_x(screen):
        w = screen.get_width()
        panel_w = min(int(w * 0.46), 650)
        margin = max(12, int(w * 0.025))
        return margin + panel_w // 2

    def _panel_rect(self, screen):
        """Cadre central commun, également utilisé par les sous-écrans."""
        w, h = screen.get_size()
        panel_w = min(int(w * 0.46), 650)
        panel_h = int(h * 0.82)
        rect = pygame.Rect(0, 0, panel_w, panel_h)
        rect.center = (self._content_center_x(screen), h // 2 + h // 40)
        # Le cadre s'arrête au-dessus de la bande d'aides du bas.
        rect.height = min(rect.height, h - max(42, h // 11) - 8 - rect.top)
        return rect

    @staticmethod
    def _wrap_text(font, text, max_width):
        """Découpe un texte en lignes tenant dans `max_width`."""
        words = text.split()
        if not words:
            return [""]
        lines = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def _draw_stat_cards(self, screen, cards, bottom, max_width):
        """Cartes de bilan alignées (libellé discret, valeur en gros) dont
        le bas tombe sur `bottom` ; renvoie le haut occupé."""
        h = screen.get_height()
        gap = max(4, h // 120)
        card_w = (max_width - gap * (len(cards) - 1)) // len(cards)
        label_font = _sysfont(UI_FONTS, max(9, h // 64), bold=True)
        value_size = max(15, h // 26)
        value_font = _sysfont(UI_FONTS, value_size, bold=True)
        while (value_size > 11 and max(value_font.size(v)[0] for _l, v, _c in cards)
               > card_w - 8):
            value_size -= 1
            value_font = _sysfont(UI_FONTS, value_size, bold=True)
        card_h = label_font.get_height() + value_font.get_height() + 14
        top = bottom - card_h
        x = self._content_center_x(screen) - (card_w * len(cards)
                                              + gap * (len(cards) - 1)) // 2
        for label, value, color in cards:
            rect = pygame.Rect(x, top, card_w, card_h)
            plate = pygame.Surface(rect.size, pygame.SRCALPHA)
            plate.fill((5, 14, 18, 200))
            pygame.draw.rect(plate, (*theme("accent"), 90), plate.get_rect(), 1)
            pygame.draw.line(plate, (*color, 255), (0, 0), (card_w - 1, 0), 3)
            screen.blit(plate, rect)
            name = label_font.render(label, True, DIM_COLOR)
            if name.get_width() > card_w - 6:
                name = pygame.transform.smoothscale(
                    name, (card_w - 6, name.get_height()))
            screen.blit(name, name.get_rect(midtop=(rect.centerx, rect.top + 6)))
            number = value_font.render(value, True, color)
            screen.blit(number, number.get_rect(
                midbottom=(rect.centerx, rect.bottom - 4)))
            x += card_w + gap
        return top

    def _draw_info_blocks(self, screen, blocks, cards=None):
        """Centre plusieurs paragraphes dans l'espace avant les boutons.

        `blocks` contient des couples (texte, couleur). La police et les
        retours à la ligne s'adaptent à la largeur et à la hauteur réellement
        disponibles, afin qu'aucun bilan ne déborde du panneau. `cards`
        (voir `stat_cards`) s'affichent juste au-dessus des boutons.
        """
        blocks = [(text, color) for text, color in blocks if text]
        if not blocks and not cards:
            return
        w, h = screen.get_size()
        panel = self._panel_rect(screen)
        rows = self._layout(screen)
        top = h // 5 + h // 11
        bottom = rows[0][2].top - max(10, h // 60) if rows else panel.bottom - 20
        max_width = panel.width - max(36, panel.width // 10)
        if cards:
            bottom = self._draw_stat_cards(screen, cards, bottom, max_width)
            bottom -= max(8, h // 50)
        if not blocks:
            return
        available = max(1, bottom - top)

        # Réduit progressivement le corps si un bilan très long ne tient pas.
        size = max(17, h // 38)
        while True:
            font = _sysfont(
                "dejavusans,arial,liberationsans", size,
            )
            wrapped = [(self._wrap_text(font, text, max_width), color)
                       for text, color in blocks]
            line_h = font.get_linesize() + max(1, size // 8)
            gap = max(6, size // 2)
            total_h = (sum(len(lines) for lines, _ in wrapped) * line_h
                       + gap * (len(wrapped) - 1))
            if total_h <= available or size <= 14:
                break
            size -= 1

        y = top + max(0, (available - total_h) // 2)
        for index, (lines, color) in enumerate(wrapped):
            for line in lines:
                surf = font.render(line, True, color)
                screen.blit(surf, surf.get_rect(center=(
                    self._content_center_x(screen), y + line_h // 2,
                )))
                y += line_h
            if index + 1 < len(wrapped):
                y += gap

    def _fit_font(self, text, size, max_width, spacing_ratio=0.0, minimum=24):
        """Plus grande police (≤ `size`) dont le texte espacé tient."""
        while True:
            font = _sysfont(UI_FONTS, size, bold=True)
            spacing = int(size * spacing_ratio)
            if tracked_width(font, text, spacing) <= max_width or size <= minimum:
                return font, spacing
            size -= 2

    def _draw_title(self, screen):
        w, h = screen.get_size()
        # Titre en capitales espacées avec halo, petite ligne d'accroche
        # au-dessus et barre segmentée en dessous : un écran de jeu, pas
        # une diapositive. Les intitulés longs sont ajustés à la largeur.
        title_text = self.title.upper()
        glow = self.glow_color or theme("accent")
        panel = self._panel_rect(screen)
        font, spacing = self._fit_font(title_text, max(36, h // 11),
                                       panel.width - 40, 0.06, 26)
        title = styled_text(font, title_text, self.title_color, spacing,
                            glow=glow, glow_radius=max(4, h // 90))
        title_y = h // 8 if len(self.items()) > 8 else h // 5
        center_x = self._content_center_x(screen)
        pos = title.get_rect(center=(center_x, title_y))
        screen.blit(title, pos)
        text_h = font.get_height()
        if self.kicker:
            kick_font = _sysfont(UI_FONTS, max(11, h // 52), bold=True)
            kicker = styled_text(kick_font, self.kicker.upper(), glow,
                                 max(1, h // 300))
            screen.blit(kicker, kicker.get_rect(
                center=(center_x, title_y - text_h // 2 - kicker.get_height() // 3)))
        line_w = min(tracked_width(font, title_text, spacing), int(w * 0.32))
        line_y = title_y + text_h // 2 + max(4, h // 120)
        left = center_x - line_w // 2
        pygame.draw.line(screen, glow, (left, line_y),
                         (left + line_w - 40, line_y), 3)
        for i in range(3):
            x = left + line_w - 32 + i * 12
            pygame.draw.line(screen, theme("warm"), (x, line_y), (x + 7, line_y), 3)

    def _draw_footer_strip(self, screen):
        """Bande basse sombre soulignée d'un filet accent."""
        w, h = screen.get_size()
        height = max(42, h // 11)
        footer = pygame.Surface((w, height), pygame.SRCALPHA)
        footer.fill((3, 8, 12, 215))
        pygame.draw.line(footer, (*theme("accent"), 150), (0, 0), (w, 0), 1)
        pygame.draw.line(footer, (*theme("warm"), 220), (0, 0), (w // 6, 0), 2)
        screen.blit(footer, (0, h - height))

    def _draw_keycaps(self, screen, pairs):
        w, h = screen.get_size()
        strip = _keycap_strip(pairs, h, w - 32)
        screen.blit(strip, strip.get_rect(center=(w // 2, h - max(42, h // 11) // 2)))

    # ------------------------------------------------------------------
    def handle_event(self, event, screen):
        rows = [row for row in self._layout(screen) if row[0] is not None]
        if not rows:
            return None
        if self.selected not in [row[0] for row in rows]:
            self.selected = rows[0][0]
        key = None
        if event.type == pygame.KEYDOWN:
            key = event.key
        elif event.type == pygame.CONTROLLERBUTTONDOWN:
            key = {
                pygame.CONTROLLER_BUTTON_DPAD_UP: pygame.K_UP,
                pygame.CONTROLLER_BUTTON_DPAD_DOWN: pygame.K_DOWN,
                pygame.CONTROLLER_BUTTON_DPAD_LEFT: pygame.K_LEFT,
                pygame.CONTROLLER_BUTTON_DPAD_RIGHT: pygame.K_RIGHT,
                pygame.CONTROLLER_BUTTON_A: pygame.K_RETURN,
                pygame.CONTROLLER_BUTTON_B: pygame.K_ESCAPE,
            }.get(event.button)
        if key is not None:
            self.keyboard_focus = True
            index = next(i for i, row in enumerate(rows) if row[0] == self.selected)
            if key in (pygame.K_UP, pygame.K_DOWN):
                index = (index + (1 if key == pygame.K_DOWN else -1)) % len(rows)
                self.selected = rows[index][0]
                return None
            if key == pygame.K_ESCAPE:
                return next((ident for ident in ("back", "menu")
                             if any(row[0] == ident for row in rows)), None)
            ident, label, rect, split_x = rows[index]
            adjust = key in (pygame.K_LEFT, pygame.K_RIGHT) and "<" in label
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) or adjust:
                direction = -1 if key == pygame.K_LEFT else 1
                self.sounds.play("click", volume_scale=0.5)
                return self.on_click(ident, (split_x + direction, rect.centery),
                                     rect, split_x)
        if event.type == pygame.MOUSEMOTION and any(event.rel):
            self.keyboard_focus = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.keyboard_focus = False
            for ident, _label, rect, split_x in rows:
                if ident is not None and self._button_contains(rect, event.pos):
                    self.selected = ident
                    self.sounds.play("click", volume_scale=0.5)
                    return self.on_click(ident, event.pos, rect, split_x)
        return None

    def on_click(self, ident, _pos, _rect, _split_x=None):
        """Par défaut, l'identifiant de la ligne est l'action retournée."""
        return ident

    def draw(self, screen):
        w, h = screen.get_size()
        screen.blit(self._background((w, h)), (0, 0))

        panel_rect = self._panel_rect(screen)
        screen.blit(self._panel(panel_rect.size), panel_rect)
        self._draw_title(screen)

        mouse = pygame.mouse.get_pos()
        rows = self._layout(screen)
        pulse = 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 260.0)
        font = self._shared_font(h, rows, len(rows) > 8)
        for ident, label, rect, _split_x in rows:
            hovered = (ident is not None
                       and ((self.keyboard_focus and ident == self.selected)
                            or (not self.keyboard_focus
                                and self._button_contains(rect, mouse))))
            offset = 0
            if hovered:
                glow = self._button_glow(rect.size)
                glow.set_alpha(int(70 + 90 * pulse))
                screen.blit(glow, glow.get_rect(center=rect.center))
                offset = max(4, rect.height // 8)   # la ligne avance d'un cran
                # Chevron de sélection qui « respire » devant la ligne.
                tip_x = rect.left - 4 - int(3 * pulse)
                half = max(4, rect.height // 6)
                pygame.draw.polygon(screen, theme("warm"), [
                    (tip_x, rect.centery), (tip_x - half, rect.centery - half),
                    (tip_x - half, rect.centery + half)])
            if ident is not None:
                screen.blit(self._button_surface(rect.size, hovered), rect)
            color = SELECTED_TEXT if hovered else TEXT_COLOR
            if ident is None:
                color = DIM_COLOR
            text = font.render(self._display(label), True, color)
            text_rect = text.get_rect()
            text_rect.midleft = (
                self._button_text_left(rect) + offset, rect.centery,
            )
            screen.blit(text, text_rect)
        self._draw_footer_strip(screen)
        self._draw_footer(screen)

    def _draw_footer(self, screen):
        self._draw_keycaps(screen, self.nav_hints)


class MainMenu(MenuBase):
    title = "Call of Python"

    def __init__(self, sounds, settings):
        super().__init__(sounds)
        self.settings = settings

    @staticmethod
    def _font(screen_h, small=False):
        size = max(15, screen_h // (45 if small else 30))
        return _sysfont(
            "bahnschrift,dejavusans,arial,liberationsans", size, bold=True,
        )

    def items(self):
        rows = [("play", "JOUER LA CAMPAGNE")]
        if self.settings.survival_unlocked:
            rows.append(("survival", "LE DÉFERLEMENT"))
        label = get_difficulty(getattr(self.settings, "difficulty", "soldier")).label
        rows += [("difficulty", f"DIFFICULTÉ  <  {label}  >"),
                 ("multiplayer", "COOPÉRATION LAN"),
                 ("settings", "PARAMÈTRES"), ("quit", "QUITTER")]
        return rows

    def on_click(self, ident, pos, rect, split_x=None):
        if ident == "difficulty":
            center = split_x if split_x is not None else rect.centerx
            self.settings.cycle_difficulty(1 if pos[0] >= center else -1)
            self.settings.save()
            set_theme(self.settings.difficulty)
            return None
        return ident

    @staticmethod
    def _content_center_x(screen):
        return int(screen.get_width() * 0.235)

    def _panel_rect(self, screen):
        w, h = screen.get_size()
        panel_w = min(int(w * 0.39), 520)
        panel_h = int(h * 0.84)
        rect = pygame.Rect(0, 0, panel_w, panel_h)
        rect.center = (self._content_center_x(screen), h // 2)
        rect.height = min(rect.height, h - max(42, h // 11) - 8 - rect.top)
        return rect

    def _layout(self, screen):
        rows = super()._layout(screen)
        max_w = self._panel_rect(screen).width - 34
        result = []
        resized_rows = []
        for ident, label, rect, _split in rows:
            width = min(rect.width, max_w)
            resized_rows.append((ident, label, pygame.Rect(
                rect.centerx - width // 2, rect.y, width, rect.height,
            )))
        font = self._shared_font(screen.get_height(), resized_rows, len(rows) > 8)
        for ident, label, resized in resized_rows:
            result.append((
                ident, label, resized,
                self._bracket_split(font, self._display(label), resized),
            ))
        return result

    def _draw_title(self, screen):
        """Logo : « CALL OF » espacé au-dessus d'un « PYTHON » géant
        auréolé, puis une étiquette biseautée « INCIDENT LUNAIRE »."""
        w, h = screen.get_size()
        panel = self._panel_rect(screen)
        center_x = self._content_center_x(screen)
        max_w = panel.width - 40
        big, big_spacing = self._fit_font("PYTHON", max(48, h // 7), max_w, 0.04, 30)
        small, small_spacing = self._fit_font(
            "CALL OF", max(18, h // 24), max_w, 0.45, 14)
        title_y = h // 5
        logo = styled_text(big, "PYTHON", TITLE_COLOR, big_spacing,
                           glow=theme("accent"), glow_radius=max(5, h // 70))
        logo_rect = logo.get_rect(center=(center_x, title_y))
        screen.blit(logo, logo_rect)
        top = styled_text(small, "CALL OF", theme("hover"), small_spacing)
        screen.blit(top, top.get_rect(
            center=(center_x, title_y - big.get_height() // 2 - small.get_height() // 3)))
        tag_font = _sysfont(UI_FONTS, max(12, h // 48), bold=True)
        tag_text = tracked(tag_font, "INCIDENT LUNAIRE", SELECTED_TEXT, max(1, h // 260))
        tag_rect = tag_text.get_rect().inflate(28, 8)
        tag_rect.midtop = (center_x, title_y + big.get_height() // 2 + max(4, h // 90))
        skew = tag_rect.height // 2
        pygame.draw.polygon(screen, theme("warm"), [
            (tag_rect.left + skew, tag_rect.top), (tag_rect.right, tag_rect.top),
            (tag_rect.right - skew, tag_rect.bottom), (tag_rect.left, tag_rect.bottom)])
        screen.blit(tag_text, tag_text.get_rect(center=tag_rect.center))
        version = _sysfont(UI_FONTS, max(10, h // 64), bold=True).render(
            f"v{GAME_VERSION}", True, DIM_COLOR)
        screen.blit(version, version.get_rect(midleft=(tag_rect.right + 10, tag_rect.centery)))
        self._draw_chevrons(screen, tag_rect.left - 12, tag_rect.centery,
                            max(5, tag_rect.height // 3))

    @staticmethod
    def _draw_chevrons(screen, right, center_y, size):
        """Insigne de grade : 1 à 3 chevrons selon la difficulté."""
        count = theme("chevrons")
        color = theme("hover")
        for index in range(count):
            y = center_y + (index - (count - 1) / 2) * (size * 0.9)
            x = right - size
            pygame.draw.lines(screen, color, False, [
                (x - size, y - size * 0.45), (x, y + size * 0.45),
                (x + size, y - size * 0.45)], 3)

    def draw(self, screen):
        set_theme(getattr(self.settings, "difficulty", "soldier"))
        super().draw(screen)
        self._draw_difficulty_summary(screen)
        parts = []
        if self.settings.best_level > 0:
            parts.append(("MEILLEUR NIVEAU", str(self.settings.best_level)))
        if self.settings.best_wave > 0:
            parts.append(("RECORD DÉFERLEMENT", f"VAGUE {self.settings.best_wave}"))
        if parts:
            w, h = screen.get_size()
            label_font = _sysfont(UI_FONTS, max(11, h // 56), bold=True)
            value_font = _sysfont(UI_FONTS, max(13, h // 42), bold=True)
            center_x = self._content_center_x(screen)
            line_h = value_font.get_linesize() + 2
            start_y = h - h // 6 - (len(parts) - 1) * line_h // 2
            for index, (label, value) in enumerate(parts):
                y = start_y + index * line_h
                name = label_font.render(label, True, DIM_COLOR)
                number = value_font.render(value, True, GOLD_COLOR)
                total = name.get_width() + 10 + number.get_width()
                x = center_x - total // 2
                screen.blit(name, name.get_rect(midleft=(x, y)))
                screen.blit(number, number.get_rect(
                    midleft=(x + name.get_width() + 10, y)))

    def _draw_difficulty_summary(self, screen):
        """Résumé de la difficulté sous sa ligne quand elle est sélectionnée."""
        if self.selected != "difficulty" or not self.keyboard_focus:
            row = next((r for r in self._layout(screen) if r[0] == "difficulty"), None)
            if row is None or not self._button_contains(row[2], pygame.mouse.get_pos()):
                return
        row = next(r for r in self._layout(screen) if r[0] == "difficulty")
        rect = row[2]
        h = screen.get_height()
        font = _sysfont(UI_FONTS, max(10, h // 62), bold=True)
        summary = get_difficulty(self.settings.difficulty).summary.upper()
        text = styled_text(font, summary, theme("hover"))
        screen.blit(text, text.get_rect(
            midright=(rect.right - 4, rect.bottom + font.get_height() // 2)))

    def _draw_footer(self, screen):
        self._draw_keycaps(screen, (("ZQSD", "DÉPLACEMENT"), ("MAJ", "GLISSADE"),
                                    ("SOURIS", "VISÉE / TIR"), ("1-4", "ARMES")))


class SettingsMenu(MenuBase):
    """Paramètres : résolution, volumes, sensibilité, touches.

    Un clic sur la moitié gauche d'une ligne "< valeur >" décrémente,
    sur la moitié droite incrémente. Un clic sur une ligne de touche
    passe en mode capture : la prochaine touche pressée est assignée.
    """

    title = "Paramètres"
    kicker = "// configuration"

    def __init__(self, sounds, settings):
        super().__init__(sounds)
        self.settings = settings
        self.waiting_action = None  # action en cours de re-mappage

    def draw(self, screen):
        set_theme(getattr(self.settings, "difficulty", "soldier"))
        super().draw(screen)

    def items(self):
        s = self.settings
        ads_mode = "Bascule" if getattr(s, "toggle_ads", False) else "Maintien"
        difficulty = get_difficulty(
            getattr(s, "difficulty", "soldier"),
        ).label
        rows = [
            ("resolution", f"Résolution :  <  {s.resolution[0]} x {s.resolution[1]}  >"),
            ("sound_volume",
             f"Effets sonores :  <  {int(s.sound_volume * 100)} %  >"),
            ("music_volume",
             f"Musique :  <  {int(s.music_volume * 100)} %  >"),
            ("sensitivity", f"Sensibilité souris :  <  {int(s.sensitivity * 100)} %  >"),
            ("invert_mouse", f"Souris inversée :  <  {'Oui' if s.invert_mouse else 'Non'}  >"),
            ("fov", f"Champ de vision :  <  {getattr(s, 'fov', 70)} deg  >"),
            ("camera_shake",
             f"Secousses camera :  <  {int(getattr(s, 'camera_shake', 1.0) * 100)} %  >"),
            ("toggle_ads",
             f"Visee clic droit :  <  {ads_mode}  >"),
            ("difficulty",
             f"Difficulté :  <  {difficulty}  >"),
            (None, ""),  # séparateur
        ]
        for action in KEY_ACTIONS:
            # La clé "roulade" est conservée pour les sauvegardes existantes.
            name = ACTION_LABELS.get(action, action.capitalize())
            if self.waiting_action == action:
                label = f"{name} :  [appuyez sur une touche]"
            else:
                label = f"{name} :  {s.key_name(action)}"
            rows.append((f"key:{action}", label))
        rows.append(("reset_keys", "Réinitialiser les touches"))
        rows.append(("back", "Retour"))
        return rows

    def handle_event(self, event, screen):
        # Mode capture d'une nouvelle touche.
        if self.waiting_action is not None and event.type == pygame.CONTROLLERBUTTONDOWN:
            if event.button == pygame.CONTROLLER_BUTTON_B:
                self.waiting_action = None
            return None
        if self.waiting_action is not None and event.type == pygame.KEYDOWN:
            if event.key != pygame.K_ESCAPE:  # Échap annule le re-mappage
                self.settings.bind_key(self.waiting_action, event.key)
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
        if ident == "sound_volume":
            s.sound_volume = round(
                min(1.0, max(0.0, s.sound_volume + 0.1 * direction)), 2,
            )
            s.save()
        elif ident == "music_volume":
            s.music_volume = round(
                min(1.0, max(0.0, s.music_volume + 0.1 * direction)), 2,
            )
            s.save()
        elif ident == "sensitivity":
            s.sensitivity = round(min(1.0, max(0.1, s.sensitivity + 0.1 * direction)), 2)
            s.save()
        elif ident == "invert_mouse":
            s.invert_mouse = not s.invert_mouse   # bascule (les deux moitiés)
            s.save()
        elif ident == "fov":
            s.fov = min(90, max(60, s.fov + 5 * direction))
            s.save()
        elif ident == "camera_shake":
            values = (0.0, 0.5, 1.0)
            index = min(range(len(values)), key=lambda i: abs(
                values[i] - s.camera_shake
            ))
            s.camera_shake = values[(index + direction) % len(values)]
            s.save()
        elif ident == "toggle_ads":
            s.toggle_ads = not s.toggle_ads
            s.save()
        elif ident == "difficulty":
            s.cycle_difficulty(direction)
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
        self._draw_keycaps(screen, (("< >", "RÉGLER"), ("ÉCHAP", "ANNULER / RETOUR"),
                                    ("F11", "RÉSERVÉ"), ("DOUBLON", "TOUCHES ÉCHANGÉES")))


class EndScreen(MenuBase):
    """Écran de fin : game over (retour au niveau 1) ou victoire.

    En mode survie, "Rejouer" relance le Déferlement et le sous-titre
    affiche la vague atteinte.
    """

    menu_vertical_offset = 0.13

    def __init__(self, sounds, victory, title=None, subtitle=None,
                 survival=False, stats=None, coop_mission=False):
        super().__init__(sounds)
        self.victory = victory
        self.survival = survival
        self.coop_mission = coop_mission
        self.stats_line = format_stats(stats)
        self.cards = stat_cards(stats)
        self.title = title or ("VICTOIRE !" if victory else "GAME OVER")
        if victory:
            self.kicker = "// mission accomplie"
            self.title_color, self.glow_color = (255, 236, 190), GOLD_COLOR
        else:
            self.kicker = "// signal perdu"
            self.title_color, self.glow_color = (255, 222, 216), DANGER_COLOR
        if subtitle is not None:
            self.subtitle = subtitle
        elif victory:
            self.subtitle = "Tous les niveaux sont terminés, félicitations !"
        else:
            self.subtitle = "Vous avez été abattu — vous repartez de zéro."

    def items(self):
        if self.coop_mission:
            return [("multiplayer", "Retour au menu LAN"), ("menu", "Menu principal")]
        if self.survival:
            label = "Rejouer le Déferlement"
            action = "survival"
        else:
            label = "Rejouer" if self.victory else "Recommencer (niveau 1)"
            action = "play"
        return [(action, label), ("menu", "Menu principal"), ("quit", "Quitter")]

    def draw(self, screen):
        super().draw(screen)
        self._draw_info_blocks(screen, [(self.subtitle, TEXT_COLOR)], self.cards)


class MultiplayerMenu(MenuBase):
    """Multijoueur LAN : héberger une partie du Déferlement en coop, ou
    rejoindre un hôte en saisissant son adresse IP."""

    title = "Multijoueur LAN"
    kicker = "// liaison tactique"

    def __init__(self, sounds, settings):
        super().__init__(sounds)
        self.settings = settings
        self.editing = False    # saisie de l'adresse en cours
        self.error = ""         # dernier message d'erreur réseau

    def items(self):
        if self.editing:
            ip_label = f"IP hôte : {self.settings.last_ip}_"
        else:
            ip_label = f"IP hôte : {self.settings.last_ip}"
        return [
            ("host", "Héberger : Déferlement"),
            ("host_mission", "Héberger : Mission Entrepôt"),
            ("ip", ip_label),
            ("join", "Rejoindre"),
            ("back", "Retour"),
        ]

    def handle_event(self, event, screen):
        if self.editing and event.type == pygame.CONTROLLERBUTTONDOWN:
            if event.button not in (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_B):
                return None
            event = pygame.event.Event(pygame.KEYDOWN, key=(
                pygame.K_RETURN if event.button == pygame.CONTROLLER_BUTTON_A
                else pygame.K_ESCAPE), unicode="")
        if self.editing and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.editing = False
                self.error = ""
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                address = valid_ipv4(self.settings.last_ip)
                if address is None:
                    self.error = "Adresse IPv4 invalide (ex. 192.168.1.20)."
                    return None
                self.settings.last_ip = address
                self.editing = False
                self.error = ""
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
        if ident == "join":
            address = valid_ipv4(self.settings.last_ip)
            if address is None:
                self.error = "Adresse IPv4 invalide (ex. 192.168.1.20)."
                return None
            self.settings.last_ip = address
        self.editing = False
        return ident

    def _draw_footer(self, screen):
        w, h = screen.get_size()
        font = self._font(h, small=True)
        if self.error:
            surf = styled_text(font, self.error.upper(), DANGER_COLOR)
            screen.blit(surf, surf.get_rect(center=(w // 2, h - h // 9)))
        self._draw_keycaps(screen, (("HÔTE", "FAIT TOURNER LA PARTIE"),
                                    ("IP LOCALE", "POUR REJOINDRE"),
                                    ("PORT", "5577")))


class SealBrokenScreen(MenuBase):
    """Révélation après la mort du Colosse : il était le Sceau."""

    title = "LE SCEAU EST BRISÉ"
    kicker = "// alerte — brèche lunaire"
    title_color = (255, 222, 216)
    glow_color = DANGER_COLOR
    CHARS_PER_SECOND = 55          # défilement « machine à écrire »

    def __init__(self, sounds):
        super().__init__(sounds)
        self._opened_at = None

    LORE = [
        "Le Colosse s'effondre... et le laboratoire tremble encore.",
        "Trop tard, vous comprenez : il n'était pas leur champion.",
        "Il était le Sceau — et son portail lunaire est grand ouvert.",
        "Sur la Lune, le Déferlement gronde. Tenez 30 vagues.",
    ]

    def items(self):
        return [("survival", "Affronter le Déferlement"),
                ("menu", "Fuir (menu principal)")]

    def draw(self, screen):
        super().draw(screen)
        _w, h = screen.get_size()
        now = pygame.time.get_ticks()
        if self._opened_at is None:
            self._opened_at = now
        budget = int((now - self._opened_at) / 1000 * self.CHARS_PER_SECOND)
        font = self._font(h, small=True)
        max_width = self._panel_rect(screen).width - 36
        y = h // 5 + h // 12
        for line in self.LORE:
            shown = line[:max(0, budget)]
            budget -= len(line)
            if shown:
                surf = font.render(shown, True, (226, 176, 140))
                if surf.get_width() > max_width:
                    surf = pygame.transform.smoothscale(
                        surf, (max_width, surf.get_height()))
                rect = surf.get_rect(midleft=(
                    self._content_center_x(screen) - max_width // 2, y))
                screen.blit(surf, rect)
                if len(shown) < len(line):    # curseur de frappe
                    pygame.draw.rect(screen, DANGER_COLOR, (
                        rect.right + 3, rect.top + 3, max(3, h // 120), rect.height - 6))
            y += int(font.get_height() * 1.35)


class LevelCompleteScreen(MenuBase):
    """Transition entre deux niveaux : annonce le suivant + bilan chiffré."""

    menu_vertical_offset = 0.13

    def __init__(self, sounds, finished_index, next_name, stats=None):
        super().__init__(sounds)
        self.title = f"Niveau {finished_index + 1} terminé !"
        self.kicker = "// zone sécurisée"
        self.next_name = next_name
        self.stats_line = format_stats(stats)
        self.cards = stat_cards(stats)

    def items(self):
        return [("continue", "Continuer"), ("menu", "Menu principal")]

    def draw(self, screen):
        super().draw(screen)
        self._draw_info_blocks(screen, [
            (f"PROCHAINE ZONE : {self.next_name.upper()}", theme("warm")),
            ("Vous gardez vos armes et récupérez de la vie.", DIM_COLOR),
        ], self.cards)
