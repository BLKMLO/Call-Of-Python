# llm.md — Contexte projet unique (source de vérité)

> **Ce fichier est l'unique source de contexte pour toutes les IA** (Claude,
> GPT, Kimi, agents, etc.) travaillant sur ce dépôt. Les anciens fichiers
> (`CLAUDE.md`, `GPT.md`, `AGENTS.md`) ne contiennent plus qu'une redirection
> vers ici.
>
> Règle de maintenance : après chaque changement notable, mettre à jour
> **ce fichier et lui seul**. Ne jamais remettre de contenu dans les fichiers
> d'origine, afin que toutes les IA partagent le même contexte et ne se
> contredisent pas.
>
> Consolidé le 25 juillet 2026 depuis : `CLAUDE.md`, `GPT.md`, `AGENTS.md`.

---

<!-- ====== Contenu consolidé depuis `CLAUDE.md` ====== -->

# Call of Python — contexte projet

> Pour les corrections les plus récentes et leurs invariants, voir la section
> « contexte de reprise GPT » plus bas.

FPS rétro en Python 3.12 / pygame (raycasting pseudo-3D façon Wolfenstein
3D), développé de bout en bout par itérations avec Claude Code. Ce fichier
résume l'état du projet pour reprendre le travail sans tout redécouvrir.

Repo GitHub : `BLKMLO/Call-Of-Python` (renommé depuis `BLKMLO/TempGPT`).
La branche par défaut est `main` ; les évolutions partent d'une branche
`agent/<description>` et reviennent par pull request.

## Lancer / tester

```bash
pip install -r requirements.txt
python main.py
```

La suite `unittest` est committée dans `tests/` et utilise les pilotes SDL
factices pour fonctionner sans écran ni carte son :

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --python 3.12 --with pygame \
  python -m unittest discover -s tests -v
