# PyFPS — FPS en Python / pygame (raycasting)

Petit FPS façon rétro (rendu pseudo-3D par raycasting, comme Wolfenstein 3D),
écrit en Python 3.12 avec **pygame comme seule dépendance externe**.

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

## Gameplay

- **4 niveaux** à thèmes différents (Entrepôt, Base militaire,
  Laboratoire, Assaut final), chacun avec sa carte, ses textures, son
  ambiance et sa nappe musicale. Le niveau suivant se débloque quand
  **tous les ennemis sont éliminés** ; le joueur y conserve son arsenal
  et récupère de la vie. **S'il meurt, il repart de zéro** (niveau 1,
  pistolet seul). Le meilleur niveau atteint est mémorisé.
- **3 types d'ennemis** (milicien, soldat, soldat lourd) **plus un boss**
  (le Colosse, 550 PV, barre de vie dédiée) au dernier niveau. IA :
  détection à vue, **pathfinding BFS** (ils contournent murs et piliers),
  **strafe latéral en combat**, **alerte des alliés** (un ennemi qui vous
  repère crie, un coup de feu attire le secteur), patrouille au repos,
  repli vers un point de couverture quand ils sont blessés. Leurs vie et
  dégâts augmentent avec les niveaux. Sprites animés (marche, tir),
  barres de vie flottantes, **cadavres persistants** au sol.
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
- **Particules** : sang à l'impact, gerbe à la mort, poussière teintée de
  la texture du mur touché.
- HUD complet : arme en vue subjective animée (balancement, recul,
  éclair de bouche, abaissée au rechargement), munitions, emplacements
  d'armes, minimap (ennemis, objets), voile rouge de dégâts, compteur
  de FPS optionnel.

## Architecture (pensée pour être étendue)

| Fichier        | Rôle |
|----------------|------|
| `main.py`      | Point d'entrée, machine à états (menu / paramètres / jeu / transition / fin), musique |
| `settings.py`  | Paramètres + persistance JSON (résolution, volume, sensibilité, touches, progression) |
| `menu.py`      | Menu principal, paramètres, fin de niveau, game over / victoire |
| `game.py`      | Boucle de gameplay : entrées, tir hitscan multi-plombs, ramassages, alertes, fins |
| `level.py`     | Cartes ASCII + définition des niveaux (thème, ennemis, armes, difficulté) |
| `raycaster.py` | Rendu : murs texturés (DDA + z-buffer), y-shearing, billboards, particules, ligne de vue |
| `entities.py`  | `Player` (arsenal, pitch), `Grunt`/`Soldier`/`Heavy`/`Boss`, `Pickup` |
| `ai.py`        | Machine à états des ennemis (idle / chase / attack / cover) + pathfinding BFS |
| `weapons.py`   | Specs des armes + niveaux d'amélioration (Mk. II...) |
| `hud.py`       | Arme FP, viseur dynamique, marqueurs, vie, munitions, minimap, barre de boss |
| `particles.py` | Particules 3D (sang, impacts, poussière) |
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
- **Multijoueur** : la simulation (`game.py` + `entities.py`) est séparée
  du rendu (`raycaster.py` / `hud.py`), ce qui facilite une future
  synchronisation réseau des états d'entités.
