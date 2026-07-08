# Call of Python — FPS en Python / pygame (raycasting)

FPS façon rétro (rendu pseudo-3D par raycasting, comme Wolfenstein 3D),
écrit en Python 3.12 avec **pygame comme seule dépendance externe** —
y compris le multijoueur LAN (sockets UDP de la bibliothèque standard).

Les graphismes sont en **pixel-art façon Minecraft** : de petits fichiers
PNG (`assets/`) dessinés en basse résolution, "pliés" sur les murs 3D par
le raycaster et affichés en billboards pour les personnages et objets.
Les PNG sont générés par `assets.py` (et régénérables avec
`python assets.py`), mais peuvent aussi être retouchés à la main dans
n'importe quel éditeur d'images, comme un pack de textures.

## Lancer le jeu

```bash
pip install -r requirements.txt   # installe pygame
python main.py
```

## Contrôles (par défaut, re-mappables dans Paramètres)

| Action              | Touche       |
|---------------------|--------------|
| Avancer / reculer   | `Z` / `S`    |
| Gauche / droite     | `Q` / `D`    |
| Sprint              | `Maj gauche` |
| Viser (horizontal + vertical) | Souris |
| Tirer               | Clic gauche (maintien = rafale pour les armes automatiques) |
| Changer d'arme      | `1`–`4` ou molette |
| Recharger           | `R`          |
| Compteur de FPS     | `F3`         |
| Pause               | `Échap` (puis `M` pour revenir au menu) |

Le menu **Paramètres** règle la résolution, le volume, la sensibilité de
la souris et les touches (WASD possible). Sauvegardé dans `settings.json`.

## Histoire

Quatre niveaux pour atteindre le cœur du bastion... et son gardien, le
Colosse. Mais en l'abattant, vous comprenez trop tard : il n'était pas
leur champion, il était **le Sceau** qui retenait la horde. Sa mort
déclenche **le Déferlement** — un mode survie où les vagues déferlent
par les sas de l'arène, jusqu'à la cinquantième.

## Gameplay

- **4 niveaux** à thèmes différents (Entrepôt, Base militaire,
  Laboratoire, Assaut final), chacun avec sa carte, ses textures, son
  ambiance et sa nappe musicale. Le niveau suivant se débloque quand
  **tous les ennemis sont éliminés** ; le joueur y conserve son arsenal
  et récupère de la vie. **S'il meurt, il repart de zéro** (niveau 1,
  pistolet seul). Le meilleur niveau atteint est mémorisé.
- **Le Déferlement (mode survie)** : débloqué en brisant le Sceau (et
  ensuite accessible depuis le menu). Des vagues de plus en plus grosses
  et dures, **jusqu'à la vague 50** ; un Colosse accompagne la horde
  toutes les 10 vagues. Une vague nettoyée accorde un répit et un peu de
  vie ; mais **si elle n'est pas nettoyée en 60 secondes, la suivante
  déferle par-dessus** — la submersion guette. Trousses de soins toutes
  les 3 vagues, armes au sol de plus en plus améliorées toutes les 5.
  Le record de vagues est sauvegardé.
- **Portes coulissantes automatiques** sur les cartes : elles s'ouvrent
  à l'approche (du joueur comme des ennemis — l'IA les traverse), les
  balles et les regards passent par l'entrebâillement.
- **Multijoueur LAN en coopération** sur le Déferlement : un joueur
  **héberge** (il fait tourner la partie), les autres **rejoignent** par
  son adresse IP locale (port UDP 5577). Architecture hôte-autoritaire :
  chaque client simule son propre joueur (visée sans latence) et reçoit
  ~15 instantanés/s du monde ; les coéquipiers apparaissent en uniforme
  bleu. Un joueur à terre réapparaît après quelques secondes — la partie
  n'est perdue que si tous tombent en même temps.