```

Le workflow `.github/workflows/ci.yml` rejoue compilation, contrôles Ruff
critiques et les 81 tests sous Python 3.12 sur Ubuntu et Windows.

## Architecture

| Fichier        | Rôle |
|----------------|------|
| `main.py`      | Point d'entrée, machine à états (menu / jeu / Sceau / Déferlement / fin), musique |
| `settings.py`  | Paramètres + persistance JSON (résolution, volumes effets/musique, sensibilité, souris inversée, plein écran F11, touches, progression, records) |
| `menu.py`      | Menu principal, paramètres, fin de niveau, écran du Sceau, game over / victoire |
| `game.py`      | Boucle de gameplay : entrées, tir hitscan, ramassages, alertes, portes, stats, caméra de mort |
| `survival.py`  | Le Déferlement : vagues, délai de submersion dégressif, apparitions, ravitaillement |
| `network.py`   | Couche LAN : datagrammes UDP + JSON, sockets non bloquantes, sans thread |
| `coop.py`      | Coop LAN : hôte autoritaire (`CoopHostGame`) et client répliqué (`CoopClientGame`) |
| `level.py`     | Cartes ASCII + niveaux (thème, ennemis, armes, décors, difficulté) + portes coulissantes |
| `raycaster.py` | Rendu : murs texturés en couches (DDA + z-buffer), portes, y-shearing, billboards, ciel étoilé, particules |
| `entities.py`  | `Player` (arsenal, pitch, bouclier), `Grunt`/`Soldier`/`Heavy`/`Sniper`/`Kamikaze`/`Boss`, `Pickup`, `Prop` |
| `ai.py`        | Machine à états des ennemis (idle / chase / attack / cover) + pathfinding BFS + tactiques (flanc, couverture) |
| `weapons.py`   | Specs des armes + niveaux d'amélioration (Mk. II...) |
| `hud.py`       | Arme FP, viseur dynamique, marqueurs, panneau de vagues, minimap, barre de boss, écran de mort |
| `particles.py` | Particules 3D (sang, impacts, poussière, surgissements) |
| `sounds.py`    | Effets + sept thèmes contextuels synthétisés en pur Python (+ overrides fichiers réels dans `assets/sound/`) |
| `assets.py`    | Chargement des PNG (`assets/`) ; générateurs procéduraux de secours (`_BUILDERS`) si un PNG manque |

`README.md` documente le gameplay côté joueur en détail — s'y référer pour
la liste des features. Ce fichier se concentre sur les détails
d'implémentation et les décisions techniques non triviales.

## Conventions et pièges connus

- **Monde y-vers-le-bas** : angle 0 = est (+x), angle croissant = tourner
  à DROITE. `dx` souris positif → angle croissant → tourne à droite. Toute
  la chaîne (rendu, soleil, étoiles, son stéréo, indicateurs de dégâts) a
  été auditée et est cohérente — cf. commit `984b279`.
- **Cache mural** (`raycaster.py`) : FIFO borné (`CACHE_LIMIT`), éviction
  d'UNE seule entrée par insertion. Une éviction en bloc avait causé des
  pics de lag (~200ms) lors des rotations dans des zones à géométrie
  variée (rotonde du Gouvernement) — ne pas revenir à un cache généra-
  tionnel/bulk-évict.
- **Zoom de visée (ADS)** : `zoom_screen()` recadre + réagrandit l'image
  déjà rendue (post-traitement), plutôt que de changer le FOV — changer
  le FOV par frame invalidait tout le cache mural (gros pic de lag).
- **Rendu des murs en couches** (`cast_ray_layers`, ajouté récemment) : un
  raycaster classique s'arrête au premier mur et masque tout ce qui est
  derrière, y compris plus haut (un gratte-ciel derrière une salle basse
  disparaissait). La fonction traverse plusieurs murs et élague ceux qui
  sont entièrement masqués (ne garde que ceux qui dépassent au-dessus de
  tout ce qui est devant) pour rester aussi rapide qu'un rayon simple en
  zone dégagée. Le z-buffer (occlusion des sprites) utilise toujours le
  premier mur (le plus proche), pas les couches suivantes.
- **Taille des billboards** : plafonnée via une distance de projection
  plancher (`MIN_SPRITE_DIST`) pour éviter qu'un ennemi/décor grossisse à
  l'infini de très près — ne change pas l'occlusion/le tri (qui utilisent
  la vraie distance).
- **Props (décors)** bloquent les déplacements et le pathfinding IA mais
  PAS les balles ni les regards (`has_line_of_sight`/`cast_ray` ignorent
  `prop_tiles`) — seuls les murs de la grille bloquent la ligne de vue.
- **Portes** : ne doivent être placées que dans des murs de hauteur 1.0
  (jamais dans un mur "haut", sinon vide visuel au-dessus).
- **IA tactique** (`ai.py`) : hiérarchie par type d'ennemi.
  `Soldier.FLANKS=True` (contourne pour attaquer par le flanc/les
  arrières quand il perd le joueur de vue), `Soldier`/`Sniper.USES_COVER
  =True` (alterne planque/sortie "peek" pendant le combat, avec grâce de
  perte de vue via `LOSE_SIGHT_TIME` pour ne pas ressortir de l'état
  "attack" dès qu'il se planque). `exposure_fraction()`
  (`raycaster.py`) échantillonne la silhouette du joueur perpendiculai-
  rement à la ligne de tir pour réduire la précision ennemie quand il
  n'est que partiellement exposé (à couvert).
- **Scancodes** (`SLOT_SCANCODES` dans `game.py`) pour les touches 1-4 :
  indépendants de la disposition clavier (AZERTY/QWERTY).
- **Molette** : gère `event.flipped` (défilement "naturel" Linux/macOS) ;
  molette horizontale (`y=0`) ignorée.
- **Souris inversée** : un seul réglage (`settings.invert_mouse`) inverse
  les DEUX axes (horizontal ET vertical) en même temps.
- **Boutons de réglage `< valeur >`** (menu Paramètres) : le point de
  bascule gauche/droite se calcule entre les deux chevrons
  (`MenuBase._bracket_split`), PAS au centre du texte entier — un libellé
  à préfixe long (ex. "Sensibilité souris") décale sinon les deux
  chevrons du même côté du centre, rendant un des deux clics inopérant.
- **Bouclier de spawn** (`Player.activate_shield`) : invulnérabilité de
  quelques secondes à l'arrivée sur un niveau/le Déferlement. Les tests
  qui infligent des dégâts juste après un `Game(...)`/`SurvivalGame(...)`
  doivent faire `player.shield = 0.0` avant `take_damage`, sinon le
  dégât est silencieusement ignoré.
- **Caméra de mort** : `Game.update` fige tout le gameplay dès
  `outcome == "dead"` mais laisse tourner `death_time` (chute/bascule de
  vue + assombrissement + texte, ~`DEATH_CAM_TIME` secondes) avant que
  `finished` ne devienne vrai. Ne pas confondre avec l'ancien
  `end_delay` (toujours utilisé pour "victory").
- **Musique/son personnalisés** (`sounds.py`) : `assets/sound/` est
  optionnel. `reload.<ext>` remplace le clic synthétisé ; `<n>.<ext>`
  (n = numéro affiché du niveau, 1..5) ou `menu.<ext>`/`survival.<ext>`
  remplacent la nappe procédurale. Extensions essayées dans l'ordre
  `AUDIO_EXTENSIONS` (ogg, mp3, wav, flac). Sans fichier, chaque contexte
  utilise son propre `MusicProfile` (racine, tempo, motif et timbre) et une
  boucle déterministe de 12 secondes raccordée sans clic.
- **Coop LAN** : `CoopHostGame` hérite de `SurvivalGame` (hôte
  autoritaire) ; `CoopClientGame` est une classe indépendante qui expose
  la même interface (`handle_event`/`update`/`draw`/`finished`/`outcome`)
  mais duplique une partie de l'init (spawn du joueur, armes de départ,
  bouclier de spawn) plutôt que d'hériter de `Game` — à garder en tête si
  on ajoute un champ à `Player`/`Game.__init__` : il faudra le répliquer
  ici aussi.
- **Textures (refonte graphique)** : les PNG d'`assets/` ont été refaits
  à la main en art détaillé (via ChatGPT, branche `agent/refonte-graphique`),
  bien plus riches que les générateurs procéduraux d'`assets.py` — ces
  derniers ne servent plus que de secours si un PNG manque. Ne PAS relancer
  `python assets.py` (il écraserait les textures détaillées par les
  procédurales). Ajout au passage : polices système (`SysFont`), fond de
  menu (`assets/menu_background.png`), plein écran F11.
- **Cadrage des décors (`prop_*`)** : la refonte a découpé une planche de
  sprites aux mauvais décalages → certains décors contenaient des
  fragments d'objets voisins et/ou étaient tronqués. Nettoyés en ne
  gardant que la plus grande composante connexe puis en recadrant dessus.
  La voiture a depuis été régénérée avec un avant complet et des marges ; le
  banc du Gouvernement a été remplacé par un siège individuel plus compact.
  Vérifier composantes et marges avant de committer tout nouveau décor.

## Historique des sessions (dans l'ordre)

1. FPS complet : menu, paramètres, map de test, ZQSD + souris + tir, IA
   basique, vie/mort, code modulaire.
2. Textures pixel-art "Minecraft", plusieurs niveaux/armes progressives.
3. Passe d'amélioration libre.
4. Portes coulissantes, sprites directionnels, mode survie (vagues)
   après le boss — lore : le boss est "le Sceau".
5. Coop LAN, kamikaze/sniper, stats, renommage en **Call of Python**,
   packs de vie cachés.
6. Optimisation (FPS, textures, animations, particules, sons).
7. Campagne 5 niveaux (Entrepôt → Métropole → Gouvernement → Base
   militaire → Laboratoire) + Déferlement sur la Lune.
8. Fixes : gratte-ciel réellement hauts, visée clic droit (ADS), plus
   d'ennemis/armes, cartes agrandies/variées, Lune plate avec portail.
9. Fixes : bâtiments coupés, voiture bloquante, soleil dynamique
   (8h→19h), anti-lag (cache FIFO), préparation numba (jamais implémentée).
10. Passe libre + polish final (munitions, lueur de tir, cache mural).
11. Audit gauche/droite souris (Windows/Linux) : inversion du défilement
    des étoiles (seul vrai bug trouvé), molette `flipped`, mode relatif
    souris optionnel.
12. Option "souris inversée" dans les Paramètres.
13. Fix bouton de sensibilité (calcul du point de bascule), inversion
    souris étendue à l'axe vertical.
14. Bouclier temporaire au changement de niveau, ancien sprint Maj
    gauche/droite (remplacé depuis par la roulade).
15. Son de rechargement réel (fichier fourni), musiques de niveau
    personnalisables (`assets/sound/`), IA tactique (flanc, couverture,
    exposition partielle), nerf sniper (-5% dégâts).
16. Déferlement : packs de vie toutes les 2 vagues, délai de submersion
    dégressif (30s, -10%/vague, plancher 3s), plafond de taille des
    billboards de très près.
17. Caméra de mort cinématique (façon Dark Souls), vie du Colosse x3
    (550→1650), rendu des murs en couches (gratte-ciels visibles
    derrière les salles basses).
18. **Refonte graphique** (par ChatGPT, hors sessions Claude) : tous les
    PNG refaits en art détaillé, fond de menu, polices système, plein
    écran F11. Fusionnée dans `main`.
19. Correction du cadrage des décors régénérés : suppression des fragments
    parasites et des marges (plus grande composante connexe + recadrage),
    reconstruction temporaire du banc du Gouvernement tronqué (miroir).
20. Régénération définitive de la voiture et des sièges, suppression d'une
    porte isolée du Laboratoire, couvert renforcé et télégraphie du sniper à
    genou pendant 0,75 s (synchronisée en coop), tirs ennemis frontaux, murs
    blancs du Laboratoire et nuages hors niveau lunaire. Contexte dans la
    section « contexte de reprise GPT ».
21. Milicien accéléré de 50 %, roulades joueur/soldat avec i-frames et synchro
    coop, Lune texturée avec cristaux aliens de couverture, portail flottant
    et menu principal cinématique lunaire. Contexte complet dans la section
    « contexte de reprise GPT ».
22. Nettoyage de robustesse : réglages bornés et atomiques, entrées maladroites
    neutralisées, protocole UDP défensif, validation hôte des positions/
    roulades/tirs, boucliers de réapparition coop et caches légers. Dix tests
    dédiés dans `tests/test_cleanup.py`, invariants complets dans la section
    « contexte de reprise GPT ».
23. Équilibrage des roulades : fenêtre centrale de 0,30 s d'i-frames et aucun
    cooldown pour le joueur/les coéquipiers (séquences LAN anti-paquets
    retardés), soldat à 3 s de cooldown avec esquive réflexe après un impact
    sans annuler les plombs simultanés. Écran de mort refait en panneau
    tactique lisible et adaptatif. Contexte complet dans la section
    « contexte de reprise GPT ».
24. Passe libre Kimi (bugs, robustesse, perf, tests) : visée sniper annulée
    sur toutes les transitions d'état, rechargement auto audible, roulade
    gelée après victoire, textes « 50 vagues » alignés sur FINAL_WAVE=30,
    settings immunisés contre RecursionError, double bind UDP interdit sous
    Windows (SO_EXCLUSIVEADDRUSE), caches de polices/menu, icônes HUD,
    textes statiques, minimap sans copie, tampon de zoom ADS réutilisé,
    fondu des murs d'énergie mémoïsé (alpha quantifié), smoke tests enfin
    commités (`tests/test_smoke.py`). 43 tests verts. CHANGELOG.md créé.
25. Réparation de l'historique et lot gameplay/accessibilité : l'arbre du
    commit racine `67949e2` a été recréé à l'identique dans `5019052`, avec
    `ef9849d` comme parent, sur `agent/history-gameplay-repair`. Le Colosse
    passe à trois phases et libère deux packs de vie ; le Déferlement utilise
    des ennemis possédés ; Laboratoire, cratères et HUD sont recalibrés ; les
    commandes multi-touch sont activées par détection SDL. Sept tests dédiés
    portent la suite à 50 tests.
26. Passe post-fusion de fiabilité : packs de phase du Colosse différés au
    lieu d'être perdus en zone encombrée, cadavres exclus du placement,
    commandes tactiles maintenues neutralisées à la reprise, roulade coop
    interdite après l'issue et œil de profil possédé correctement miroir.
    Pygame est fixé à 2.6.1 et une CI GitHub Actions Linux/Windows automatise
    compilation, erreurs Python critiques et 54 tests.
27. Animations de recharge et identité audio : quatre poses détaillées
    `fp_<id>_reload` générées à partir des armes existantes, interpolation et
    mouvements propres dans le HUD, progression normalisée dans `Weapon`.
    Cinq thèmes de campagne, le Déferlement et le menu utilisent désormais
    sept profils musicaux procéduraux distincts. Six tests portent la suite à
    60 tests.
28. Impacts typés et mixage séparé : sang rouge/blessure sourde pour les
    organiques, éclats/choc métallique pour le lourd et le Colosse, sang vert/
    extinction pour tout possédé. Chaque impact est répliqué séparément en
    coop. Les volumes des effets et de la musique deviennent indépendants,
    avec migration de l'ancien volume global. Sept tests portent la suite à
    67 tests.
29. Corrections P0/P1 de l'audit : cache de billboards LRU limité à 64 Mio,
    protocole coop v2 séquencé et acquitté, compression UDP, inventaire
    autoritaire, validation complète des armes/cadences/munitions, pause hôte
    globale, budget de déplacement temporel et collisions joueurs/ennemis.
    Dix tests adversariaux portent la suite à 77 tests.
30. Équilibrage et polish UI : mise en joue du sniper réduite de 25 %
    (`0,75` → `0,5625 s`), roulade du militaire raccourcie de 25 %
    (`1,0` → `0,75 s`) avec portée et i-frames réduites ensemble, douze
    nouvelles poses portant chaque arme à quatre keyframes de recharge,
    boutons de menu latéraux en parallélogramme avec contour au survol et
    écran de mort verrouillé 3 s avec titre gothique sanglant. Quatre
    non-régressions supplémentaires portent la suite à 81 tests.

## Dette / manques à connaître

- **Couverture de tests encore partielle mais en progrès.** Quatre-vingt-un
  tests sont présents : `tests/test_requested_changes.py` (22
  non-régressions), `tests/test_cleanup.py` (15 contrôles robustesse/UI) et
  `tests/test_smoke.py` (8 tests de fumée généraux — boot, campagne,
  survie, menus, coop loopback UDP, réglages, sons), qui remplacent les
  anciens `smoke_test2..11.py` jamais commités, plus
  `tests/test_gameplay_extensions.py` (11 tests Colosse, possédés, décors,
  réseau étendu et tactile), `tests/test_reload_music.py` (8 tests sur les
  poses, le HUD, la progression de recharge et les profils musicaux) et
  `tests/test_impact_audio.py` (7 tests impacts, volumes, menu et coop), plus
  `tests/test_p0_p1.py` (10 tests de mémoire, protocole, sécurité hôte,
  collisions et pause coop).
- **Ruff complet** : 19 remarques stylistiques préexistantes restent ouvertes.
  La CI bloque uniquement les erreurs Python critiques (`E9`, `F63`, `F7`,
  `F82`) afin de ne pas rendre toutes les PR rouges pour cette dette connue.
- **numba** : évoqué comme piste d'optimisation si un jour nécessaire,
  jamais implémenté (le cache FIFO a suffi à éliminer les pics de lag
  observés).
- **Multijoueur** : handshake et instantanés testés avec une vraie socket UDP
  locale entre deux instances — toujours pas de test réseau multi-machines.
- `settings.json` est gitignoré (contient les préférences locales/l'IP
  du dernier hôte rejoint) — normal que `git status` le montre modifié
  après une partie.

---

<!-- ====== Contenu consolidé depuis `GPT.md` ====== -->

# Call of Python — contexte de reprise GPT

Dernière mise à jour : 29 juillet 2026. Dépôt `BLKMLO/Call-Of-Python`,
branche de travail `agent/reload-animations-level-music`.

## Corrections P0/P1 de robustesse

- `Raycaster._sprite_cache` est un LRU pondéré par la taille SDL réelle
  (`pitch × hauteur`), limité à `64 Mio` et `512` surfaces. Une surface plus
  grosse que le budget est rendue sans être conservée. Ne pas réutiliser la
  limite historique de `4000` entrées pour les billboards ; elle autorisait
  près de `940 Mio` de RSS supplémentaire dans le scénario d'audit.
  `_wall_cache` conserve en revanche son FIFO à éviction unique, car ses
  colonnes étroites et l'invariant anti-pic sont différents.
- Le protocole coop courant vaut `PROTOCOL_VERSION = 2`. Le handshake fournit
  un `session_id`; chaque entrée possède `iq`, chaque instantané `sq`, et le
  client rejette toute autre session ainsi que les séquences anciennes ou
  dupliquées. Les événements fiables `rev` portent leur propre numéro, restent
  dans un journal borné jusqu'à l'acquittement `ea`, et sont appliqués
  strictement dans l'ordre. `eb` permet une reprise bornée si un client dépasse
  exceptionnellement la fenêtre de `512` événements.
- La position de réapparition et la santé sont déjà dans la ligne joueur ;
  le client restaure donc aussi sa réapparition depuis cet état, sans dépendre
  du seul événement `rs`. Chaque ligne joueur ajoute en fin de tableau
  l'inventaire `[weapon_id, level]` et l'arme active : un événement `wpk` perdu
  ne supprime plus définitivement une arme. Les anciens lecteurs ignorent ces
  champs ajoutés en fin de ligne.
- Les instantanés v2 supérieurs à `1100` octets sont compressés par `UdpPeer`
  avec le préfixe `Z1`. La décompression est bornée à `BUFFER_SIZE`; ne jamais
  accepter un flux zlib non terminé, des données supplémentaires ou une
  expansion sans limite.
- Un tir client v2 est un déclenchement `[weapon_id, [angles...]]`. L'hôte
  possède ses propres instances `Weapon` et dérive chargeur, cadence, recharge,
  dégâts, rayon d'impact, dispersion et nombre exact de plombs. Les anciens
  couples `[angle, dégâts]` sont volontairement refusés : un ancien client
  peut lire les instantanés compatibles, mais doit être mis à jour pour tirer.
- Le déplacement distant consomme un crédit alimenté par `net_time`, à
  `Player.SPEED` hors roulade et `Player.ROLL_SPEED` pendant l'action, avec
  seulement `0,15 s` de capacité et `0,03` case de marge. Plusieurs paquets
  dans la même frame ne recréent aucun crédit. ADS applique aussi son
  multiplicateur de vitesse.
- `Player.move(..., blockers=...)` sous-échantillonne marche et roulade contre
  les cercles vivants. Le solo, l'hôte et la prédiction cliente passent leurs
  ennemis/coéquipiers comme obstacles ; `_separate_enemies()` résout aussi les
  chevauchements créés par l'IA. Un joueur déjà chevauché reste autorisé à
  s'éloigner.
- L'instantané réplique `pa`. `CoopHostGame._handle_input()` conserve
  séquences/acquittements pendant la pause mais refuse position, angle,
  roulade, recharge et tir. Le client utilise `controls_paused`, purge les
  actions maintenues et se recale sur la position hôte.
- `Player.update()` met à jour toutes les armes possédées : une recharge
  continue lorsque l'arme est rangée.

## Impacts typés et volumes séparés

- `Enemy.impact_type` vaut `flesh` pour `Grunt`, `Soldier`, `Sniper` et
  `Kamikaze`, `armor` pour `Heavy` et `Boss`, et toujours `possessed` lorsque
  `Enemy.possessed` est actif. Cette priorité garantit que les lourds et
  Colosses du Déferlement gardent l'identité alien verte.
- `ParticleSystem.spawn_impact()` produit une gerbe rouge, des fragments
  métalliques ou une gerbe verte. Le paramètre `fatal=True` augmente la gerbe
  sans mélanger les palettes ; `spawn_death()` accepte le même type.
- `SoundBank` expose `flesh_hit`, `armor_hit` et `possessed_hit`, synthétisés
  respectivement comme blessure sourde, résonance métallique et flamme
  étouffée. Les sons sont positionnels et atténués comme les anciens impacts.
- L'hôte coop ajoute un événement `["ei", net_id, fatal]` pour chaque balle
  encaissée. Le client supprime l'effet de repli fondé sur la variation de vie
  lorsqu'un tel événement existe, puis rejoue chaque événement séparément.
  Un hôte ancien reste compatible grâce au repli sur l'instantané de santé.
- `Settings.sound_volume` et `Settings.music_volume` sont indépendants.
  L'ancienne clé JSON `volume` initialise les deux valeurs ; la propriété
  `Settings.volume` reste un alias de compatibilité qui écrit les deux.

## Animations de recharge et musiques contextuelles

- Chaque arme dispose désormais de quatre poses de recharge réelles :
  `fp_<id>_reload_1.png`, `_reload_2.png`, `_reload.png` et `_reload_3.png`.
  Les douze nouvelles poses intermédiaires couvrent main d'appui, extraction,
  insertion, cartouche/pompe et bande d'alimentation. Tous les fichiers restent
  en `192x144`, avec alpha et coins transparents.
- `Weapon.reload_progress` expose une progression bornée `[0, 1]` uniquement
  pendant la recharge. `hud.reload_frames()` parcourt six points de passage
  (repos inclus aux deux extrémités), soit cinq transitions mécaniques ;
  `hud.reload_pose()` conserve les offsets propres à l'arme. Les fondus sont
  quantifiés sur six niveaux et toutes les poses/combinaisons sont mises en
  cache par résolution : aucune transformation d'image n'est effectuée à
  chaque frame. Une pose intermédiaire absente replie sur `_reload`, puis sur
  la pose normale si nécessaire.
- Les temps de recharge, le remplissage du chargeur, le son, les contrôles
  tactiles et la coop ne changent pas. La pose revient progressivement au
  repos pendant les 18 % finaux afin que la remise à zéro du compteur ne
  provoque aucun saut.
- `sounds.MUSIC_PROFILES` définit sept identités : menu cinématique,
  Entrepôt industriel, Métropole urbaine, Gouvernement solennel, Base
  militaire martiale, Laboratoire expérimental et Déferlement alien.
  `_music_loop()` synthétise chaque thème à la demande, de façon déterministe
  et bouclable. Les fichiers `menu.*`, `1.*` à `5.*` et `survival.*` gardent
  la priorité.
- `tests/test_reload_music.py` contient huit non-régressions : progression,
  intégrité des seize PNG de recharge, cinq transitions, mouvements distincts,
  quatre étapes HUD réellement différentes par arme, couverture des profils
  et déterminisme/raccord des boucles.

## Équilibrage sniper/militaire et polish des menus/de la mort

- `Sniper.AIM_DELAY = 0.5625` : la mise en joue avant le coup est réduite de
  25 % par rapport aux `0,75 s` précédents. `FIRE_DELAY = 2.3` reste inchangé
  et commence toujours après le tir ; il n'y a donc pas de double accélération
  de la cadence.
- `Soldier.ROLL_DURATION = 0.75` surcharge la valeur générique d'`Enemy`.
  `ROLL_SPEED = 2.8` et `ROLL_COOLDOWN = 3.0` ne changent pas : portée,
  animation et invincibilité diminuent ensemble de 25 %. Le client coop borne
  aussi un ancien `roll_timer` d'une seconde à la durée courante.
- Tous les boutons hérités de `MenuBase` sont placés dans le panneau latéral
  gauche, dessinés comme des parallélogrammes et alignés à gauche. Le contour
  vert et le liseré orange n'apparaissent qu'au survol. La collision suit le
  polygone ; les coins transparents ne sont pas cliquables. Les surfaces
  normales/survolées sont mises en cache par taille.
- `DEATH_SKIP_LOCK = 3.0` interdit à Entrée, Espace, Échap, clic et tactile
  d'écourter les trois premières secondes. La fermeture SDL reste gérée par
  la boucle principale. `HUD.resize()` précalcule le titre serif gothique rouge
  et ses coulures ; avant le déverrouillage, l'indication affiche
  « LA MORT VOUS RETIENT... », puis les commandes de passage.

## Réparation Git, Colosse, possédés, environnements et tactile

- Le `main` force-poussé pointait sur le commit racine `67949e2`, détaché de
  l'historique publié jusqu'à `ef9849d`. Son arbre a été recréé byte-identique
  dans le commit-pont distant `5a56c44`, puis fusionné par la PR #22 dans
  `da017a3`. La branche `backup/force-pushed-main-67949e2` conserve le commit
  racine. Ne jamais reconstruire cette filiation en réappliquant manuellement
  les fichiers : `git diff --exit-code 67949e2 5a56c44` doit rester vide.
- Le Colosse a trois phases déterminées par sa vie : phase 1 au-dessus de
  66 %, phase 2 entre 66 et 33 %, phase 3 sous 33 %. Les couples
  vitesse/cadence sont `(1.15, 0.72)`, `(1.28, 0.58)` et `(1.42, 0.46)`.
  Chaque seuil réellement franchi alimente une file d'événements que `Game`
  matérialise en `lifepack` visible sur un flanc du boss. Si tous les
  emplacements sont momentanément encombrés, l'événement est remis en tête et
  retenté après la séparation des ennemis ; les cadavres ne bloquent pas le
  placement. Un impact franchissant deux seuils libère bien deux packs ; un
  boss tué net n'en libère pas inutilement.
- Les packs du Colosse sont des `Pickup.dynamic` avec un `net_id`. En coop,
  les booléens des objets statiques restent au début de `pk` ; les lignes
  `[id, x, y, kind, taken]` sont ajoutées ensuite. Un ancien client les ignore
  après son `zip`, tandis qu'un nouveau client les valide et les crée. Les
  lignes ennemies ajoutent aussi `max_health` et `possessed` en fin de tableau,
  ce qui corrige au passage la barre de vie des Colosses renforcés par les
  vagues sans casser les formats historiques.
- Tous les ennemis créés par `SurvivalGame.spawn_enemy()` sont possédés.
  `assets.get_possessed()` dérive et met en cache aura, teinte et yeux verts
  depuis chaque pose/orientation existante ; aucun PNG détaillé n'est écrasé.
  Le `Soldier` possédé a `CAN_ROLL=False` et 72 % de sa vitesse de campagne ;
  le `Grunt` possédé conserve 82 % de sa vitesse. Les autres archétypes
  gardent leur mobilité.
- Le Laboratoire utilise un sol de résine blanche `(232..176)` et laisse les
  murs `1`, `2` et le panneau `4` à hauteur standard `1.0`. Seule l'enceinte
  `3` du Colosse reste à `1.55`. Les cratères lunaires sont précalculés avec
  un minimum de 30 et un espacement cible de 38 px : aucun coût par frame.
- `touch_controls.py` détecte les périphériques via
  `pygame._sdl2.touch.get_num_devices()` et s'active aussi au premier
  `FINGERDOWN` (hot-plug). Stick gauche, glissement de visée, tir/ADS,
  roulade, recharge, arme, pause et menu supportent plusieurs doigts. Les
  événements souris synthétiques portant `touch=True` sont ignorés en jeu
  pour éviter un double tir ; clavier et vraie souris restent parallèles.
  Toute bascule pause/reprise remet aussi à zéro les doigts et boutons
  maintenus, afin qu'une action posée pendant la pause ne parte pas à la
  reprise.
- `.github/workflows/ci.yml` s'exécute sur les PR vers `main`, les pushes sur
  `main` et manuellement. Deux jobs Python 3.12 couvrent Ubuntu et Windows :
  installation de Pygame 2.6.1, compilation, règles Ruff critiques et suite
  `unittest`. Les actions GitHub sont épinglées par SHA et le jeton est limité
  à `contents: read`.

## Équilibrage des roulades et écran de mort

- La roulade du joueur dure désormais `0.55 s` à `4.55` cases/s : sa portée
  reste donc pratiquement inchangée (~`2.5` cases) et elle n'a plus aucun
  cooldown. Une nouvelle roulade reste refusée tant que les `0.55 s` de la
  précédente ne sont pas terminées. Elle n'est pas une parade instantanée
  pendant toute l'animation : `0.08 s` d'amorce vulnérable,
  `0.30 s` d'i-frames (`0.08 <= elapsed < 0.38`), puis `0.17 s` de
  récupération vulnérable. Même en les enchaînant, ces deux fenêtres exposées
  empêchent donc une invincibilité continue. `Player.roll_invulnerable` est
  l'autorité ; `roll_invuln` reste à zéro pour préserver la forme de l'ancien
  état.
- `RemotePlayer` applique exactement la même fenêtre côté hôte et côté client.
  Une évolution future de la roulade joueur doit donc maintenir ensemble les
  constantes de `Player`, leur reprise dans `RemotePlayer`, le clamp réseau
  de `rt` et l'allocation anti-téléportation basée sur `ROLL_SPEED`. Chaque
  déclenchement client incrémente aussi `Player.roll_sequence`, envoyé sous
  `rs` : l'hôte accepte une séquence strictement plus récente et rejette les
  vieux datagrammes UDP. Pour un ancien client sans `rs`, un front `rt=0` puis
  `rt>0` est exigé. Sans cela, retirer le cooldown permettrait à un paquet
  retardé de relancer une roulade fantôme.
- Le cooldown du soldat passe de `5.0` à `3.0 s`. Avec un cooldown prêt, un
  projectile réellement encaissé pose `Enemy.hit_roll_request` et l'IA roule
  latéralement par rapport à la source au pas d'IA suivant. La demande est
  volontairement consommée après résolution du coup complet : tous les plombs
  simultanés d'un fusil à pompe infligent leurs dégâts avant l'esquive. Un
  espace trop étroit conserve la courte nouvelle tentative de `0.35 s`.
  `EnemyAI.proactive_roll_delay` décale seulement les roulades spontanées au
  premier contact (`0.6..1.8 s`) ; il ne pollue pas `roll_cooldown` et ne peut
  donc pas empêcher la première réaction à une balle.
- L'écran de mort ne recrée aucune surface ni aucun glyphe par frame.
  `HUD.resize()` prépare le panneau sombre, le titre serif rouge avec coulures,
  l'état vital et les deux indications verrouillée/déverrouillée. Les tailles
  se recalibrent à la résolution ; le fondu et l'indication animée utilisent
  `death_time`, puisque `HUD.update()` est figé pendant la cinématique.
  Entrée/Espace/Échap/clic/tactile sont ignorés avant
  `DEATH_SKIP_LOCK = 3.0`, puis peuvent avancer vers l'écran de fin.

## Passe de nettoyage, robustesse et sécurité LAN

- `settings.py` ne fait plus confiance au JSON local : lecture limitée à
  `64 KiB`, racine obligatoirement objet, nombres finis et bornés, booléens
  stricts, progression plafonnée et IPv4 validée. Les keycodes inconnus,
  `Échap` et `F11` sont rejetés ; les doublons chargés sont réparés et un
  remappage en conflit échange les deux touches au lieu de rendre une action
  inaccessible. La sauvegarde passe par `settings.json.tmp`, `fsync`, puis
  `os.replace` : une interruption ne tronque plus le dernier fichier valide.
- Le menu LAN refuse une IPv4 mal formée avant la connexion. Le menu des
  touches rappelle que `F11` est global et qu'`Échap` annule la capture. En
  jeu, rechargement, changement d'arme et molette sont ignorés pendant la
  pause ou après la fin ; perdre le focus met en pause et libère la visée afin
  d'éviter un clic droit ou un mouvement de souris « coincé » au retour.
- `network.UdpPeer.receive()` n'accepte que des objets JSON, ignore aussi les
  imbrications invalides et ne traite jamais plus de `128` datagrammes dans
  une image. Cela empêche une liste JSON ou un flot UDP de faire planter ou
  d'affamer la boucle de rendu.
- La coop reste hôte-autoritaire : quatre joueurs maximum (hôte + 3), adresse
  source et session exactes, séquence `iq`, coordonnées/angles finis, crédit
  de déplacement alimenté uniquement par l'horloge hôte, collisions dynamiques
  sous-échantillonnées et roulade/i-frames démarrées par l'hôte. `rs` identifie
  toujours chaque roulade, en plus de la séquence générale du paquet.
- Les tirs distants sont bornés à `32` déclenchements par paquet, mais le vieux
  seau générique de crédits/dégâts déclarés est remplacé par les instances
  `Weapon` de l'hôte. Une reconnexion ne rejoue toujours pas cinq secondes de
  minigun d'un coup. Ce n'est pas un système anti-triche Internet, mais les
  téléportations, dégâts arbitraires, munitions infinies, cadences falsifiées
  et dénis de service LAN les plus évidents ne sont plus acceptés.
- Tous les instantanés reçus sont vérifiés avant indexation : lignes trop
  courtes, types d'ennemis inconnus, `NaN`/infinis, événements incomplets,
  santé, vague et positions hors bornes sont ignorés. La santé et la mort
  envoyées par l'hôte restent autoritaires même si le client affiche encore
  un bouclier ou une roulade. Les coéquipiers reçoivent côté hôte le même
  bouclier de spawn/réapparition de `3 s` que le joueur local.
- Optimisations sans changement de gameplay : sprite d'arme HUD redimensionné
  une fois par résolution/arme, volume du canal musical écrit seulement lors
  d'un changement, file d'apparitions du Déferlement passée de `list.pop(0)`
  à `deque.popleft()`, et un seul appel horloge par frame de portail.

## Passe roulades, Lune et menu

- Le milicien `Grunt`, seul ennemi du premier niveau, passe de `SPEED = 1.7`
  à `2.55` (+50 %). Sa cadence reste strictement `FIRE_DELAY = 1.3` : ne pas
  confondre mobilité et fréquence de tir lors d'un futur équilibrage.
- Le militaire `Soldier` possède `CAN_ROLL = True`. En combat et avec un côté
  praticable, l'IA effectue une roulade latérale de `0.75 s`, à `2.8` cases/s,
  avec invincibilité pendant toute l'animation et cooldown de `3.0 s` entre
  deux déclenchements. Durée, portée et i-frames sont donc 25 % plus courtes
  que dans la version à une seconde. Il ne navigue, ne vise et ne tire pas
  pendant l'action. Les trois frames sont
  `assets/enemy_soldier_roll_0..2.png` (`64x96`).
- Le sprint a été supprimé. La touche configurable `roulade` (Maj par défaut)
  déclenche une roulade joueur de `0.55 s`, vitesse `4.55`, i-frames centrales
  de `0.30 s` et aucun cooldown après l'animation. La direction suit ZQSD, ou
  avance par défaut. Les longues impulsions sont sous-échantillonnées : un pic
  de `dt` ne traverse pas un mur. Tir, ADS et rotation de vue sont suspendus ;
  la caméra bascule et l'arme s'abaisse. Le HUD indique « en cours » ou
  « prête ». Les anciens `settings.json` contenant `sprint` sont migrés
  automatiquement vers `roulade`.
- La coop ajoute roulade/temps restant après les anciens champs des joueurs
  et des ennemis. Les formats historiques 7 champs (joueurs), 8 champs
  (ennemis) et 9 champs (ennemis avec `aiming`) restent acceptés. L'hôte
  applique les i-frames des clients distants : la protection n'est pas
  seulement cosmétique côté client.
- Dans `MAP_MOON`, toutes les crevasses `V` sont remplacées par des cristaux
  `k` / `prop_alien_crystal` (`96x112`, largeur monde `0.88`) montrant un alien
  emprisonné. Chaque cristal bloque déplacement/pathfinding par sa case et
  balles/perception par un cercle de rayon `0.46`; le rendu reste un billboard
  irrégulier qui masque naturellement ce qui est derrière par ordre de
  profondeur. Le régolithe utilise `moon_ground`: grain et cratères gris sont
  précalculés au changement de résolution, sans primitives ajoutées par frame.
- Le portail lunaire n'a plus de pied ni de support : anneau ovale complet,
  vortex animé conservé, `v_offset` oscillant autour de `0.11` pour la
  lévitation. Les quatre frames restent en `79x117` et partagent une boîte
  opaque `71x108` en `(4, 2)`.
- Le menu principal utilise un nouveau fond `1280x720`: soldat seul sur la
  Lune, arme abaissée, face à un portail gigantesque. Le panneau et les
  boutons occupent le tiers gauche laissé sombre par la composition ; police,
  libellés, records et pied de page ont été recalibrés à `1280x720` et
  `800x600`. Les autres menus restent centrés et leur mode compact a été
  resserré pour ne pas déborder après le changement de police.

## Corrections de la passe combat et environnements

- Le sniper conserve sa pose de mise en joue à genou. Son anticipation,
  d'abord passée de `1.25` à `0.75` seconde, vaut désormais `0.5625 s`
  (`Sniper.AIM_DELAY`, nouvelle réduction de 25 %). Le cooldown de `2.3`
  secondes commence toujours après le tir : seule la télégraphie avant le
  coup est raccourcie.
- Les frames de tir de `grunt`, `soldier`, `heavy`, `boss` et du coéquipier
  `ally` ont été régénérées en vue strictement frontale. Arme et flash sont
  orientés vers le joueur ; chaque silhouette reste alignée au sol et garde
  une hauteur proche de sa frame `idle`, pour éviter tout pivot ou saut
  d'échelle au tir. Le kamikaze n'est pas concerné car il ne tire jamais.
- Le Laboratoire emploie trois textures dédiées claires :
  `wall_lab_tech.png`, `wall_lab_metal.png` et
  `wall_lab_reinforced.png`. Elles ne remplacent pas les murs historiques
  partagés avec les autres niveaux. `wall_sealed_portal.png` est lui aussi
  intégré à cette enceinte blanche, tout en gardant sa brèche verte enchaînée.
- Les niveaux terrestres ont désormais un panorama de nuages teinté par leur
  horizon. Il est généré une seule fois par niveau/résolution, boucle avec la
  rotation de la caméra et ne demande que deux blits par frame. Tout niveau
  dont la configuration contient `stars` — actuellement la Lune — le
  désactive automatiquement. La clé optionnelle `clouds: false` permet aussi
  de le couper explicitement dans un futur niveau.
- Vérification visuelle effectuée à `960x540` sur les cinq tirs, le
  Laboratoire et la Lune. La mesure SDL factice sur 120 frames n'a montré
  aucun coût marginal mesurable du panorama nuageux.

## Corrections de la passe précédente

- `assets/prop_car.png` a été régénéré : berline complète, avant droit non
  tronqué, contenu opaque `176x67` dans une toile transparente `192x80` avec
  marge sur les quatre côtés. La largeur monde reste `1.10`.
- `assets/prop_bench.png` est désormais un siège parlementaire individuel
  avec pupitre, et non une banquette double massive. Sa largeur monde passe de
  `0.97` à `0.46` dans `entities.PROP_SPECS`.
- Dans `MAP_LAB`, l'ancienne porte `(23, 14)` n'était reliée à une cloison que
  par son côté gauche. Elle est remplacée par un mur métallique `2` : toutes
  les portes restantes sont encadrées par des murs sur un axe.
- `ai.cover_adjusted_chance()` conserve la précision normale à exposition
  complète, mais renforce légèrement le couvert : facteur
  `0.28 + 0.72 * exposure` au lieu de `0.35 + 0.65 * exposure`.
- Le sniper possède `AIM_DELAY = 0.5625`. Lorsque son arme est prête, il passe
  en `aiming`, s'immobilise et utilise `assets/enemy_sniper_aim.png` (un genou
  au sol). Le tir part à la première frame après 0,5625 s. Perdre la ligne de
  vue, se replier au corps à corps, changer d'état, mourir ou perdre la cible
  annule la visée ; aucun tir ne reste stocké derrière un mur.
- La pose à genou a été régénérée pour corriger l'anatomie puis replacée en
  vue strictement frontale : genou gauche au sol, pied droit planté, épaules
  face caméra et canon raccourci pointé vers le joueur. La frame
  `enemy_sniper_fire.png` a été refaite dans la même pose avec un flash centré,
  afin d'éviter un pivot de profil au moment du tir. Ne pas réutiliser les
  versions intermédiaires avec deux pieds droits ou un long canon latéral.
- La coop transmet `aiming` comme neuvième champ de chaque ennemi. Le client
  accepte toujours les anciens instantanés à huit champs et affiche la pose
  du sniper sur les deux machines.
- Le fallback procédural `enemy_sniper_aim` est enregistré dans `assets.py` ;
  il ne remplace jamais le PNG livré tant que celui-ci existe.

## Invariants à préserver

- Les seuils du Colosse se calculent depuis `health / max_health`, jamais
  depuis ses PV bruts : les multiplicateurs de niveau/vague doivent rester
  compatibles. `Boss.take_damage()` produit les événements, mais seul `Game`
  choisit une case praticable et crée les packs. Après réplication directe de
  santé, le client appelle `sync_phase_from_health()` sans créer d'objet local.
  Un placement impossible doit remettre la phase en attente ; les ennemis
  morts ne font jamais partie des positions occupées.
- Les objets dynamiques coop sont ajoutés APRÈS les booléens statiques de
  `pk`. Ne jamais transformer rétroactivement `pk` en dictionnaire ou déplacer
  les lignes dynamiques devant les booléens : les anciens clients dépendent
  de cet ordre. Toute valeur réseau reste validée et bornée avant création.
- `Enemy.set_possessed()` doit précéder la construction de `EnemyAI` sur tout
  nouveau chemin d'apparition, afin que l'IA ne prépare pas de roulade pour un
  `Soldier` possédé. Les variantes visuelles restent des surfaces mises en
  cache et de même taille que la pose source.
- Le tactile ne doit jamais se fier à l'état global du bouton gauche SDL :
  un doigt peut émuler une souris. Le tir maintenu utilise uniquement
  `_mouse_fire_held` pour une vraie souris et `TouchControls.fire_held` pour
  les doigts. Une perte de focus et chaque bascule pause/reprise libèrent les
  deux états et tous les doigts.
- Les dimensions physiques des props reposent sur la boîte opaque, via
  `_height_for_visible_width`; ne pas compenser les marges transparentes en
  augmentant arbitrairement `SPRITE_HEIGHT`.
- Les poses à genou `aim` et `fire` sont contenues dans une toile `64x96`, avec
  une silhouette opaque plus basse (`44x74`, alignée au sol). Le moteur garde
  donc les pieds au sol et le personnage paraît réellement agenouillé sans
  modifier le raycaster.
- Le délai de 0,5625 s s'ajoute au temps entre deux tirs
  (`FIRE_DELAY = 2.3`) : le cooldown commence après le tir, pas au début de
  la mise en joue.
- Une exposition de `1.0` ne doit jamais être pénalisée par le bonus de
  couvert. L'exposition est bornée entre `0.0` et `1.0`.
- Le joueur n'a aucun cooldown mais `Player.start_roll()` doit toujours refuser
  un redéclenchement pendant `rolling`. Le cooldown soldat de `3.0 s` se mesure
  de déclenchement à déclenchement et inclut ses `0.75 s` de roulade. Ne
  jamais remplacer le déplacement sous-échantillonné par un unique grand pas
  collisionné. Les instantanés coop historiques peuvent annoncer jusqu'à
  `1.0 s`, mais le client les borne à `Soldier.ROLL_DURATION`.
- `MAP_MOON`, `PROP_CHARS`, `cover_circles`, le test de ligne de vue et le
  hitscan doivent rester cohérents : retirer seulement l'un d'eux rendrait un
  cristal traversable, invisible à l'IA ou perméable aux balles.
- Toute évolution de l'état réseau joueur/ennemi doit ajouter ses champs en
  fin de ligne et rester tolérante aux instantanés plus courts afin qu'un
  client mis à jour ne plante pas avec un hôte plus ancien.
- Toute donnée UDP est non fiable, même en LAN : ne jamais indexer un paquet
  avant validation, accepter `NaN`/`inf`, ou réintroduire une position, une
  invincibilité, des dégâts ou une cadence décidés sans borne par le client.
  La compatibilité des anciens instantanés concerne leur lecture, pas le
  relâchement des contrôles de l'hôte.
- Le protocole v2 exige `session_id`, `iq` et `sq`; les événements `rev` ne
  sont consommés qu'en séquence contiguë puis acquittés par `ea`. Ne jamais
  vider le journal après un seul envoi ni réaccepter `[angle, dégâts]`.
- `_sprite_cache_bytes` doit toujours rester inférieur ou égal à
  `_sprite_cache_budget`. Toute insertion ou nouvelle forme de surface mise
  en cache doit comptabiliser `get_pitch() * get_height()` et maintenir
  l'ordre LRU. Cette règle ne modifie pas le FIFO mural.
- `RemotePlayer.shield` est simulé par l'hôte. Une réapparition doit remettre
  santé, roulade, cooldown et bouclier ensemble ; côté client, un instantané
  de mort doit d'abord annuler bouclier/i-frames avant de poser le cadavre.
- Le cache `_weapon_scale_cache` appartient à une résolution HUD et doit être
  vidé dans `HUD.resize()`. La file `spawn_queue` est un `deque` : employer
  `extend` / `popleft`, jamais réintroduire `pop(0)` dans la boucle de vague.

## Validation disponible

La suite contient 81 tests. `tests/test_requested_changes.py` conserve les
22 non-régressions graphiques et de gameplay : marges de la
voiture, conception et échelle du siège, topologie des portes et blancheur des
murs du laboratoire, courbe de couvert, délai/annulation/pose du sniper,
compatibilité coop 8/9 champs, stabilité d'échelle des cinq tirs frontaux et
présence/absence correcte des nuages sur Terre/la Lune, vitesse du milicien,
roulades joueur/soldat (direction, i-frames, enchaînement/cooldown, collision,
frames et IA), compatibilité réseau de la roulade, cristaux de couverture et
nouveau fond de menu.

`tests/test_cleanup.py` ajoute 15 contrôles : paquets UDP bornés et non-objets,
réglages malformés/sauvegarde atomique/JSON imbriqué (RecursionError), IPv4,
conflits et touches réservées, téléportation/`NaN`/spam de roulade, séquences
de roulades enchaînées et paquets retardés, validation autoritaire des armes,
bouclier et mort en coop, commandes ignorées en pause, cache du sprite
d'arme, mise en page gothique de mort à basse résolution, verrou non skippable
de trois secondes, géométrie/collision des boutons parallélogrammes et file
d'apparitions en temps constant.

`tests/test_smoke.py` (session 24) ajoute 8 tests de fumée généraux : boot
(réglages + SoundBank avec/sans mixer), campagne (frames complètes, mort
avec caméra jusqu'à `finished`, victoire), Déferlement (vagues, `spawn_queue`
deque, `survival_info`), rendu/clic de tous les menus aux résolutions
extrêmes, coop réelle en loopback UDP (join → `synced`, draw des deux côtés,
sockets refermées — port de test 15577 ≠ 5577), round-trip des réglages avec
JSON tronqué, et lecture de tous les effets/musiques.

`tests/test_gameplay_extensions.py` ajoute 11 contrôles : règles/cache et
miroir des possédés, trois phases/deux packs et reprise d'un placement différé
du Colosse, extension coop des ennemis/objets dynamiques, sol/hauteurs du
Laboratoire, densité des cratères, multi-touch, rejet du clic souris
synthétique, reprise de pause sans action maintenue et blocage de la roulade
coop après l'issue.

`tests/test_reload_music.py` ajoute 8 contrôles : progression normalisée de
la recharge, dimensions/alpha des seize poses, cinq transitions, mouvements
distincts, quatre étapes HUD réellement différentes par arme, couverture des
sept profils musicaux et génération déterministe/distincte/raccordée.

`tests/test_impact_audio.py` ajoute 7 contrôles : classification et priorité
des matières, palettes de particules non mélangées, migration/persistance des
deux volumes, lignes du menu, gains indépendants, réplication exacte des
impacts coop et rejet des événements réseau malformés.

`tests/test_p0_p1.py` ajoute 10 contrôles adversariaux : budget mémoire LRU,
collision joueur/ennemi avec grand `dt`, débit distant alimenté par l'horloge
hôte, pause globale, séquence d'entrée, retransmission jusqu'à acquittement,
session/ordre des instantanés, réparation de l'inventaire, compression UDP et
recharge d'une arme rangée.

Commande utilisée :

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --python 3.12 --with pygame \
  python -m unittest discover -s tests -v
```

