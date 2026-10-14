# llm.md — Contexte projet unique (source de vérité)

> **Unique source de contexte pour toutes les IA** (Claude, GPT, Kimi,
> agents…). `CLAUDE.md`, `GPT.md`, `AGENTS.md` ne sont que des redirections
> vers ce fichier : ne jamais y remettre de contenu. Après chaque changement
> notable, mettre à jour **ce fichier et lui seul**.

## Projet

- FPS rétro Python 3.12 / pygame 2.6.1 (raycasting pseudo-3D façon
  Wolfenstein 3D). Repo `BLKMLO/Call-Of-Python` (ex-`TempGPT`).
- Version jeu **0.6.0**, protocole réseau **v5** (`version.py`). Les mentions
  « six choix », « deux niveaux par bonus », roulade 2,5 cases, protocole
  v3/v4 sont historiques.
- Contenu : campagne 5 niveaux (Entrepôt → Métropole → Gouvernement → Base
  militaire → Laboratoire, boss final « le Sceau » = Colosse) puis le
  **Déferlement** (survie par vagues sur la Lune, `FINAL_WAVE = 30`), coop LAN
  jusqu'à 4 joueurs. `README.md` documente le gameplay côté joueur ;
  `docs/gameplay.md`, `docs/gameplay-validation.md`, `docs/network-protocol.md`
  détaillent règles, preuves et protocole.

## Workflow et consignes utilisateur

- Branche par défaut `main` ; travailler sur `agent/<description>` et revenir
  par PR. Travail en cours : branche `agent/gameplay-evolution`, PR brouillon
  #29 (CI à consulter sur GitHub).
- Ne jamais annoncer une étape validée sans tests + recette. Conserver toutes
  les gates demandées par l'utilisateur. Rollback = réversion du commit.
- À chaque étape : mettre à jour README, CHANGELOG, architecture, doc réseau
  si nécessaire, et ce fichier.
- Pas de persistance/sauvegarde nouvelle sans demande ; les sauvegardes sont
  hors périmètre des passes gameplay.
- Historique Git : `main` contient le commit-pont `5a56c44` recréant l'arbre de
  `67949e2` (branche `backup/force-pushed-main-67949e2`). Ne jamais
  reconstruire cette filiation à la main ; `git diff --exit-code 67949e2
  5a56c44` doit rester vide.
