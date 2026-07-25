# LLM.md — Contexte projet Call of Python (unifié)

> Fusion condensée de `CLAUDE.md` et `GPT.md` (dernière source : 23 juillet 2026).
> **Ce fichier est la mémoire persistante du projet** : après chaque changement
> notable, le mettre à jour plutôt que compter sur la mémoire de conversation.

FPS rétro Python 3.12 / pygame (raycasting pseudo-3D façon Wolfenstein 3D).
Repo : `BLKMLO/Call-Of-Python` (renommé depuis `TempGPT`). Branches de travail
passées : `claude/python-fps-pygame-e1fouo`, `claude/call_of_python_LLM`.

## Lancer / tester

```bash
pip install -r requirements.txt
python main.py
```

34 tests dans `tests/` (`test_requested_changes.py` : 22 non-régressions
gameplay/graphiques ; `test_cleanup.py` : 12 contrôles robustesse/réseau) :

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --with pygame \
  python -m unittest discover -s tests -v
```

Smoke test possible avec `SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy`
(instancier `Game`/`SurvivalGame`/`CoopHostGame`/`CoopClientGame`, simuler des
frames, asserter des invariants — y compris une vraie socket UDP locale hôte↔client).

## Architecture (un fichier = un rôle)

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée, machine à états (menu / jeu / Sceau / Déferlement / fin), musique |
| `settings.py` | Paramètres + persistance JSON (bornée, atomique via `.tmp`+`os.replace`) |
| `menu.py` | Menus, paramètres, fins de niveau, game over / victoire |
| `game.py` | Boucle gameplay : entrées, tir hitscan, ramassages, portes, caméra de mort |
| `survival.py` | Le Déferlement : vagues, submersion dégressive, ravitaillement |
| `network.py` | LAN : UDP + JSON, non bloquant, sans thread, défensif (max 128 datagrammes/frame, objets JSON uniquement) |
| `coop.py` | Coop LAN : hôte autoritaire (`CoopHostGame` hérite `SurvivalGame`), client répliqué (`CoopClientGame`, init dupliquée — répliquer tout nouveau champ `Player`/`Game.__init__`) |
| `level.py` | Cartes ASCII + niveaux + portes coulissantes |
| `raycaster.py` | Rendu : murs texturés en couches (DDA + z-buffer), y-shearing, billboards, ciel, nuages |
| `entities.py` | `Player`, `Grunt`/`Soldier`/`Heavy`/`Sniper`/`Kamikaze`/`Boss`, `Pickup`, `Prop` |
| `ai.py` | États ennemis (idle/chase/attack/cover), BFS, flanc, couverture |
| `weapons.py` | Specs armes + niveaux Mk. II…IV |
| `hud.py` | Arme FP, viseur, minimap, barre de boss, écran de mort tactique |
| `particles.py`, `sounds.py`, `assets.py` | Particules 3D ; sons synthétisés (+ overrides `assets/sound/`) ; PNG + générateurs procéduraux de SECOURS |

## Invariants critiques (ne pas casser)

- **Monde y-vers-le-bas** : angle 0 = est, angle croissant = tourner à DROITE.
  Toute la chaîne (rendu, soleil, étoiles, stéréo) est cohérente (commit `984b279`).
- **Cache mural** : FIFO borné, éviction d'UNE entrée par insertion — jamais
  d'éviction en bloc (pics de lag ~200 ms).
- **ADS** : `zoom_screen()` recadre l'image rendue (post-traitement) — ne pas
  changer le FOV par frame (invalide le cache).
- **Murs en couches** (`cast_ray_layers`) : traverse plusieurs murs, n'élague que
  les entièrement masqués ; le z-buffer des sprites utilise le PREMIER mur.
- **Billboards** : taille plafonnée par `MIN_SPRITE_DIST` (projection seule ;
  occlusion/tri = vraie distance).
- **Props** : bloquent déplacement/pathfinding, PAS les balles ni la ligne de vue.
  Dimensions physiques = boîte opaque via `_height_for_visible_width` (ne pas
  compenser les marges transparentes).
- **Portes** : uniquement dans des murs de hauteur 1.0.
- **Textures** : PNG d'`assets/` refaits en art détaillé — ne JAMAIS relancer
  `python assets.py` (écraserait tout par le procédural). Vérifier composantes
  connexes et marges avant de committer un décor.
- **Roulade joueur** : 0,55 s à 4,55 cases/s, sans cooldown, mais fenêtre
  d'i-frames centrale de 0,30 s (0,08 s amorce + 0,17 s récupération vulnérables).
  `Player.roll_invulnerable` est l'autorité ; refus de redéclenchement pendant
  `rolling`. Déplacement sous-échantillonné (jamais un grand pas collisionné).
  Toute évolution doit maintenir ensemble : constantes `Player`, reprise dans
  `RemotePlayer`, clamp réseau `rt`, allocation anti-téléportation `ROLL_SPEED`,
  séquence `rs` (l'hôte rejette les datagrammes UDP retardés ; front `rt=0`→`rt>0`
  pour les anciens clients).
- **Roulade soldat** (`CAN_ROLL`) : 1,0 s à 2,8 cases/s, cooldown 3,0 s de
  déclenchement à déclenchement. `hit_roll_request` posé après résolution
  complète d'un coup (tous les plombs d'un fusil à pompe passent avant l'esquive).
- **Sniper** : `AIM_DELAY = 0,75 s` (télégraphie à genou, `enemy_sniper_aim.png`),
  puis `FIRE_DELAY = 2,3 s` APRÈS le tir. Toute perte de vue/cible annule la visée.
- **Couvert** : `cover_adjusted_chance()` = `0,28 + 0,72 * exposure` ; une
  exposition de 1,0 n'est jamais pénalisée. `exposure` bornée [0, 1].
- **Grunt** : `SPEED = 2,55` (+50 %), cadence inchangée `FIRE_DELAY = 1,3`.
- **Bouclier de spawn** (3 s, aussi pour les coéquipiers en coop) : les tests de
  dégâts doivent faire `player.shield = 0.0` d'abord.
- **Caméra de mort** : gameplay figé à `outcome == "dead"`, `death_time` tourne
  (~`DEATH_CAM_TIME`) avant `finished`. HUD préparé dans `HUD.resize()` ; vider
  `_weapon_scale_cache` dans `resize()`.
- **Cristaux lunaires** (`MAP_MOON`, `k`/`prop_alien_crystal`) : bloquent
  déplacement/pathfinding par la case ET balles/perception par un cercle rayon
  0,46 — `PROP_CHARS`, `cover_circles`, ligne de vue et hitscan doivent rester
  cohérents ensemble.
- **Portail lunaire** : 4 frames `prop_portal_0..3.png` (79x117, boîte opaque
  71x108 en (4,2)), anneau fermé sans support, vortex animé (110 ms/frame),
  `v_offset` ~0,11. Mur `wall_sealed_portal` en `(28,18)` de MAP_LAB (pas (28,19)).
  Animations de props = locales, jamais dans les instantanés coop.
- **Réseau** : UDP non fiable même en LAN — valider AVANT d'indexer (pas de
  NaN/inf, positions/dégâts/i-frames/cadence bornés côté hôte). Nouveaux champs
  ajoutés EN FIN de ligne, tolérance aux instantanés plus courts (7/8/9 champs).
  Tirs distants : ≤32 événements/paquet, 20 crédits/s (capacité 14), dégâts ≤
  Mk. IV, 0,18 rad autour de l'orientation. Réapparition = santé + roulade +
  cooldown + bouclier ensemble ; un instantané de mort annule d'abord bouclier/
  i-frames. `spawn_queue` = `deque` (`extend`/`popleft`, jamais `pop(0)`).
- **Settings** : JSON ≤ 64 KiB, types stricts, progression plafonnée, IPv4
  validée ; Échap/F11 non remappables ; conflit de touches = échange.
- **Divers** : `SLOT_SCANCODES` (AZERTY/QWERTY) ; molette `event.flipped` ;
  `invert_mouse` inverse les DEUX axes ; point de bascule des boutons `< valeur >`
  entre les chevrons (`MenuBase._bracket_split`) ; sprint supprimé (touche
  `roulade`, Maj par défaut, migration auto des anciens `settings.json`) ;
  `settings.json` est gitignoré (normal qu'il apparaisse modifié).

## Dette / manques

- Anciens smoke tests généraux (`smoke_test2..11.py`) jamais commités.
- numba évoqué, jamais implémenté (le cache FIFO a suffi).
- Multijoueur testé en UDP local seulement, pas multi-machines.

## Historique condensé (23 sessions)

1-3 : FPS complet, textures pixel-art, niveaux/armes progressifs.
4 : portes coulissantes, sprites directionnels, survie (boss = « le Sceau »).
5 : coop LAN, kamikaze/sniper, renommage **Call of Python**.
6-8 : optimisations ; campagne 5 niveaux + Déferlement lunaire ; ADS, cartes
agrandies. 9 : anti-lag (cache FIFO), soleil dynamique. 10-14 : polish, audit
souris, boutons de réglage, bouclier de spawn. 15 : sons personnalisés
(`assets/sound/`), IA tactique (flanc/couverture/exposition). 16 : Déferlement
(vie toutes les 2 vagues, submersion 30 s −10 %/vague plancher 3 s). 17 : caméra
de mort cinématique, Colosse ×3 (1650 PV), murs en couches. 18-19 : refonte
graphique complète (textures détaillées, F11, polices système) + nettoyage des
cadrages de props. 20 : sniper télégraphié, tirs ennemis frontaux, Laboratoire
blanc, nuages. 21 : roulades joueur/soldat, cristaux lunaires, portail flottant,
menu cinématique. 22 : robustesse (settings bornés/atomiques, UDP défensif,
validation hôte, 12 tests). 23 : équilibrage roulades (i-frames 0,30 s, cooldown
soldat 3 s), écran de mort tactique.
