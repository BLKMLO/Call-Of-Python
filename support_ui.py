"""Indicateurs coop compacts : secours et signaux, sans état de simulation."""

import math

import pygame

from mission_marker import MissionMarker


def ping_sprites(game):
    if not hasattr(game, "_ping_markers"):
        game._ping_markers = {}
    game._ping_markers = {pid: marker for pid, marker in game._ping_markers.items()
                          if pid in game.pings.markers}
    result = []
    for pid, (x, y, _timer) in game.pings.markers.items():
        marker = game._ping_markers.get(pid)
        if marker is None:
            marker = MissionMarker()
            marker.surface.fill((120, 190, 255), special_flags=pygame.BLEND_RGB_MULT)
            game._ping_markers[pid] = marker
        marker.x, marker.y = x, y
        result.append(marker)
    return result


def draw_support(screen, hud, player, pings, rescue=(), pid=0, key="E"):
    lines = []
    own = next((row for row in rescue if row[0] == pid), None)
    if own:
        if own[1] > 6:
            lines.append(f"Secours possible : {own[1] - 6:.0f} s · Réanimation {own[2]:.1f}/3 s")
        else:
            lines.append(f"Réapparition : {own[1]:.0f} s")
    elif rescue:
        target = rescue[0]
        lines.append(f"J{target[0] + 1} à terre : {key.upper()} / LB / ACT. près de l'allié")
        if target[2] > 0:
            lines.append(f"Secours {target[2]:.1f}/3 s · rester proche, Interagir pour annuler")
    if pings.markers:
        owner, (x, y, _) = next(reversed(pings.markers.items()))
        distance = math.hypot(x - player.x, y - player.y)
        bearing = ((math.atan2(y - player.y, x - player.x) - player.angle + math.pi)
                   % math.tau - math.pi)
        direction = "devant" if abs(bearing) < .35 else ("droite" if bearing > 0 else "gauche")
        lines.append(f"Signal J{owner + 1} · {distance:.0f} m · {direction}")
    baseline = screen.get_height() // 2 + 70 if own else 230
    for index, line in enumerate(lines):
        text = hud.small_font.render(line, True, (175, 222, 255))
        if text.get_width() > screen.get_width() - 32:
            text = pygame.transform.smoothscale(text, (screen.get_width() - 32, text.get_height()))
        screen.blit(text, (screen.get_width() // 2 - text.get_width() // 2, baseline + index * 22))