- **5 types d'ennemis** : milicien, soldat, soldat lourd, **kamikaze**
  (très rapide, gilet explosif : il fonce et détone au contact — ou
  quand on l'abat, avec réactions en chaîne dans une grappe) et
  **sniper** (mortel à longue portée, il recule si on l'approche) —
  **plus un boss** (le Colosse, 550 PV, barre de vie dédiée). IA :
  détection à vue, **pathfinding BFS** (ils contournent murs, piliers et
  portes), **strafe latéral en combat**, **alerte des alliés** (un ennemi
  qui vous repère crie, un coup de feu attire le secteur), patrouille au
  repos, repli vers un point de couverture quand ils sont blessés. Leurs
  vie et dégâts augmentent avec les niveaux. **Sprites directionnels**
  (on les voit de face, de dos ou de profil selon leur orientation),
  animations de marche/tir, barres de vie flottantes, **cadavres
  persistants** au sol.
- **Packs de vie cachés** : un par carte, hors minimap (dont une salle
  secrète derrière une porte dans la Base militaire). Bloc blanc à croix
  rouge dont les **étincelles vertes** trahissent la présence — soin
  complet. En survie, il réapparaît à chaque vague de Colosse.
- **Statistiques de partie** : éliminations, précision et temps de jeu,
  affichés en direct au HUD et en bilan sur les écrans de fin de niveau
  et de fin de partie (cumulés sur la campagne).
- **4 armes** : pistolet de départ, puis fusil à pompe, fusil d'assaut et
  minigun **à ramasser sur les cartes**. Une arme trouvée à un niveau
  supérieur est plus puissante (« Mk. II », « Mk. III »...) ; ramasser
  une arme déjà possédée la recharge ou l'améliore. Trousses de soins au
  sol également.
- **Sensations FPS** : visée verticale à la souris (y-shearing), sprint,
  tremblement d'écran (dégâts, grosses armes), marqueurs de touche,
  viseur dynamique qui s'écarte au tir, indicateurs de direction des
  dégâts reçus.
- **Audio spatial** : sons du monde atténués avec la distance et
  panoramiqués gauche/droite (stéréo) selon la direction ; **musique
  d'ambiance procédurale** propre à chaque niveau — le tout synthétisé
  en pur Python, sans aucun fichier audio.
- **Particules** : sang à l'impact (qui s'écrase au sol), gerbe à la
  mort, poussière teintée de la texture du mur touché, fondu de sortie.
- **Performances** : colonnes de murs et sprites mis à l'échelle
  mémoïsés, ombrage et brume pré-calculés, correction de perspective en
  table, lancer de rayons optimisé, ligne de vue de l'IA cadencée —
  100+ FPS en 1280x720 même en pleine horde.
- HUD complet : arme en vue subjective animée (balancement, recul,
  éclair de bouche, abaissée au rechargement), munitions, emplacements
  d'armes, minimap (ennemis, objets), voile rouge de dégâts, compteur
  de FPS optionnel.

## Architecture (pensée pour être étendue)

| Fichier        | Rôle |
|----------------|------|
| `main.py`      | Point d'entrée, machine à états (menu / jeu / Sceau / Déferlement / fin), musique |
| `settings.py`  | Paramètres + persistance JSON (résolution, volume, touches, progression, records) |
| `menu.py`      | Menu principal, paramètres, fin de niveau, écran du Sceau, game over / victoire |
| `game.py`      | Boucle de gameplay : entrées, tir hitscan multi-plombs, ramassages, alertes, portes, stats |
| `survival.py`  | Le Déferlement : vagues, submersion à 60 s, apparitions par les sas, ravitaillement |
| `network.py`   | Couche LAN : datagrammes UDP + JSON, sockets non bloquantes, sans thread |
| `coop.py`      | Coop LAN : hôte autoritaire (`CoopHostGame`) et client répliqué (`CoopClientGame`) |
| `level.py`     | Cartes ASCII + niveaux (thème, ennemis, armes, difficulté) + portes coulissantes |
| `raycaster.py` | Rendu : murs texturés (DDA + z-buffer), portes, y-shearing, billboards, particules |
| `entities.py`  | `Player` (arsenal, pitch), `Grunt`/`Soldier`/`Heavy`/`Boss`, `Pickup`, sprites directionnels |
| `ai.py`        | Machine à états des ennemis (idle / chase / attack / cover) + pathfinding BFS |
| `weapons.py`   | Specs des armes + niveaux d'amélioration (Mk. II...) |
| `hud.py`       | Arme FP, viseur dynamique, marqueurs, panneau de vagues, minimap, barre de boss |
| `particles.py` | Particules 3D (sang, impacts, poussière, surgissements) |
| `sounds.py`    | Effets + musique d'ambiance synthétisés en pur Python, stéréo positionnelle |
| `assets.py`    | Génération/chargement des PNG pixel-art (`assets/`) |

### Pistes d'extension

- **Nouvelle arme** : un `WeaponSpec` dans `weapons.py` + ses sprites
  `fp_<id>` / `pickup_<id>` dans `assets.py`.
- **Nouveau niveau** : une grille ASCII + une entrée dans `LEVELS`
  (`level.py`) — thème, composition d'ennemis, armes au sol.
- **Nouveau type d'ennemi** : hériter d'`Enemy` (`entities.py`) et
  ajouter sa palette dans `assets.py` — l'IA est réutilisable telle quelle.
- **Nouvelles textures** : éditer les PNG de `assets/` directement, ou
  ajouter un builder dans `assets.py`.
- **Multijoueur** : le protocole de `coop.py` (instantanés JSON) est
  simple à étendre — nouveaux événements, plus de joueurs, coop sur la
  campagne, voire un mode versus.