(`--python 3.12` est nécessaire : pygame 2.6.1 n'a pas de wheel pour les
Python plus récents et tenterait de se compiler depuis les sources.)

## Passe libre Kimi (25 juillet 2026) — bugs, robustesse, perf, tests

Détails complets dans `CHANGELOG.md`. Points à connaître pour la suite :

- `Enemy.cancel_aim()` est appelé sur TOUTES les transitions d'état de l'IA
  (attack→cover, cover→chase, chase→idle, et l'historique attack→chase) :
  toute nouvelle transition doit l'appeler aussi, sinon le sniper tire sans
  télégraphie et patrouille à genou.
- Le son de rechargement est joué aux DEUX endroits où un rechargement
  démarre : touche R ET rechargement automatique en fin de chargeur
  (`game.py` + `coop.py`).
- Sous Windows, la socket hôte utilise `SO_EXCLUSIVEADDRUSE` (jamais
  `SO_REUSEADDR`, qui y autorise un double bind UDP silencieux) ; ailleurs,
  `SO_REUSEADDR` est conservé.
- Nouveaux caches à respecter : `_sysfont` (menu.py, durée de vie process),
  `HUD._text_cache` (borné à 256, réservé aux libellés STATIQUES, vidé dans
  `resize()` avec les polices), `HUD._slot_icon_cache`, `raycaster._zoom_scratch`
  (tampon ADS unique, réalloué au changement de taille), variantes alpha des
  murs d'énergie mémoïsées dans `_wall_cache` sous une clé `(*clé, alpha)`
  avec alpha quantifié par pas de 16 — la surface du chemin opaque (255) n'est
  JAMAIS mutée par `set_alpha`. La politique FIFO à éviction unique reste
  inchangée pour toute insertion.
- `zoom_screen` blitte désormais depuis l'écran via un `area` plutôt que
  `subsurface().copy()` ; le post-traitement ADS lui-même est inchangé
  (invariant FOV toujours valable).
- Minimap : la base statique est blittée directement et les points mobiles
  dessinés sur l'écran à l'offset (10, 10) — plus de `.copy()` par frame.

## Portails (20 juillet 2026)

- Le portail lunaire utilise quatre PNG `assets/prop_portal_0..3.png`. La
  classe `Prop` sélectionne une frame toutes les `110 ms` avec
  `pygame.time.get_ticks()`. Les surfaces et leurs mises à l'échelle sont
  mises en cache : aucune rotation/composition n'est faite pendant le rendu.
- Les quatre frames font `79x117`, partagent la même boîte opaque (`71x108`,
  en `(4, 2)`) et gardent l'anneau immobile ; seul le vortex vert tourne et
  pulse. L'anneau est fermé, sans support, et lévite. Le portail ne doit pas
  être retourné selon la parité de sa case.
- Dans `MAP_LAB`, le mur `(28, 18)`, derrière l'épaule du Colosse placé en
  `(25, 19)`, devient le caractère `4` / `wall_sealed_portal`. La texture
  montre un petit trou vert barré de chaînes : le Colosse est visuellement le
  Sceau qui retient le futur Déferlement. Ne pas le remettre en `(28, 19)` :
  dans l'axe central, le billboard du boss le masque entièrement.
- Ce mur spécial reste solide pour déplacements, tirs et pathfinding. Sa
  hauteur volontairement standard (`1.0`) en fait un panneau en retrait devant
  le mur technique extérieur et évite de répéter verticalement le petit sceau.
- Les animations de props sont locales et purement visuelles ; elles ne sont
  pas ajoutées aux instantanés coop.

---

<!-- ====== Contenu consolidé depuis `AGENTS.md` ====== -->

# AGENTS.md — Contexte projet Call of Python (synthèse)

> Synthèse (dernière source : 23 juillet 2026), destinée aux agents IA qui
> lisaient `AGENTS.md` (ex. Kimi Code). Les sections détaillées ci-dessus
> restent la référence.

FPS rétro Python 3.12 / pygame (raycasting pseudo-3D façon Wolfenstein 3D).
Repo : `BLKMLO/Call-Of-Python` (renommé depuis `TempGPT`).

## Lancer / tester

```bash
pip install -r requirements.txt
python main.py
```

81 tests dans `tests/` (`test_requested_changes.py` : 22 non-régressions
gameplay/graphiques ; `test_cleanup.py` : 15 contrôles robustesse/réseau/UI ;
`test_smoke.py` : 8 tests de fumée généraux ;
`test_gameplay_extensions.py` : 11 tests Colosse/tactile ;
`test_reload_music.py` : 8 tests recharge/audio ;
`test_impact_audio.py` : 7 tests impacts/volumes/menu/coop ;
`test_p0_p1.py` : 10 tests mémoire/protocole/collisions/sécurité) :

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --python 3.12 --with pygame \
  python -m unittest discover -s tests -v
```

Smoke tests commités dans `tests/test_smoke.py` avec
`SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy` (boot, campagne, survie,
menus, coop loopback UDP réel hôte↔client, réglages, sons).

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
- **Caches de rendu** : cache mural FIFO, éviction d'UNE entrée par insertion
  — jamais en bloc (pics de lag ~200 ms). Cache de billboards LRU pondéré par
  `pitch × hauteur`, strictement limité à 64 Mio et 512 entrées.
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
- **Colosse** : phases par ratios 66/33 %, pas par PV absolus ; chaque seuil
  vivant produit exactement un pack dynamique placé hors de la ligne de tir.
  En coop, `max_health`/`possessed` restent en fin de ligne ennemie et les
  objets dynamiques restent après les booléens statiques de `pk`.
- **Possédés** : uniquement les apparitions de `SurvivalGame`; `Soldier`
  sans roulade à 72 % de vitesse, `Grunt` à 82 %. Aura/yeux dérivés et mis en
  cache depuis les poses existantes, sans nouveau PNG.
- **Tactile** : activation SDL ou premier `FINGERDOWN`; l'état souris global
  n'est jamais utilisé pour le tir maintenu, afin d'éviter le double clic
  synthétique. Focus perdu = tous les doigts et boutons libérés.
- **Roulade joueur** : 0,55 s à 4,55 cases/s, sans cooldown, mais fenêtre
  d'i-frames centrale de 0,30 s (0,08 s amorce + 0,17 s récupération vulnérables).
  `Player.roll_invulnerable` est l'autorité ; refus de redéclenchement pendant
  `rolling`. Déplacement sous-échantillonné (jamais un grand pas collisionné).
  Toute évolution doit maintenir ensemble : constantes `Player`, reprise dans
  `RemotePlayer`, clamp réseau `rt`, allocation anti-téléportation `ROLL_SPEED`,
  séquence `rs` (l'hôte rejette les datagrammes UDP retardés ; front `rt=0`→`rt>0`
  pour les anciens clients).
- **Roulade soldat** (`CAN_ROLL`) : 0,75 s à 2,8 cases/s, cooldown 3,0 s de
  déclenchement à déclenchement. Portée et i-frames ont diminué ensemble de
  25 %. `hit_roll_request` est posé après résolution complète d'un coup (tous
  les plombs d'un fusil à pompe passent avant l'esquive).
- **Sniper** : `AIM_DELAY = 0,5625 s` (télégraphie à genou,
  `enemy_sniper_aim.png`), puis `FIRE_DELAY = 2,3 s` APRÈS le tir. Toute perte
  de vue/cible annule la visée.
- **Couvert** : `cover_adjusted_chance()` = `0,28 + 0,72 * exposure` ; une
  exposition de 1,0 n'est jamais pénalisée. `exposure` bornée [0, 1].
- **Grunt** : `SPEED = 2,55` (+50 %), cadence inchangée `FIRE_DELAY = 1,3`.
- **Bouclier de spawn** (3 s, aussi pour les coéquipiers en coop) : les tests de
  dégâts doivent faire `player.shield = 0.0` d'abord.
- **Caméra de mort** : gameplay figé à `outcome == "dead"`, `death_time` tourne
  (~`DEATH_CAM_TIME`) avant `finished`. Aucune entrée ne peut passer la mort
  avant `DEATH_SKIP_LOCK = 3.0`. HUD et titre sanglant préparés dans
  `HUD.resize()` ; vider `_weapon_scale_cache`, `_reload_blend_cache` et
  `_reload_sprite_cache` dans `resize()`.
- **Menus** : tous les boutons passent par `MenuBase._button_surface()` et
  `_button_contains()` ; conserver la forme parallélogramme, le placement
  latéral gauche, le contour uniquement au survol et la collision polygonale.
- **Recharges** : `RELOAD_KEYFRAMES` garde les six points de passage repos →
  `_reload_1` → `_reload_2` → `_reload` → `_reload_3` → repos. Les PNG sont
  `192x144` transparents ; tout asset manquant doit continuer à replier vers
  `_reload`, puis la pose normale, sans création par frame.
- **Cristaux lunaires** (`MAP_MOON`, `k`/`prop_alien_crystal`) : bloquent
  déplacement/pathfinding par la case ET balles/perception par un cercle rayon
  0,46 — `PROP_CHARS`, `cover_circles`, ligne de vue et hitscan doivent rester
  cohérents ensemble.
- **Portail lunaire** : 4 frames `prop_portal_0..3.png` (79x117, boîte opaque
  71x108 en (4,2)), anneau fermé sans support, vortex animé (110 ms/frame),
  `v_offset` ~0,11. Mur `wall_sealed_portal` en `(28,18)` de MAP_LAB (pas (28,19)).
  Animations de props = locales, jamais dans les instantanés coop.
- **Réseau** : UDP non fiable même en LAN — valider AVANT d'indexer (pas de
  NaN/inf, positions/dégâts/i-frames/cadence décidés par le client). Protocole
  v2 : session, `iq`/`sq`, événements `rev` contigus acquittés par `ea`,
  compression `Z1` bornée. Nouveaux champs ajoutés EN FIN de ligne, tolérance
  aux instantanés plus courts. Tirs : ≤32 déclenchements/paquet, instances
  `Weapon` hôte, vieux `[angle, dégâts]` refusés. Réapparition = santé +
  roulade + cooldown + bouclier ensemble ; un instantané de mort annule
  d'abord bouclier/i-frames. `spawn_queue` = `deque` (`extend`/`popleft`,
  jamais `pop(0)`).
- **Settings** : JSON ≤ 64 KiB, types stricts, progression plafonnée, IPv4
  validée ; Échap/F11 non remappables ; conflit de touches = échange.
- **Divers** : `SLOT_SCANCODES` (AZERTY/QWERTY) ; molette `event.flipped` ;
  `invert_mouse` inverse les DEUX axes ; point de bascule des boutons `< valeur >`
  entre les chevrons (`MenuBase._bracket_split`) ; sprint supprimé (touche
  `roulade`, Maj par défaut, migration auto des anciens `settings.json`) ;
  `settings.json` est gitignoré (normal qu'il apparaisse modifié).

## Dette / manques

- numba évoqué, jamais implémenté (le cache FIFO a suffi).
- Multijoueur testé en UDP local seulement, pas multi-machines.