- `settings.json` est gitignoré (normal qu'il apparaisse modifié).

## Lancer / tester

```bash
pip install -r requirements.txt
python main.py
UV_CACHE_DIR=/tmp/uv-cache uv run --python 3.12 --with pygame \
  python -m unittest discover -s tests -v
```

- `--python 3.12` obligatoire (pas de wheel pygame 2.6.1 pour Python plus
  récent). Tests en pilotes SDL factices (`SDL_VIDEODRIVER/SDL_AUDIODRIVER=dummy`).
- État actuel : **164 tests OK**, Ruff OK (règles E, F, I, UP, B dans
  `pyproject.toml`), couverture minimale 70 %.
- `tools/validate_gameplay.py --stage 10` (exécuté aussi en CI) : assertion à
  4 cartes, datagramme max observé 718 octets.
- `tools/clean_sprites.py` (+ `--check`, testé) : nettoyage des sprites.
- CI `.github/workflows/ci.yml` : PR vers `main`, push `main`, manuel ;
  Ubuntu + Windows, Python 3.12 : compilation, Ruff, tests, couverture, wheel.
  Actions épinglées par SHA, jeton `contents: read`. Workflow release : groupe
  `executables-${{ github.ref }}`.
- Packaging : `pyproject.toml`, licence MIT, wheel, PyInstaller.
- Fixtures de `tests/test_menu_controls.py` : vider `_FONT_CACHE` avant de
  fermer SDL. Port coop de test 15577 (≠ 5577 du jeu).
- Tests qui infligent des dégâts juste après `Game(...)`/`SurvivalGame(...)` :
  faire `player.shield = 0.0` d'abord (bouclier de spawn).
- Non validé automatiquement : ressenti en jeu réel, manette physique,
  tactile matériel, LAN multi-machines.

## Architecture

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée, machine à états (menu/jeu/Sceau/Déferlement/fin), musique, contrôleur manette des menus |
| `runtime.py` / `version.py` | `FixedStepClock` 60 Hz (rendu ≤120 Hz, ≤8 pas de rattrapage) ; versions jeu/protocole |
| `settings.py` | Paramètres + JSON (borné, atomique) |
| `menu.py` | Menus, paramètres, LAN, fins de niveau, game over/victoire |
| `game.py` | Boucle gameplay solo : entrées, hitscan, ramassages, portes, mission, caméra de mort |
| `survival.py` | Déferlement : vagues, submersion, apparitions, ravitaillement |
| `difficulty.py` | Profils Recrue/Soldat/Vétéran + directeur de pression (limité à la cadence) |
| `scoring.py` | Score commun autoritaire et grades |
| `upgrades.py` / `upgrade_ui.py` | Cartes d'amélioration et perks |
| `mutators.py` | Mutateurs de vagues (coop) |
| `elites.py` | Élites et Commandant |
| `boss_patterns.py` / `hazards.py` | Patterns du Colosse ; tracé au sol télégraphié |
| `grenades.py` | Grenades |
| `coop_support.py` / `support_ui.py` | Mise à terre, secours, pings |
| `mission_marker.py` | Balises d'objectifs (sans modifier les PNG) |
| `network.py` | UDP + JSON non bloquant, sans thread, défensif |
| `coop.py` | `CoopHostGame` (hérite `SurvivalGame`, hôte autoritaire) ; `CoopClientGame` (indépendant, init dupliquée) |
| `level.py` | Cartes ASCII, niveaux, portes coulissantes |
| `raycaster.py` | Murs texturés en couches (DDA + z-buffer), y-shearing, billboards, ciel, nuages, particules |
| `entities.py` | `Player`, `RemotePlayer`, ennemis, `Pickup`, `Prop` |
| `ai.py` | États idle/chase/attack/cover, BFS, flanc, couverture |
| `weapons.py` | Specs armes + niveaux Mk. II…IV |
| `hud.py` | Arme FP, viseur, minimap, barre de boss, écran de mort |
| `gamepad.py` / `touch_controls.py` | Manette SDL (Xbox/PS, zone morte, hot-plug, vibration) ; multi-touch |
| `particles.py`, `sounds.py`, `assets.py` | Particules 3D ; sons/musiques synthétisés + overrides ; PNG + générateurs de secours |

## Conventions et pièges (rendu / moteur)

- **Monde y-vers-le-bas** : angle 0 = est (+x), angle croissant = tourner à
  DROITE ; `dx` souris > 0 → droite. Chaîne entière cohérente (rendu, soleil,
  étoiles, stéréo, indicateurs de dégâts).
- **Cache mural** (`_wall_cache`) : FIFO borné (`CACHE_LIMIT`), éviction d'UNE
  entrée par insertion — jamais en bloc (pics ~200 ms). Variantes alpha des
  murs d'énergie sous clé `(*clé, alpha)`, alpha quantifié par 16 ; la surface
  opaque n'est JAMAIS mutée par `set_alpha`.
- **Cache billboards** (`_sprite_cache`) : LRU pondéré `get_pitch() *
  get_height()`, ≤ 64 Mio et ≤ 512 surfaces ; `_sprite_cache_bytes <=
  _sprite_cache_budget` toujours ; surface trop grosse rendue sans cache.
- **ADS** : `zoom_screen()` recadre/agrandit l'image rendue (blit avec `area`,
  tampon `_zoom_scratch` réutilisé) — ne jamais changer le FOV par frame.
- **`cast_ray_layers(..., max_height=...)`** traverse plusieurs murs, élague
  les masqués, s'arrête selon `Raycaster.max_height` (recalculé dans
  `set_level`). Tout niveau doit déclarer ses hauteurs dans `heights`. Le
  z-buffer utilise le PREMIER mur. Les tests différentiels de
  `tests/test_bugfix_perf.py` exigent des murs identiques après optimisation.
