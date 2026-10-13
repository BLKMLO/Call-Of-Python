"""Nettoie les PNG d'ennemis mal découpés depuis leur planche d'origine.

Certaines frames contiennent des débris des frames voisines (une botte, un
bout de fusil) collés au bord de l'image, et un personnage décalé par
rapport à sa pose de repos. Ces débris gonflent `get_bounding_rect`, ce qui
décale aussi les yeux des variantes possédées.

Pour chaque `assets/enemy_*.png` (hors cadavres) :
1. supprime les composantes connexes (alpha >= 12, 8-voisinage) qui touchent
   le bord de l'image et ne sont pas la composante principale ;
2. recentre horizontalement la silhouette sur la pose de repos de la même
   vue (`idle`, `idle_back`, `idle_side`) si l'écart dépasse 3 px.

Usage : python tools/clean_sprites.py [--check]
`--check` n'écrit rien et sort en erreur si un fichier doit être corrigé.
"""

import argparse
import glob
import os
import sys

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET_DIR = os.path.join(ROOT, "assets")
MIN_ALPHA = 12
CENTER_TOLERANCE = 3


def components(surface):
    """Composantes connexes opaques : listes de pixels (x, y)."""
    mask = pygame.mask.from_surface(surface, MIN_ALPHA)
    width, height = mask.get_size()
    return [[(x, y) for y in range(height) for x in range(width) if part.get_at((x, y))]
            for part in mask.connected_components()]


def strip_edge_fragments(surface):
    """Efface les débris touchant le bord ; retourne le nombre de pixels."""
    width, height = surface.get_size()
    parts = sorted(components(surface), key=len, reverse=True)
    removed = 0
    for part in parts[1:]:
        if any(x in (0, width - 1) or y in (0, height - 1) for x, y in part):
            for point in part:
                surface.set_at(point, (0, 0, 0, 0))
            removed += len(part)
    return removed


def reference_name(name):
    """Pose de repos de la même vue que `name` (ou None)."""
    kind = name.split("_")[1]
    if name.endswith("_back"):
        view = "_back"
    elif name.endswith("_side"):
        view = "_side"
    else:
        view = ""
    reference = f"enemy_{kind}_idle{view}"
    return None if reference == name else reference


def recenter(surface, target_centerx):
    """Décale la silhouette pour aligner son centre ; retourne le décalage."""
    bounds = surface.get_bounding_rect(min_alpha=MIN_ALPHA)
    shift = target_centerx - bounds.centerx
    if abs(shift) <= CENTER_TOLERANCE:
        return 0
    shift = max(-bounds.x, min(surface.get_width() - bounds.right, shift))
    moved = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    moved.blit(surface, (shift, 0))
    surface.fill((0, 0, 0, 0))
    surface.blit(moved, (0, 0))
    return shift


def clean(write=True):
    changed = []
    paths = sorted(glob.glob(os.path.join(ASSET_DIR, "enemy_*.png")))
    names = [os.path.splitext(os.path.basename(p))[0] for p in paths]
    surfaces = {n: pygame.image.load(p) for n, p in zip(names, paths, strict=True)}
    # Les poses de repos d'abord : elles servent de référence aux autres.
    for name in sorted(names, key=lambda n: "_idle" not in n):
        if "_dead" in name:
            continue
        surface = surfaces[name]
        removed = strip_edge_fragments(surface)
        shift = 0
        reference = reference_name(name)
        if reference in surfaces:
            target = surfaces[reference].get_bounding_rect(min_alpha=MIN_ALPHA).centerx
            shift = recenter(surface, target)
        if removed or shift:
            changed.append((name, removed, shift))
            if write:
                pygame.image.save(surface, os.path.join(ASSET_DIR, name + ".png"))
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = clean(write=not args.check)
    for name, removed, shift in changed:
        print(f"{name}: {removed} px de débris retirés, décalage {shift:+d} px")
    if args.check and changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
