"""Le Déferlement — mode survie par vagues.

Histoire : le Colosse n'était pas le champion de la horde, il était le
Sceau qui la retenait. Sa mort ouvre les vannes : les ennemis déferlent
par les sas de l'arène, vague après vague, jusqu'à la 30e.

Règles :
- une vague est "terminée" quand tous ses ennemis sont morts ; la
  suivante arrive après un répit fixe de 7 secondes (le temps de
  recharger), avec un petit bonus de soin ;
- MAIS si la vague n'est pas nettoyée avant la submersion (30 secondes
  pour la 1ère vague, puis 3 % de moins à chaque nouvelle vague, soit
  ~12,4 s à la 30e ; planchers de sécurité 8 s pour les vagues 1-10, 6 s
  pour 11-20 et 4 s pour 21-30, non atteints à ce rythme), la suivante
  déferle quand même par-dessus : on peut être submergé ;
- les ennemis sortent tous du portail central puis s'en écartent ;
- les vagues grossissent et durcissent ; toutes les 10 vagues, un
  Colosse accompagne la horde ;
- les trousses de soins réapparaissent toutes les 3 vagues, les packs de
  vie complets toutes les 2 vagues, les armes au sol toutes les 5 vagues
  (de plus en plus améliorées) ;
- en solo, aucune amélioration ennemie (ni mutateur, ni élite) et une
  amélioration d'arme toutes les 2 vagues nettoyées ; en coopération LAN,
  mutateurs et élites restent actifs avec une amélioration toutes les 3 ;
- survivre à la vague 30 est la victoire ultime.
"""

import math
import random
from collections import deque

from difficulty import ThreatDirector, get_difficulty
from elites import apply_elite, apply_traits
from entities import ENEMY_TYPES
from game import Game
from level import SURVIVAL_LEVEL
from mutators import apply_mutator, composition, mutator_for_wave

FINAL_WAVE = 30                # dernière vague
WAVE_TIMEOUT_BASE = 30.0       # délai de submersion de la 1ère vague (s)
WAVE_FLOOR_START = 8.0         # plancher des vagues 1-10 (s)
WAVE_FLOOR_STEP = 2.0          # -2 s de plancher par tranche de 10 vagues
WAVE_FLOOR_MIN = 2.0           # plancher absolu (au-delà de la vague 40)
INTERMISSION = 4.0             # répit avant la toute première vague (s)
CLEAR_INTERMISSION = 7.0       # répit fixe après une vague nettoyée (s)
BOSS_EXTRA_TIME = 10.0         # délai de submersion en plus si un Colosse est dans la vague (s)
EMERGE_TIME = 0.6              # durée de la poussée de sortie du portail (s)
EMERGE_SPEED = 3.5             # vitesse de cette poussée (cases / s)
SPAWN_MAX_DISTANCE = 2.0       # apparition toujours à moins de 2 m du portail
SPAWN_PLAYER_CLEARANCE = 1.2   # distance minimale visée entre apparition et joueur
SPAWN_INTERVAL = 0.4           # étalement des apparitions dans une vague (s)
MAX_ALIVE = 24                 # ennemis simultanés (les autres attendent en file)
MAX_CORPSES = 60               # cadavres conservés au sol (rendu)
CLEAR_HEAL = 12                # PV rendus par vague nettoyée en Soldat (voir difficulty.py)
ALERT_PULSE = 2.5              # la horde re-flaire le joueur à cette fréquence (s)
UPGRADE_EVERY_SOLO = 2         # amélioration d'arme toutes les N vagues (solo)
UPGRADE_EVERY_COOP = 3         # idem en coopération LAN (inchangé)
SHIELD_FROM_WAVE = 7           # porte-boucliers à partir de cette vague
SHIELD_EVERY = 3               # un soldat sur trois porte un bouclier
SWARM_FROM_WAVE = 8            # essaims de kamikazes à partir de cette vague
SWARM_EVERY = 4                # ... une vague sur quatre (hors Colosse)