- `has_line_of_sight` : borné à `int(dist) + 2` croisements ; saute
  `first_cover_hit` si `cover_circles` vide.
- `raycaster.rotate_zoom_screen()` remplace `rotozoom` (glissade, mort) — ne
  pas revenir à `rotozoom`.
- **Billboards** : taille plafonnée par `MIN_SPRITE_DIST` (projection seule ;
  occlusion/tri = vraie distance). `entities._visible_bounds()` mémoïse
  `get_bounding_rect` par sprite.
- **Props** : bloquent déplacement/pathfinding, PAS balles ni ligne de vue.
  Dimensions physiques = boîte opaque via `_height_for_visible_width` (ne pas
  gonfler `SPRITE_HEIGHT`). Vérifier composantes connexes et marges avant de
  committer un décor. `prop_car` largeur monde 1,10 ; `prop_bench` (siège
  individuel) 0,46.
- **Portes** : uniquement dans des murs de hauteur 1,0, encadrées par des murs
  sur un axe.
- **Textures** : PNG détaillés dans `assets/` ; `python assets.py` ne complète
  que les absents, seul `--force-procedural` écrase. Fallbacks procéduraux
  (`_BUILDERS`, dont `enemy_sniper_aim`) jamais prioritaires sur un PNG.
- **Nuages** : panorama par niveau/résolution, 2 blits/frame ; désactivé si
  `stars` dans la config (Lune) ou `clouds: false`.
- **HUD** : `_text()` cache ≤ 512 (`TEXT_CACHE_LIMIT`), libellés statiques et
  compteurs bornés uniquement, jamais `set_alpha` sur une sortie. Vider dans
  `HUD.resize()` : polices, `_text_cache`, `_weapon_scale_cache`,
  `_reload_blend_cache`, `_reload_sprite_cache`. Minimap : base blittée,
  points dessinés à l'offset (10, 10), pas de `.copy()`.
- `TouchControls` compose l'habillage une fois par résolution
  (`_build_overlay()`).
- F3 affiche `Clock.get_fps()` de la boucle principale (ne pas le dériver du
  `dt` fixe).
- Caches à respecter : `_sysfont` (menu, durée process), `_FONT_CACHE`,
  `HUD._slot_icon_cache`.

## Entrées, menus, réglages

- `SLOT_SCANCODES` (touches 1-4 indépendantes AZERTY/QWERTY) ; molette gère
  `event.flipped`, horizontale ignorée ; `invert_mouse` inverse les DEUX axes.
- Menus : sélection par identifiant dans `MenuBase`, haut/bas, gauche/droite
  pour régler, Entrée/Espace/A valider, Échap/B retour ; séparateurs exclus ;
  B ne quitte pas depuis le menu principal. Boutons via
  `MenuBase._button_surface()`/`_button_contains()` : parallélogrammes,
  panneau latéral gauche, contour seulement au survol, collision polygonale
  (souris). Bascule `< valeur >` entre chevrons (`_bracket_split`, `_row_font`
  partagé). Listes compactes bornées : Retour visible à 800×600.
- Remappage clavier : ignore les boutons manette sauf B (annuler) ; ne jamais
  injecter de touches manette dans `Settings.bind_key`. Échap/F11 non
  remappables ; conflit = échange. Touches réservées F5–F8. Ancien `sprint`
  migré vers `roulade`.
- `reset_gameplay_input` (`gamepad.py`) purge souris/tactile/boutons/tirs
  clients en attente ; gâchettes à relâcher après pause/reprise/focus/
  ouverture de contrôleur. `main.py` ferme le contrôleur des menus avant
  d'ouvrir celui de la partie et le rouvre aux retours menu.
- `GamepadInput.consume_actions()` ne touche pas `_fire_was_held` (seul
  `update()` le possède, sinon semi-auto en rafale).
- Tactile : activation SDL (`get_num_devices`) ou premier `FINGERDOWN` ;
  événements souris `touch=True` ignorés ; tir maintenu = `_mouse_fire_held`
  (vraie souris) et `TouchControls.fire_held` — jamais l'état global SDL.
  Focus perdu et toute bascule pause/reprise libèrent doigts et boutons.
