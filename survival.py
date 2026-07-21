"""Le Déferlement — mode survie par vagues.

Histoire : le Colosse n'était pas le champion de la horde, il était le
Sceau qui la retenait. Sa mort ouvre les vannes : les ennemis déferlent
par les sas de l'arène, vague après vague, jusqu'à la 50e.

Règles :
- une vague est "terminée" quand tous ses ennemis sont morts ; la
  suivante arrive après un court répit (et un petit bonus de soin) ;
- MAIS si la vague n'est pas nettoyée avant la submersion (30 secondes
  pour la 1ère vague, puis 10 % de moins à chaque nouvelle vague), la
  suivante déferle quand même par-dessus : on peut être submergé ;
- les vagues grossissent et durcissent ; toutes les 10 vagues, un
  Colosse accompagne la horde ;
- les trousses de soins réapparaissent toutes les 3 vagues, les packs de
  vie complets toutes les 2 vagues, les armes au sol toutes les 5 vagues
  (de plus en plus améliorées) ;
- survivre à la vague 50 est la victoire ultime.
"""

import math
import random
from collections import deque

from game import Game
from level import SURVIVAL_LEVEL

FINAL_WAVE = 30                # dernière vague
WAVE_TIMEOUT_BASE = 30.0       # délai de submersion de la 1ère vague (s)
WAVE_TIMEOUT_DECAY = 0.9       # -10 % de délai à chaque nouvelle vague
WAVE_TIMEOUT_MIN = 3.0         # plancher : reste jouable en fin de partie
INTERMISSION = 4.0             # répit entre deux vagues nettoyées (s)
SPAWN_INTERVAL = 0.4           # étalement des apparitions dans une vague (s)
MAX_ALIVE = 24                 # ennemis simultanés (les autres attendent en file)
MAX_CORPSES = 60               # cadavres conservés au sol (rendu)
CLEAR_HEAL = 12                # PV rendus quand une vague est nettoyée à temps
ALERT_PULSE = 2.5              # la horde re-flaire le joueur à cette fréquence (s)


def wave_timeout(wave):
    """Délai de submersion de la vague `wave` (1-indexée) : 30 s pour la
    1ère, réduit de 10 % à chaque vague suivante, avec un plancher."""
    return max(WAVE_TIMEOUT_MIN,
              WAVE_TIMEOUT_BASE * WAVE_TIMEOUT_DECAY ** max(0, wave - 1))


def wave_composition(wave):
    """Liste des types d'ennemis de la vague `wave` (1-indexée).

    Le bestiaire s'élargit avec les vagues : kamikazes dès la 3e,
    snipers dès la 6e, de plus en plus de lourds et de soldats.
    """
    count = min(4 + math.ceil(wave * 0.6), 20)
    kinds = []
    if wave % 10 == 0:          # un Colosse toutes les 10 vagues
        kinds.append("boss")
        count -= 3
    heavy_w = min(0.30, wave * 0.015)
    kamikaze_w = 0.0 if wave < 3 else min(0.18, 0.04 + wave * 0.006)
    sniper_w = 0.0 if wave < 6 else min(0.14, 0.03 + wave * 0.004)
    soldier_w = min(0.45, 0.10 + wave * 0.03)
    for _ in range(max(0, count)):
        roll = random.random()
        if roll < heavy_w:
            kinds.append("heavy")
        elif roll < heavy_w + kamikaze_w:
            kinds.append("kamikaze")
        elif roll < heavy_w + kamikaze_w + sniper_w:
            kinds.append("sniper")
        elif roll < heavy_w + kamikaze_w + sniper_w + soldier_w:
            kinds.append("soldier")
        else:
            kinds.append("grunt")
    return kinds


def wave_multipliers(wave):
    """(vie, dégâts) des ennemis de la vague : montée progressive."""
    return 1.0 + wave * 0.03, 1.0 + wave * 0.025


