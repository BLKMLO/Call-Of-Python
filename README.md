# Call of Python — FPS en Python / pygame

FPS rétro en pseudo-3D par raycasting, inspiré de *Wolfenstein 3D* et écrit
en Python 3.12. `pygame` est la seule dépendance externe ; le multijoueur
LAN utilise les sockets UDP de la bibliothèque standard.

Le jeu propose une campagne de cinq niveaux, un mode survie coopératif et
une direction graphique pixel-art militaire/SF. Les textures, sprites
directionnels et armes sont fournis dans `assets/`.

## Lancer le jeu

```bash
pip install -r requirements.txt
python main.py
```

Le pack PNG livré est chargé en priorité. En cas de fichier manquant,
`python assets.py` génère uniquement les éléments absents. Pour restaurer
volontairement tous les anciens visuels procéduraux :

```bash
python assets.py --force-procedural
```

## Contrôles

Les touches sont modifiables dans **Paramètres**.

| Action | Touche par défaut |
|---|---|
| Avancer / reculer | `Z` / `S` |
| Gauche / droite | `Q` / `D` |
| Sprint | `Maj` |
| Regarder / viser | Souris |
| Tirer | Clic gauche |
| Mise en joue | Clic droit maintenu |
| Changer d'arme | `1`–`4` ou molette |
| Recharger | `R` |
| Afficher les FPS | `F3` |
| Pause | `Échap` |

La résolution, le volume, la sensibilité et les touches sont sauvegardés
dans `settings.json`.

## Modes de jeu

### Campagne

Parcourez l'**Entrepôt**, la **Métropole**, le **Gouvernement**, la
**Base militaire** et le **Laboratoire** pour stopper une invasion. Chaque
niveau possède sa carte, ses ennemis, ses décors et son ambiance.

Le niveau suivant se débloque après l'élimination de tous les ennemis.
L'arsenal et une partie de la vie sont conservés entre les missions, mais
une mort relance la campagne depuis le début. Le meilleur niveau atteint
reste mémorisé.

Le Colosse du Laboratoire n'était pas le chef de l'invasion, mais le Sceau
qui retenait un portail lunaire. Sa chute débloque **Le Déferlement**.

### Le Déferlement

Mode survie sur une plaine lunaire ouverte : les ennemis apparaissent par
un portail central pendant 30 vagues de plus en plus rapides. Un Colosse
rejoint la horde toutes les dix vagues, tandis que soins et améliorations
d'armes sont distribués à intervalles réguliers.

Le mode est jouable seul ou en coopération LAN. Un joueur héberge la
partie sur le port UDP `5577`, les autres rejoignent son adresse IP locale.
L'hôte reste autoritaire sur le monde et la partie ne se termine que si
tous les joueurs sont à terre simultanément.

## Fonctionnalités principales

- **Raycasting avancé** : murs texturés à hauteurs variables, portes
  coulissantes, z-buffer, ciel dynamique et visée verticale.
- **Combat FPS** : pistolet, fusil à pompe, fusil d'assaut et minigun avec
  recul, rechargement, niveaux d'amélioration et mise en joue.
- **Ennemis variés** : milicien, soldat, lourd, kamikaze, sniper et
  Colosse, avec sprites directionnels et animations.
- **IA tactique** : détection, patrouille, alerte des alliés, couverture,
  contournement et pathfinding BFS.
- **Décors interactifs** : véhicules, mobilier, rochers, crevasses et
  portail influencent les déplacements et le pathfinding.
- **HUD complet** : vie, munitions, arsenal, minimap, statistiques,
  indicateurs de dégâts, barre de boss et compteur de FPS optionnel.
- **Ambiance dynamique** : cycle solaire propre à chaque niveau, audio
  spatial, musiques procédurales et particules d'impact.
- **Progression** : armes à ramasser, trousses de soins, packs de vie
  cachés, statistiques et records sauvegardés.
- **Optimisations** : caches de mise à l'échelle, éclairage pré-calculé,
  raycasting optimisé et calculs d'IA cadencés.

Des fichiers audio personnalisés peuvent être placés dans `assets/sound/`
aux formats MP3, OGG, WAV ou FLAC : `menu`, `survival`, `reload` et les
numéros de niveaux (`1`, `2`, etc.). Les sons synthétisés restent utilisés
en l'absence de fichiers.

## Architecture

| Fichier | Rôle |
|---|---|
| `main.py` | Point d'entrée et machine à états |
| `settings.py` | Paramètres, touches et progression |
| `menu.py` | Menus et écrans de fin |
| `game.py` | Boucle de jeu, tir, objets, portes et statistiques |
| `survival.py` | Gestion des vagues du Déferlement |
| `network.py` / `coop.py` | Transport UDP et coopération hôte/client |
| `level.py` | Cartes, thèmes, ennemis et difficulté |
| `raycaster.py` | Rendu 3D, sprites, ciel et particules |
| `entities.py` / `ai.py` | Joueur, ennemis, objets et comportements |
| `weapons.py` | Armes et améliorations |
| `hud.py` | Interface de jeu et minimap |
| `particles.py` / `sounds.py` | Effets visuels et audio |
| `assets.py` | Chargement des PNG et fallback procédural |

## Étendre le jeu

- **Arme** : ajouter un `WeaponSpec` dans `weapons.py` et les sprites
  `fp_<id>` / `pickup_<id>`.
- **Niveau** : ajouter une grille et sa configuration dans `LEVELS`
  (`level.py`).
- **Décor** : ajouter un sprite `prop_<id>`, une entrée dans `PROP_SPECS`
  et un caractère dans `PROP_CHARS`.
- **Ennemi** : hériter d'`Enemy` dans `entities.py` ; l'IA existante est
  réutilisable.
- **Texture** : modifier ou ajouter les PNG dans `assets/` ; le fallback
  procédural reste optionnel.