- En pause/après fin : recharge, changement d'arme, molette ignorés ; perte de
  focus = pause.
- `settings.py` : JSON ≤ 64 KiB, racine objet, nombres finis bornés, booléens
  stricts, progression plafonnée, IPv4 validée ; sauvegarde
  `settings.json.tmp` + `fsync` + `os.replace`. `sound_volume` (défaut 0,4) et
  `music_volume` indépendants ; ancienne clé `volume` initialise les deux,
  propriété `volume` = alias.

## Joueur

- **Glissade** (remplace la roulade ; noms `roll_*`, touche `roulade` (Maj),
  champs réseau `rt`/`rs` conservés) : `ROLL_DURATION = 0.8`, `ROLL_SPEED =
  7.5`, `SLIDE_DECEL = 0.5`, vitesse décroissante `slide_speed`, distance
  ≈ 4,5 cases. Direction ZQSD (avant par défaut). Pas de cooldown mais
  `start_roll()` refuse un redéclenchement pendant `rolling`.
- I-frames 0,08–0,38 s (`Player.roll_invulnerable` = autorité, `roll_invuln`
  reste 0). Perk `ghost_slide` → `slide_ghost` = toute la glissade (aussi sur
  `RemotePlayer`).
- Pendant la glissade : tir (`_player_fire`, auto, tirs distants hôte) et
  rotation autorisés ; ADS coupé ; grenade et interaction bloquées. Caméra
  `_player_roll_camera` : image remontée 4 %, inclinaison 3°. Libellés
  « GLISSADE » / « GLIS. ».
- Déplacement sous-échantillonné (jamais un grand pas collisionné).
  `Player.move(..., blockers=...)` collisionne contre ennemis/coéquipiers ;
  `_separate_enemies()` ; un joueur déjà chevauché peut s'éloigner.
- Toute évolution de la glissade doit maintenir ensemble : constantes
  `Player`, reprise `RemotePlayer`, clamp réseau `rt`, crédit
  anti-téléportation basé sur `ROLL_SPEED`, séquence `rs`.