class SurvivalGame(Game):
    """Un `Game` sur l'arène du Déferlement, piloté par les vagues."""

    def __init__(self, screen, settings, sounds, carry_player=None):
        super().__init__(screen, settings, sounds, level_index=4,
                         carry_player=carry_player,
                         level_config=SURVIVAL_LEVEL)
        # Sans arsenal transmis (entrée par le menu) : équipement correct.
        if carry_player is None:
            self.player.add_weapon("shotgun", 1)
            self.player.add_weapon("rifle", 1)
            self.player.select_weapon(2)   # fusil d'assaut en main

        # Les armes au sol démarrent en Mk. II (elles montent avec les vagues).
        for pickup in self.pickups:
            if pickup.kind != "medkit":
                pickup.level_index = 1

        self.wave = 0
        self.wave_timer = 0.0          # chrono de submersion de la vague
        self.intermission = INTERMISSION
        self.spawn_queue = deque()     # types d'ennemis en attente
        self.spawn_cooldown = 0.0
        self.alert_pulse = 0.0

    # ------------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        if self.paused or self.outcome is not None:
            return
        self._update_waves(dt)

    def _check_outcome(self):
        """Pas de victoire "tous morts" ici : seule la vague 50 libère."""
        if not self.player.alive:
            self.outcome = "dead"

    # ------------------------------------------------------------------
    # Vagues
    # ------------------------------------------------------------------
    def _update_waves(self, dt):
        self._process_spawn_queue(dt)

        # La horde connaît toujours plus ou moins la position du joueur :
        # aucun ennemi ne reste planté au fond de l'arène.
        self.alert_pulse -= dt
        if self.alert_pulse <= 0.0:
            self.alert_pulse = ALERT_PULSE
            for ai in self.ais:
                if ai.enemy.alive and ai.enemy.ai_state == "idle":
                    ai.alert((self.player.x, self.player.y))

        if self.intermission > 0.0:
            self.intermission -= dt
            if self.intermission <= 0.0:
                self._start_wave(self.wave + 1)
            return

        self.wave_timer += dt
        cleared = not self.spawn_queue and all(
            not e.alive for e in self.enemies)
        if cleared:
            if self.wave >= FINAL_WAVE:
                self.outcome = "victory"     # le Déferlement est brisé
                self.sounds.play("level_complete")
            else:
                # Vague nettoyée à temps : répit + regain de vie.
                self.player.health = min(self.player.max_health,
                                         self.player.health + CLEAR_HEAL)
                self.intermission = INTERMISSION
                self.sounds.play("heal", volume_scale=0.7)
        elif self.wave_timer >= wave_timeout(self.wave) and self.wave < FINAL_WAVE:
            # Submersion : la vague suivante déferle par-dessus.
            self._start_wave(self.wave + 1)

    def _start_wave(self, number):
        self.wave = number
        self.wave_timer = 0.0
        self.intermission = 0.0
        self.spawn_queue.extend(wave_composition(number))
        self.sounds.play("wave", volume_scale=0.9)
        self.hud.announce(f"VAGUE {number}")
        self._refresh_pickups(number)

    def _refresh_pickups(self, wave):
        """Ravitaillement périodique : soins et armes réapparaissent."""
        for pickup in self.pickups:
            if pickup.kind == "medkit":
                if wave % 3 == 0:
                    pickup.taken = False
            elif pickup.kind == "lifepack":
                if wave % 2 == 0:
                    pickup.taken = False
            elif wave % 5 == 0:
                pickup.taken = False
                # armes de mieux en mieux : Mk II -> III -> IV
                pickup.level_index = min(3, 1 + wave // 12)

    # ------------------------------------------------------------------
    # Apparitions
    # ------------------------------------------------------------------
    def _process_spawn_queue(self, dt):
        self.spawn_cooldown -= dt
        if (not self.spawn_queue or self.spawn_cooldown > 0.0
                or sum(e.alive for e in self.enemies) >= MAX_ALIVE):
            return
        kind = self.spawn_queue.popleft()
        x, y = self._pick_spawn_point()
        hp_mult, dmg_mult = wave_multipliers(self.wave)
        enemy = self.spawn_enemy(kind, x, y, hp_mult, dmg_mult)
        # Il surgit en chasse, pas en patrouille.
        self.ais[-1].alert((self.player.x, self.player.y))
        self.particles.spawn_portal(enemy.x, enemy.y)
        self.sounds.play("spawn", volume_scale=0.8,
                         pos=(enemy.x, enemy.y), listener=self.player)
        self.spawn_cooldown = SPAWN_INTERVAL
        self._prune_corpses()

    def _pick_spawn_point(self):
        """Sas d'invasion le plus discret : loin du joueur, avec un peu
        d'aléatoire dans la case."""
        spawns = sorted(
            self.level.horde_spawns,
            key=lambda s: -math.hypot(s[0] - self.player.x,
                                      s[1] - self.player.y))
        # un des sas de la moitié la plus lointaine, au hasard
        x, y = random.choice(spawns[:max(1, len(spawns) // 2)])
        return (x + random.uniform(-0.25, 0.25),
                y + random.uniform(-0.25, 0.25))

    def _prune_corpses(self):
        """Limite le nombre de cadavres au sol (rendu et mémoire)."""
        dead = sum(1 for e in self.enemies if not e.alive)
        excess = dead - MAX_CORPSES
        if excess <= 0:
            return
        kept_e, kept_a = [], []
        for enemy, ai in zip(self.enemies, self.ais):
            if not enemy.alive and excess > 0:
                excess -= 1
                continue        # les plus anciens cadavres disparaissent
            kept_e.append(enemy)
            kept_a.append(ai)
        self.enemies, self.ais = kept_e, kept_a

    # ------------------------------------------------------------------
    def survival_info(self):
        """Infos affichées par le HUD pendant le Déferlement."""
        remaining = (sum(1 for e in self.enemies if e.alive)
                     + len(self.spawn_queue))
        return {
            "wave": self.wave,
            "final": FINAL_WAVE,
            "remaining": remaining,
            "next_in": (self.intermission if self.intermission > 0.0
                        else max(0.0, wave_timeout(self.wave) - self.wave_timer)),
            "intermission": self.intermission > 0.0,
        }