def swarm_size(wave, count_mult=1.0):
    """Kamikazes d'un essaim : 0 hors vagues d'essaim, sinon 3 + n // 6
    (4 à la vague 8, 7 à la 28), modulé par la difficulté."""
    if wave < SWARM_FROM_WAVE or wave % SWARM_EVERY or wave % 10 == 0:
        return 0
    return max(2, round((3 + wave // 6) * count_mult))


# Contrats : défis optionnels d'une vague, récompensés par une carte bonus.
# clé : (libellé, arme exigée, type d'ennemi ou None, objectif)
CONTRACTS = {
    "shotgun_kamikaze": ("Kamikazes au fusil à pompe", "shotgun", "kamikaze", 5),
    "pistol_heavy": ("Lourds au pistolet", "pistol", "heavy", 2),
    "rifle_sniper": ("Snipers au fusil d'assaut", "rifle", "sniper", 2),
    "grenade_any": ("Ennemis à la grenade", "grenade", None, 4),
    "pistol_any": ("Ennemis au pistolet", "pistol", None, 8),
    "shotgun_shield": ("Porte-boucliers au fusil à pompe", "shotgun", "shield", 2),
}
CONTRACT_FROM_WAVE = 2
CONTRACT_EVERY = 3     # vagues 2, 5, 8... (hors vagues du Colosse)


def pick_contract(wave, kinds, traits):
    """Contrat proposé à la vague `wave`, ou None. Déterministe (graine =
    numéro de vague) ; l'objectif est ramené au nombre de cibles prévues."""
    if (wave < CONTRACT_FROM_WAVE or (wave - CONTRACT_FROM_WAVE) % CONTRACT_EVERY
            or wave % 10 == 0):
        return None
    counts = {}
    for kind, trait in zip(kinds, traits, strict=True):
        counts[kind] = counts.get(kind, 0) + 1
        if trait == "shield":
            counts["shield"] = counts.get("shield", 0) + 1
    eligible = []
    for key, (_label, _weapon, target, goal) in sorted(CONTRACTS.items()):
        available = len(kinds) if target is None else counts.get(target, 0)
        if available >= 1:
            eligible.append((key, min(goal, available)))
    if not eligible:
        return None
    key, goal = random.Random(7919 * wave).choice(eligible)
    return {"key": key, "goal": goal, "progress": 0, "done": False}


def contract_line(row):
    """Ligne HUD d'un contrat répliqué `[clé, progrès, objectif, rempli]`."""
    if not row:
        return None
    key, progress, goal, done = row
    label = CONTRACTS[key][0]
    if done:
        return (f"CONTRAT REMPLI : {label} — carte bonus", (244, 196, 84))
    return (f"Contrat : {label} {progress}/{goal}", (238, 166, 75))


def valid_contract(row):
    return (isinstance(row, list) and len(row) == 4 and isinstance(row[0], str)
            and row[0] in CONTRACTS
            and all(type(v) is int for v in row[1:3])
            and 1 <= row[2] <= 64 and 0 <= row[1] <= row[2]
            and type(row[3]) is int and row[3] in (0, 1))


def wave_traits(kinds, wave):
    """Traits par ennemi : un soldat sur trois porte un bouclier dès la
    vague 7 (le minigun s'y casse les dents de face)."""
    traits = []
    soldiers = 0
    for kind in kinds:
        trait = ""
        if kind == "soldier" and wave >= SHIELD_FROM_WAVE:
            soldiers += 1
            if soldiers % SHIELD_EVERY == 0:
                trait = "shield"
        traits.append(trait)
    return traits


def wave_floor(wave):
    """Plancher du délai de submersion par tranche de 10 vagues :
    8 s (1-10), 6 s (11-20), 4 s (21-30), sans passer sous 2 s."""
    tier = max(0, wave - 1) // 10
    return max(WAVE_FLOOR_MIN, WAVE_FLOOR_START - WAVE_FLOOR_STEP * tier)


def wave_timeout(wave, difficulty="soldier"):
    """Délai de submersion de la vague `wave` (1-indexée) : 30 s pour la
    1ère, puis réduit à chaque vague selon la difficulté (-3 % Recrue,
    -6 % Soldat, -10 % Vétéran), borné par `wave_floor`."""
    decay = get_difficulty(difficulty).wave_timeout_decay
    return max(wave_floor(wave),
               WAVE_TIMEOUT_BASE * decay ** max(0, wave - 1))


def wave_composition(wave, count_mult=1.0):
    """Liste des types d'ennemis de la vague `wave` (1-indexée).

    Le bestiaire s'élargit avec les vagues : kamikazes dès la 3e,
    snipers dès la 6e, de plus en plus de lourds et de soldats.
    """
    # Le nombre d'ennemis suit la difficulté (×0,8 Recrue, ×1,25 Vétéran).
    count = max(3, round(min(4 + math.ceil(wave * 0.6), 20) * count_mult))
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


def _spawn_radius(kind):
    """Rayon de collision du type `kind` (le Colosse est plus large)."""
    return ENEMY_TYPES[kind].RADIUS


def wave_multipliers(wave):
    """(vie, dégâts) des ennemis de la vague : montée progressive."""
    return 1.0 + wave * 0.03, 1.0 + wave * 0.025


class SurvivalGame(Game):
    """Un `Game` sur l'arène du Déferlement, piloté par les vagues."""

    # Solo : ennemis sans mutateur ni élite, améliorations plus fréquentes.
    # `CoopHostGame` repasse à False pour garder la difficulté LAN.
    SOLO = True

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
        self.mutator = ""
        self.wave_timer = 0.0          # chrono de submersion de la vague
        # Délai de submersion de la vague en cours (dépend de la difficulté).
        self.wave_limit = wave_timeout(1, self.difficulty.key)
        self.intermission = INTERMISSION
        self.spawn_queue = deque()     # types d'ennemis en attente
        self.spawn_cooldown = 0.0
        self.alert_pulse = 0.0
        self.director = ThreatDirector(
            getattr(settings, "difficulty", "soldier"),
        )
        self.contract = None           # défi optionnel de la vague en cours

    def spawn_enemy(self, kind, x, y, hp_mult=1.0, dmg_mult=1.0):
        """Tous les envahisseurs lunaires sont des variantes possédées."""
        return super().spawn_enemy(
            kind, x, y, hp_mult, dmg_mult, possessed=True,
        )

    # ------------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        if self.paused or self.outcome is not None:
            return
        self._update_emergence(dt)
        self._update_waves(dt)

    def _update_emergence(self, dt):
        """Poussée de sortie : chaque nouvel ennemi s'écarte vite du portail."""
        for enemy in self.enemies:
            emerge = getattr(enemy, "emerge", None)
            if not emerge or not enemy.alive:
                continue
            dx, dy, remaining = emerge
            step = EMERGE_SPEED * min(dt, remaining)
            enemy.x, enemy.y = self.level.move_with_collisions(
                enemy.x, enemy.y, dx * step, dy * step, enemy.RADIUS)
            remaining -= dt
            enemy.emerge = (dx, dy, remaining) if remaining > 0.0 else None

    def _check_outcome(self):
        """Pas de victoire "tous morts" ici : seule la vague 30 libère."""
        if not self.player.alive:
            self.outcome = "dead"

    # ------------------------------------------------------------------
    # Vagues
    # ------------------------------------------------------------------
    def _update_waves(self, dt):
        alive_ratio = sum(e.alive for e in self.enemies) / MAX_ALIVE
        health_ratio = self.player.health / max(1, self.player.max_health)
        self.director.observe(health_ratio, alive_ratio)
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
            self.score.award(f"wave:{self.wave}", 200)
            if self.wave >= FINAL_WAVE:
                self.outcome = "victory"     # le Déferlement est brisé
                self.sounds.play("level_complete")
            else:
                # Vague nettoyée à temps : répit fixe pour recharger. Une
                # vague non nettoyée n'en a pas : la suivante déferle à la
                # submersion, par-dessus les survivants.
                self.player.health = min(self.player.max_health,
                                         self.player.health + self.difficulty.clear_heal)
                self.intermission = CLEAR_INTERMISSION
                every = UPGRADE_EVERY_SOLO if self.SOLO else UPGRADE_EVERY_COOP
                if self.wave % every == 0:
                    self._award_upgrades(f"wave:{self.wave}")
                self.sounds.play("heal", volume_scale=0.7)
        elif self.wave_timer >= self.wave_limit and self.wave < FINAL_WAVE:
            # Submersion : la vague suivante déferle par-dessus.
            self._start_wave(self.wave + 1)

    def _start_wave(self, number):
        self.wave = number
        self.wave_timer = 0.0
        self.intermission = 0.0
        self.mutator = "" if self.SOLO else mutator_for_wave(number)
        kinds = composition(wave_composition(number, self.difficulty.enemy_count),
                            self.mutator)
        if number % 10 == 5:
            kinds[0] = "commander"
        # Le Colosse est long à abattre : temps de nettoyage supplémentaire.
        self.wave_limit = wave_timeout(number, self.difficulty.key) + (
            BOSS_EXTRA_TIME if "boss" in kinds else 0.0)
        elites = not self.SOLO and number >= 4
        traits = wave_traits(kinds, number)
        self.spawn_queue.extend((kind, number, self.mutator,
                                 ("bulwark" if i == 1 else "hunter")
                                 if elites and i in (1, 3) else "", traits[i])
                                for i, kind in enumerate(kinds))
        swarm = swarm_size(number, self.difficulty.enemy_count)
        self.spawn_queue.extend(("kamikaze", number, self.mutator, "", "swarm")
                                for _ in range(swarm))
        self.contract = pick_contract(number, list(kinds) + ["kamikaze"] * swarm,
                                      traits + ["swarm"] * swarm)
        self.sounds.play("wave", volume_scale=0.9)
        self.hud.announce(f"VAGUE {number}")
        if swarm:
            self.hud.show_message("Essaim de kamikazes en approche !")
        self._refresh_pickups(number)

    def _refresh_pickups(self, wave):
        """Ravitaillement périodique : soins et armes réapparaissent."""
        for pickup in self.pickups:
            if pickup.dynamic:
                continue  # les cadeaux du Colosse ne se régénèrent pas
            if pickup.kind == "medkit":
                if wave % 3 == 0:
                    pickup.taken = False
            elif pickup.kind == "lifepack":
                if wave % self.difficulty.lifepack_every == 0:
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
        entry = self.spawn_queue.popleft()
        if not isinstance(entry, tuple):
            entry = (entry, self.wave, "", "")
        kind, wave, mutator, elite = entry[:4]
        traits = entry[4] if len(entry) > 4 else ""
        x, y, angle = self._pick_spawn_point(_spawn_radius(kind))
        hp_mult, dmg_mult = wave_multipliers(wave)
        enemy = self.spawn_enemy(kind, x, y, hp_mult, dmg_mult)
        enemy.angle = angle
        enemy.emerge = (math.cos(angle), math.sin(angle), EMERGE_TIME)
        apply_mutator(enemy, mutator)
        apply_traits(enemy, traits)
        if sum(e.alive and bool(e.elite) for e in self.enemies) < 3:
            apply_elite(enemy, elite)
        # Il surgit en chasse, pas en patrouille.
        self.ais[-1].alert((self.player.x, self.player.y))
        self.particles.spawn_portal(*self._portal_center())
        self.sounds.play("spawn", volume_scale=0.8,
                         pos=(enemy.x, enemy.y), listener=self.player)
        self.spawn_cooldown = self.director.interval(SPAWN_INTERVAL)
        self._prune_corpses()

    def _portal_center(self):
        return self.level.config.get("portal") or self.level.horde_spawns[0]

    def _pick_spawn_point(self, radius=0.3):
        """Bouche du portail : (x, y, direction de sortie).

        Le portail occupe une case bloquante ; l'ennemi apparaît juste à
        son bord, dans une direction libre tirée au hasard (de préférence
        loin des joueurs), à moins de `SPAWN_MAX_DISTANCE` du centre. Il
        s'en écarte ensuite (`emerge`).
        """
        cx, cy = self._portal_center()
        players = [p for p in self._all_players() if p.alive]
        start = random.uniform(0.0, 2 * math.pi)
        for distance in (0.55 + radius, 0.85 + radius, 1.2 + radius):
            free = []
            for step in range(16):
                angle = start + step * math.pi / 8
                x = cx + math.cos(angle) * distance
                y = cy + math.sin(angle) * distance
                if self.level.can_stand(x, y, radius):
                    gap = min((math.hypot(x - p.x, y - p.y) for p in players),
                              default=math.inf)
                    free.append((gap, x, y, angle))
            if free:
                # Jamais sur un joueur collé au portail : on sort par le côté
                # dégagé, au hasard parmi les bouches assez éloignées.
                clear = [spot for spot in free if spot[0] >= SPAWN_PLAYER_CLEARANCE]
                _gap, x, y, angle = (random.choice(clear) if clear
                                     else max(free, key=lambda spot: spot[0]))
                return x, y, angle
        # Arène modifiée sans place autour du portail : ancien sas le plus proche.
        x, y = min(self.level.horde_spawns,
                   key=lambda s: math.hypot(s[0] - cx, s[1] - cy))
        return x, y, math.atan2(y - cy, x - cx)

    def _prune_corpses(self):
        """Limite le nombre de cadavres au sol (rendu et mémoire)."""
        dead = sum(1 for e in self.enemies if not e.alive)
        excess = dead - MAX_CORPSES
        if excess <= 0:
            return
        kept_e, kept_a = [], []
        for enemy, ai in zip(self.enemies, self.ais, strict=True):
            if not enemy.alive and excess > 0:
                excess -= 1
                continue        # les plus anciens cadavres disparaissent
            kept_e.append(enemy)
            kept_a.append(ai)
        self.enemies, self.ais = kept_e, kept_a

    # ------------------------------------------------------------------
    # Contrats
    # ------------------------------------------------------------------
    def _credit_kill(self, enemy, weapon_id):
        contract = self.contract
        if contract is None or contract["done"]:
            return
        _label, weapon, target, _goal = CONTRACTS[contract["key"]]
        if weapon != weapon_id:
            return
        if target == "shield":
            if not enemy.shielded:
                return
        elif target is not None and enemy.KIND != target:
            return
        contract["progress"] = min(contract["goal"], contract["progress"] + 1)
        if contract["progress"] >= contract["goal"]:
            contract["done"] = True
            self.hud.announce("CONTRAT REMPLI")
            self.sounds.play("heal", volume_scale=0.8)
            self._award_upgrades(f"contract:{self.wave}")

    def _contract_row(self):
        contract = self.contract
        if contract is None:
            return None
        return [contract["key"], contract["progress"], contract["goal"],
                int(contract["done"])]

    def _status_lines(self):
        line = contract_line(self._contract_row())
        return super()._status_lines() + ([line] if line else [])

    # ------------------------------------------------------------------
    def survival_info(self):
        """Infos affichées par le HUD pendant le Déferlement."""
        remaining = (sum(1 for e in self.enemies if e.alive)
                     + len(self.spawn_queue))
        return {
            "wave": self.wave,
            "mutator": self.mutator,
            "final": FINAL_WAVE,
            "remaining": remaining,
            "next_in": (self.intermission if self.intermission > 0.0
                        else max(0.0, self.wave_limit - self.wave_timer)),
            "intermission": self.intermission > 0.0,
            "contract": self._contract_row(),
        }