- `Player.update()` met à jour toutes les armes (recharge d'arme rangée).
  Son de recharge joué sur R ET recharge auto (`game.py` + `coop.py`).
- Bouclier de spawn 3 s (`activate_shield`), aussi pour les coéquipiers.
- **Caméra de mort** : gameplay figé à `outcome == "dead"`, `death_time` tourne
  (~`DEATH_CAM_TIME`) avant `finished` (`end_delay` reste pour la victoire).
  `DEATH_SKIP_LOCK = 3.0` : aucune entrée ne passe avant ; A passe ensuite.
  Écran de mort entièrement précalculé dans `HUD.resize()` ; « LA MORT VOUS
  RETIENT... » avant déverrouillage. Start/B reprennent/quittent la pause ;
  HUD distingue « PAUSE HÔTE ».
- Recharge : 4 poses `fp_<id>_reload_1/_2/(rien)/_3.png` 192×144 alpha ;
  `RELOAD_KEYFRAMES` repos → _1 → _2 → _reload → _3 → repos ;
  `Weapon.reload_progress` ∈ [0,1] ; fondus quantifiés à 6 niveaux en cache,
  retour au repos sur les 18 % finaux ; repli `_reload` puis pose normale.
  Fusil : main droite arrière, main gauche charge par-dessous. Minigun : capot
  ouvert → bande présentée → calée → capot fermé.
- Ne pas modifier `WEAPON_SPECS` ni offrir de munitions via un bonus.

## Ennemis et IA

- `EnemyAI.update()` appelle `update_timers()` AVANT `moving = False` (sinon
  pas d'animation de marche). L'état `cover` est dans la chaîne d'états ; le
  contact kamikaze est un `if` indépendant après.
- `Enemy.cancel_aim()` sur TOUTES les transitions d'état (toute nouvelle
  transition aussi).
- Tactiques : `Soldier.FLANKS`, `Soldier`/`Sniper.USES_COVER` (grâce
  `LOSE_SIGHT_TIME`). `exposure_fraction()` ∈ [0,1] ;
  `ai.cover_adjusted_chance()` = `0.28 + 0.72 * exposure` (exposition 1 jamais
  pénalisée).
- **Grunt** : `SPEED = 2.55`, `FIRE_DELAY = 1.3`.
- **Sniper** : `AIM_DELAY = 0.5625` à genou (`enemy_sniper_aim.png`, toile 64×96,
  silhouette 44×74 au sol), puis `FIRE_DELAY = 2.3` APRÈS le tir. Perte de
  vue/cible/état/mort annule la visée. Dégâts −5 % (nerf).
- **Soldier** : `CAN_ROLL`, roulade latérale `ROLL_DURATION = 0.75`,
  `ROLL_SPEED = 2.8`, `ROLL_COOLDOWN = 3.0` (déclenchement à déclenchement),
  i-frames toute l'animation, frames `enemy_soldier_roll_0..2.png`.
  `hit_roll_request` consommé après résolution complète du coup (tous les
  plombs passent) ; retentative 0,35 s si trop étroit ; `proactive_roll_delay`
  0,6–1,8 s n'affecte pas `roll_cooldown`. Client borne un ancien `roll_timer`
  à `Soldier.ROLL_DURATION`.
- `Enemy.impact_type` : `flesh` (Grunt/Soldier/Sniper/Kamikaze), `armor`
  (Heavy/Boss), `possessed` prioritaire. Particules/sons distincts
  (`flesh_hit`, `armor_hit`, `possessed_hit`).
- **Possédés** : tous les ennemis de `SurvivalGame.spawn_enemy()`.
  `set_possessed()` AVANT la construction d'`EnemyAI`. Soldier possédé :
  `CAN_ROLL=False`, 72 % vitesse ; Grunt 82 %. `assets.get_possessed()` dérive
  aura/yeux en cache (même taille que la source).
- `Enemy.sprite_kind` évite de demander des PNG inexistants (Commandant).
- Tirs ennemis en vue frontale (grunt, soldier, heavy, boss, ally).

### Colosse (Boss)

- Trois phases par `health / max_health` (jamais PV bruts) : >66 %, 66–33 %,
  <33 % ; vitesse/cadence `(1.15, 0.72)`, `(1.28, 0.58)`, `(1.42, 0.46)`. Vie
  1650.
- Chaque seuil franchi → événement ; seul `Game` place un `lifepack`
  dynamique (`net_id`) sur un flanc ; placement impossible = remis en tête et
  retenté ; cadavres ignorés. Client : `sync_phase_from_health()` sans objet
  local. Ne pas casser ces packs 2/3 et 1/3.
- `boss_patterns.py` idle/warn/charge/recover : annonce 1,2 s, charge 0,65 s
  à 5,5 m/s, récupération 1,2 s, attente `4.5 − 0.5 × phase`. Cible verrouillée
  à l'annonce ; phase ≥ 2 alterne charge et frappe rayon 1,8 m. Dégâts 24
  (charge) / 28 (frappe) avant difficulté, une fois par victime ; murs
  arrêtent la charge, pas de dégâts à travers les murs. IA standard suspendue
  pendant les patterns. Réplication `en[15]`, aucune simulation client.
  `hazards.py` : tracé au sol avec z-buffer, avant ADS.
- Boss final du Déferlement : conception seule (`docs/boss-final-deferlement.md`) ;
  un test vérifie qu'aucun `FinalBoss` n'est codé.

### Élites et Commandant (`elites.py`)

- Bulwark : +35 % PV, vitesse ×0,9. Hunter : vitesse ×1,15, délai de tir ×0,9.
  Max 3 élites vivantes ; boss et Commandant exclus.
- Commandant : 220 PV, aura portée 5 avec visibilité, délai de tir allié ×0,8
  sans cumul, retiré à sa mort ; un seul vivant (second spawn → soldat).
- Entrepôt : deux ennemis existants élites + dernier ennemi Commandant.
- Champs `en[13:15]` visuels, santé max autoritaire.

## Niveaux

- **Entrepôt** (mission) : manifeste (25,5 ; 18,5), alarme (24,5 ; 3,5),
  extraction au spawn (1,5 ; 1,5), rayon 1,4, maintien 8 s consécutives.
  `Game.mission` ; autres niveaux = élimination. Interaction E/remappable, LB,
  tactile ACT (portée/ligne de vue/vie/glissade contrôlées ; pause/outcome
  bloquent). HUD mission à y=160. Arsenal initial Entrepôt LAN : pistolet.
- **Laboratoire** : sol résine blanche, textures `wall_lab_tech/metal/
  reinforced` ; murs 1, 2, 4 à 1,0, enceinte `3` du Colosse à 1,55.
  `wall_sealed_portal` (`4`) en `(28, 18)` — pas `(28, 19)` (masqué par le
  boss en `(25, 19)`).
- **Lune** (`MAP_MOON`) : cristaux `k`/`prop_alien_crystal` (96×112, largeur
  0,88) bloquent la case + balles/perception par cercle rayon 0,46 —
  `PROP_CHARS`, `cover_circles`, ligne de vue, hitscan cohérents ensemble.
  Cratères précalculés (min 30, espacement 38 px). Portail : 4 frames
  `prop_portal_0..3.png` 79×117 (boîte opaque 71×108 en (4,2)), 110 ms/frame,
  anneau fermé sans support, `v_offset` ~0,11, jamais retourné selon la
  parité ; animations de props locales, jamais répliquées.
- Fond de menu lunaire 1280×720 (panneau sur le tiers gauche).

## Déferlement (`survival.py`)

- `SurvivalGame.SOLO = True`, `CoopHostGame.SOLO = False`. Solo : aucun
  mutateur (`self.mutator = ""`), aucune élite. Conservés partout : Commandant
  vagues 5/15/25, Colosses 10/20/30, `wave_multipliers` (vie +3 %/vague,
  dégâts +2,5 %/vague). Le test de submersion force `game.SOLO = False`.
- `wave_timeout = max(wave_floor, 30 × 0.99^(n-1))` (−1 %/vague, demande
  utilisateur du 14/10, remplace −10 %) : 22,42 s à la vague 30. `wave_floor`
  = 8 s (1–10), 6 s (11–20), 4 s (21–30), minimum 2 s, n'est plus atteint. Vague avec `"boss"` :
  +`BOSS_EXTRA_TIME` (10 s, demande utilisateur). Délai effectif dans
  `self.wave_limit`.
- Vague nettoyée : `intermission = CLEAR_INTERMISSION` (7 s fixes, demande
  utilisateur). Non nettoyée : pas de répit, la suivante démarre par-dessus
  les survivants. `INTERMISSION = 4` seulement avant la vague 1.
- Packs de vie toutes les 2 vagues.
- **Apparitions** : `_pick_spawn_point(radius)` → `(x, y, angle)` à la bouche
  du portail (`level.config["portal"]`, case bloquante) : distances
  0,55/0,85/1,2 + rayon, 16 directions, `can_stand`, < `SPAWN_MAX_DISTANCE`
  (2 m) ; hasard parmi les bouches ≥ `SPAWN_PLAYER_CLEARANCE` (1,2 m) de tout
  joueur vivant, sinon la plus éloignée. Puis `enemy.emerge`
  (`EMERGE_SPEED` 3,5 × `EMERGE_TIME` 0,6 s = 2,1 m). Cases `S` = repli.
- `spawn_queue` est un `deque` (`extend`/`popleft`, jamais `pop(0)`) ; entrées
  `(kind, wave, mutator, elite)`, effets d'origine conservés en submersion.
- **Mutateurs** (coop seulement) : rapid (vitesse +15 %), armored (vie +20 %,
  vitesse −10 %), crossfire (miliciens d'indice multiple de 4 → soldats).
  Rotation par groupes de 3 vagues dès 4, graine 101 ; 10/20/30 neutres ;
  aucun boss modifié, aucun ennemi ajouté. `wv.mutator` répliqué ; annonce HUD
  à y=195 (y=160 sous 1000 px de large). Coop : deux candidats élites dès 4.

## Améliorations (`upgrades.py`)

- Plus de `MAX_CHOICES` ; plafond par bonus `CAPS`. Effets par niveau :
  dégâts +10 %, recharge −15 %, capacité +20 %, dispersion −20 %, cadence
  +8 % (arrondis entiers dégâts/capacité). Specs par arme dérivées de façon
  idempotente, ratio de rechargement conservé.
- Offre (`valid_offers`) = `rng.sample` de 3 `WEAPON_UPGRADES` + 1 `PERKS` en
  dernière position. Perks : `grenade` (+1 max et plein, `grenade_capacity`,
  `MAX_GRENADES = 6`), `ghost_slide`, `vitality` (+20 PV max et rendus),
  `momentum` (+25 % `slide_boost`).
- `apply_player` idempotent (`vitality_applied`, `grenade_applied`, copiés au
  changement de niveau), renvoie les niveaux d'Artificier gagnés →
  `Game._apply_upgrades` / `CoopHostGame._apply_client_upgrades` remplissent
  les grenades.
- Cadence : toutes les `UPGRADE_EVERY_SOLO = 2` vagues nettoyées en solo,
  `UPGRADE_EVERY_COOP = 3` en coop ; aussi après interactions Entrepôt.
  Dédupliquées par token ; file si une offre est ouverte. Tokens de
  ravitaillement grenade séparés (déduplication bornée).
- Graine isolée 101 (solo), 101+pid (clients). Délai 12 s, choix 1 par défaut,
  figé par pause hôte. UI : 4 cartes, F5–F8, croix gauche/haut/droite/bas,
  clic, tactile ; perk bordé d'ambre. `uc`/`ub` portent les choix autoritaires.
- Contexte conservé entre niveaux, jamais sur nouvelle partie ; pas de
  persistance.

## Grenades (`grenades.py`)

- G/remappable, clic stick droit, tactile FRAG. 2 charges de base (max 6 via
  perk), cooldown 1 s, fusée 2 s, rayon 2,7, dégâts décroissants 90→31
  (ennemis), 60→21 (lanceur), alliés exempts. Collision pas ≤ 0,08 m, rebond
  amorti, souffle avec ligne de vue. 8 projectiles max. Aucune explosion
  simulée côté client. `gr`/`gm` acquittent (doublon = pas de dépense). Pause
  purge les demandes non acquittées et fige la fusée hôte. Explosions
  kamikazes inchangées.

## Score (`scoring.py`)

- Ennemi crédité une fois ; objectif +500 ; vague nettoyée +200 ; victoire
  +500 ; mise à terre −150 par transition ; secours +250 (4 premiers).
- Cible campagne = budget initial ennemis + objectifs + victoire ; cible
  Déferlement 20 000. Grades D/C/B à 0/25/50 %, A/S à 75/90 % avec victoire
  obligatoire. Cumul sur la campagne, grade par segment. `sc` réplique les 5
  champs ; PID stables.

## Coop LAN

- Hôte autoritaire, 4 joueurs max. `CoopHostGame(mission_mode=True)` utilise
  `Game.update` (Entrepôt), sinon `SurvivalGame.update`. `welcome.mode`
  configure le client. Fin Entrepôt LAN : retour LAN, pas de campagne solo ;
  fin LAN distincte des records de vagues.
- `CoopClientGame` duplique l'init de `Game` : tout nouveau champ
  `Player`/`Game.__init__` doit y être répliqué.
- Ne jamais simuler objectifs, patterns boss, explosions côté client. Les
  portes incluent les joueurs distants.
- **Mise à terre / secours** (`coop_support.py`) : 20 s de secours possible
  puis 6 s avant spawn (retour auto 60 PV). Tous à terre = défaite. Secours à
  ≤ 1,4 m, 3 s, nouvel appui annule ; dégât, glissade, perte de vue,
  éloignement annulent ; pas d'accélération multi-helpers ; tir bloqué ; retour
  40 PV + 2 s bouclier sans munitions. Pause hôte fige tout ; pause locale ou
  silence client > 350 ms annule. Ping C/remappable, Back/View, tactile SIG :
  portée 12 m (hôte), 5 s, délai 2 s, 4 marqueurs max.
- Réapparition : santé + glissade + cooldown + bouclier ensemble ; un
  instantané de mort annule d'abord bouclier/i-frames. `RemotePlayer.shield`
  simulé par l'hôte.

### Réseau / protocole

- Protocole strict (`version.py`, v5) : autre version → `incompatible`, aucun
  joueur créé. `session_id`, `iq` (entrées), `sq` (instantanés), événements
  fiables `rev` contigus acquittés par `ea`, journal borné 512, reprise `eb`.
  Ne jamais vider le journal après un envoi. `ix=[séquence,index]`, `ia`, `ms`,
  `rr`, `pg`, `ga`, `lp`, `uc`, `ub`, `gr`, `gm`, `sc` : voir
  `docs/network-protocol.md`. Purge des entrées = annule les interactions non
  acquittées.
- UDP : messages compressés (`Z1`, dès 900 o) puis fragmentés à 1 200 o ;
  décompression/réassemblage bornés (`BUFFER_SIZE`, TTL, débit), jamais de
  zlib incomplet/expansion illimitée. Budget 1 200 o contrôlé à chaque envoi.
  ≤ 128 datagrammes/frame, objets JSON uniquement.
- Sockets : pas de `SO_REUSEADDR` sur POSIX ; `SO_EXCLUSIVEADDRUSE` sous
  Windows.
- Valider AVANT d'indexer : pas de NaN/inf, lignes courtes, types inconnus,
  hors bornes ignorés. Aucune position/invincibilité/dégât/cadence décidée
  sans borne par le client.
- Tirs client : `[weapon_id, [angles...]]`, ≤ 32 par paquet, instances
  `Weapon` côté hôte ; `[angle, dégâts]` refusé.
- Déplacement distant : crédit alimenté par `net_time` (`Player.SPEED` ou
  `ROLL_SPEED`, ×ADS), capacité 0,15 s, marge 0,03 case. Glissade : `rs`
  strictement croissant (rejette les paquets retardés) ; ancien client sans
  `rs` : front `rt=0` → `rt>0`.
- Nouveaux champs TOUJOURS en fin de ligne ; tolérer les instantanés plus
  courts. Joueur : inventaire `[weapon_id, level]` + arme active en fin.
  Ennemi : `max_health`, `possessed`, `aiming`, etc. en fin. `pk` : booléens
  statiques d'abord puis lignes dynamiques `[id, x, y, kind, taken]` — jamais
  dict ni réordonnancement. Impacts : événement `["ei", net_id, fatal]`.
- Pause : `pa` répliqué ; l'hôte garde séquences/acks mais refuse position,
  angle, glissade, recharge, tir ; client `controls_paused`. Un client ne peut
  pas lever `host_paused`.

## Audio

- `assets/sound/` : `reload.<ext>`, `1..5.<ext>` (niveaux),
  `menu.<ext>`, `survival.<ext>` (Déferlement + coop) ; ordre
  `AUDIO_EXTENSIONS` (ogg, mp3, wav, flac). Committés : `1.mp3`…`5.mp3`,
  `survival.mp3` ; menu synthétisé.
- Sinon 7 `MUSIC_PROFILES` procéduraux déterministes (boucles 12 s sans clic).
- `play_music` ne garde qu'une piste fichier en cache (`file_music_keys`,
  `_release_file_music`, aussi au retour menu) ; nappes synthétisées en cache.

## Performances de référence

- 24 ennemis, SDL dummy : ~6 ms médiane à 800×600, ~10–11 ms à 1280×720
  (indicatif, pas une garantie matérielle).

## Dette / manques

- Pas de test LAN multi-machines, manette physique ni tactile matériel.
- numba évoqué, jamais implémenté (le cache FIFO a suffi).
- Ressenti en jeu réel de la glissade/cartes 0.6.0 non testé.
- Boss final du Déferlement non implémenté (conception seule).
