# Call of Python — contexte projet

> Pour les corrections les plus récentes et leurs invariants, lire d'abord
> `GPT.md`.

FPS rétro en Python 3.12 / pygame (raycasting pseudo-3D façon Wolfenstein
3D), développé de bout en bout par itérations avec Claude Code. Ce fichier
résume l'état du projet pour reprendre le travail sans tout redécouvrir.
**Ce fichier a été généré automatiquement pour être nettoyé/édité par
l'utilisateur** — à élaguer selon ce qui reste utile.

Repo GitHub : `BLKMLO/Call-Of-Python` (renommé depuis `BLKMLO/TempGPT` ;
l'origin git peut encore pointer sur l'ancienne URL). Branche de travail
habituelle : `claude/python-fps-pygame-e1fouo`.

## Lancer / tester

```bash
pip install -r requirements.txt
python main.py
```

Pas de framework de test committé dans le repo (voir "Dette / manques"
ci-dessous) : les sessions précédentes ont utilisé des scripts de fumée
(`smoke_test2.py` … `smoke_test11.py`) exécutés depuis un répertoire
scratchpad **temporaire, hors dépôt** (`/tmp/claude-.../scratchpad/`) —
ils ne sont donc PAS disponibles dans une nouvelle session. Motif type
d'un script :

```python
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
# ... imports, pygame.init(), pygame.mixer.init() dans un try/except ...
```

Chaque script instancie `Game`/`SurvivalGame`/`CoopHostGame`/`CoopClientGame`
avec un driver vidéo/audio factice, simule plusieurs frames (`update`/`draw`),
et vérifie des invariants avec de simples `assert`. Si on relance une passe
de tests, il faudrait soit régénérer ces scripts, soit (mieux) les commiter
dans un dossier `tests/` du repo pour ne pas les reperdre à chaque session.

## Architecture

| Fichier        | Rôle |
|----------------|------|
| `main.py`      | Point d'entrée, machine à états (menu / jeu / Sceau / Déferlement / fin), musique |
| `settings.py`  | Paramètres + persistance JSON (résolution, volume, sensibilité, souris inversée, plein écran F11, touches, progression, records) |
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
| `sounds.py`    | Effets + musique synthétisés en pur Python (+ overrides fichiers réels dans `assets/sound/`) |
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
  `AUDIO_EXTENSIONS` (ogg, mp3, wav, flac).
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
14. Bouclier temporaire au changement de niveau, sprint Maj gauche/droite.
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
    genou pendant 1,25 s (synchronisée en coop). Contexte dans `GPT.md`.

## Dette / manques à connaître

- **Couverture de tests encore partielle.** Les régressions de la passe GPT
  sont committées dans `tests/test_requested_changes.py`; les anciens tests
  de fumée généraux (`smoke_test2..11.py`) restent absents du dépôt.
- **numba** : évoqué comme piste d'optimisation si un jour nécessaire,
  jamais implémenté (le cache FIFO a suffi à éliminer les pics de lag
  observés).
- **Multijoueur** : testé uniquement en local (deux instances sur la
  même machine) via les scripts de fumée — pas de test réseau réel
  multi-machines.
- `settings.json` est gitignoré (contient les préférences locales/l'IP
  du dernier hôte rejoint) — normal que `git status` le montre modifié
  après une partie.
