# PyFPS — FPS en Python / pygame (raycasting)

Petit FPS façon rétro (rendu pseudo-3D par raycasting, comme Wolfenstein 3D),
écrit en Python 3.12 avec **pygame comme seule dépendance externe**. Aucun
asset : sprites, arme, sons et interface sont générés procéduralement.

## Lancer le jeu

```bash
pip install -r requirements.txt   # installe pygame
python main.py
```

## Contrôles (par défaut, re-mappables dans Paramètres)

| Action            | Touche       |
|-------------------|--------------|
| Avancer / reculer | `Z` / `S`    |
| Gauche / droite   | `Q` / `D`    |
| Viser             | Souris       |
| Tirer             | Clic gauche (maintien = rafale) |
| Recharger         | `R`          |
| Pause             | `Échap` (puis `M` pour revenir au menu) |

Le clavier est re-mappable dans le menu **Paramètres** (WASD possible),
qui règle aussi la **résolution**, le **volume** et la **sensibilité souris**.
Les paramètres sont sauvegardés dans `settings.json`.

## Gameplay

- Map de test avec salles, couloirs et piliers de couverture, plus une minimap.
- 6 ennemis avec IA : détection à vue, poursuite, tir à portée, et repli
  vers un point de couverture quand ils sont blessés.
- Vie/mort pour le joueur et les ennemis (barres de vie), écran de
  **game over** et écran de **victoire** quand tous les ennemis sont éliminés.

## Architecture (pensée pour être étendue)

| Fichier        | Rôle |
|----------------|------|
| `main.py`      | Point d'entrée, machine à états (menu / paramètres / jeu / fin) |
| `settings.py`  | Paramètres + persistance JSON (résolution, volume, sensibilité, touches) |
| `menu.py`      | Menu principal, écran de paramètres, écran de fin |
| `game.py`      | Boucle de gameplay : entrées, tir hitscan, conditions de fin |
| `level.py`     | Maps ASCII, collisions (glissement le long des murs) |
| `raycaster.py` | Moteur de rendu : murs (DDA + z-buffer), sprites billboard, ligne de vue |
| `entities.py`  | `Entity`, `Player`, `Enemy` (sprites procéduraux) |
| `ai.py`        | Machine à états des ennemis (idle / chase / attack / cover) |
| `weapons.py`   | Statistiques d'armes (dégâts, cadence, chargeur, rechargement) |
| `hud.py`       | Viseur, arme animée, barres de vie, munitions, minimap, pause |
| `sounds.py`    | Sons synthétisés en pur Python (tirs, impacts, UI) |

### Pistes d'extension

- **Nouvelle arme** : instancier un autre `Weapon` dans `weapons.py`
  (ex. pistolet, fusil à pompe) et gérer le changement d'arme dans `game.py`.
- **Nouvelle map** : ajouter une grille ASCII dans `level.py` et la passer
  à `Level(...)`.
- **Nouveau type d'ennemi** : hériter d'`Enemy` (vitesse, portées, couleurs
  du sprite) — l'IA de `ai.py` est réutilisable telle quelle.
- **Multijoueur** : la simulation (`game.py` + `entities.py`) est séparée du
  rendu (`raycaster.py` / `hud.py`), ce qui facilite une future
  synchronisation réseau des états d'entités.
