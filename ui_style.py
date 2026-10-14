"""Rendu de texte « jeu vidéo » partagé par les menus et le HUD :
lettres espacées, ombre portée et halo flou, mis en cache."""

import pygame

STYLE_CACHE = {}
STYLE_LIMIT = 256


def tracked(font, text, color, spacing=0):
    """Texte avec espacement des lettres, comme les titres de jeux vidéo."""
    if spacing <= 0 or len(text) < 2:
        return font.render(text, True, color)
    glyphs = [font.render(ch, True, color) for ch in text]
    width = sum(g.get_width() for g in glyphs) + spacing * (len(glyphs) - 1)
    surface = pygame.Surface((max(1, width), font.get_height()), pygame.SRCALPHA)
    x = 0
    for glyph in glyphs:
        surface.blit(glyph, (x, 0))
        x += glyph.get_width() + spacing
    return surface


def tracked_width(font, text, spacing=0):
    return font.size(text)[0] + spacing * max(0, len(text) - 1)


def glow_surface(surface, color, radius):
    """Halo flou bon marché : silhouette teintée réduite puis agrandie."""
    radius = max(2, int(radius))
    w, h = surface.get_size()
    base = pygame.Surface((w + radius * 4, h + radius * 4), pygame.SRCALPHA)
    silhouette = pygame.mask.from_surface(surface).to_surface(
        setcolor=(*color, 255), unsetcolor=(0, 0, 0, 0))
    base.blit(silhouette, (radius * 2, radius * 2))
    size = base.get_size()
    for factor in (radius, max(2, radius // 2)):
        small = pygame.transform.smoothscale(
            base, (max(1, size[0] // factor), max(1, size[1] // factor)))
        base = pygame.transform.smoothscale(small, size)
    return base


def styled_text(font, text, color, spacing=0, glow=None, glow_radius=6,
                shadow=True):
    """Texte espacé + ombre portée + halo optionnel, mis en cache.

    Renvoie une surface dont le texte est centré : la blitter centrée sur
    le point voulu suffit (le halo déborde symétriquement)."""
    # La police elle-même (et non son id) sert de clé : elle reste vivante
    # tant que l'entrée existe, aucun id recyclé ne peut tomber dessus.
    key = (font, text, color, spacing, glow, glow_radius, shadow)
    cached = STYLE_CACHE.get(key)
    if cached is not None:
        return cached
    glyphs = tracked(font, text, color, spacing)
    pad = glow_radius * 2 if glow else 3
    surface = pygame.Surface(
        (glyphs.get_width() + pad * 2, glyphs.get_height() + pad * 2),
        pygame.SRCALPHA)
    if glow:
        surface.blit(glow_surface(glyphs, glow, glow_radius), (0, 0))
    if shadow:
        surface.blit(tracked(font, text, (0, 0, 0), spacing), (pad + 2, pad + 3))
    surface.blit(glyphs, (pad, pad))
    if len(STYLE_CACHE) >= STYLE_LIMIT:
        STYLE_CACHE.clear()
    STYLE_CACHE[key] = surface
    return surface
