# Call of Python — FPS Python / pygame

FPS rétro en pseudo-3D (raycasting), solo ou coop LAN jusqu'à 4 joueurs :
campagne de cinq missions, mode survie de 30 vagues, quatre armes évolutives.
Version gameplay **0.6.0**. Détails : [règles et équilibrage](docs/gameplay.md).

## Installation

```bash
python -m pip install .
call-of-python        # ou : python main.py depuis un clone
```

Python 3.12 + pygame 2.6.1. Les tags produisent des builds Windows/Linux via
GitHub Actions. `python assets.py` génère les visuels manquants
(`--force-procedural` remplace les PNG existants).

## Contrôles

| Action | Clavier / souris | Manette |
|---|---|---|
| Déplacement / vue | ZQSD / souris | Sticks gauche / droit |
| Tir / mise en joue | Clic gauche / droit | Gâchette droite (ou RB) / gauche |
| Glissade | Maj | A / Croix |
| Recharger | R | X / Carré |
| Changer d'arme | 1–4, molette | Y / Triangle |
| Interagir / réanimer | E | LB |
| Grenade | G | Clic stick droit |
| Signal coop | C | Back / View |
| Cartes d'amélioration | F5–F8 | Croix directionnelle |
| Pause / FPS / plein écran | Échap / F3 / F11 | Start |

Touches remappables ; commandes tactiles disponibles. Menus : flèches ou
croix, Entrée/A pour valider, Échap/B pour revenir.

## Modes

**Campagne** — Entrepôt, Métropole, Gouvernement, Base militaire, Laboratoire.
L'arsenal est conservé. L'Entrepôt (jouable aussi en LAN) a des objectifs :
manifeste, alarme, puis 8 s d'extraction. Les autres missions se gagnent par
élimination. Colosse final en trois phases.

**Le Déferlement** — 30 vagues sortant d'un portail, Colosse aux vagues 10/20/30,
Commandant aux vagues 5/15/25. Délai avant submersion : 30 s, −10 % par vague,
plancher 8 s (1-10), 6 s (11-20), 4 s (21-30) ; **+10 s si un Colosse est dans
la vague**. Vague nettoyée : 7 s de répit et +12 PV ; sinon la suivante arrive
par-dessus. En coop LAN : mutateurs et élites dès la vague 4.

## Mécaniques

- **Glissade** : 4,5 cases, tir possible, 0,30 s d'invulnérabilité.
- **Grenades** : 2 charges, fusée 2 s, rayon 2,7 m, bloquées par les murs.
- **Améliorations** : choix d'une carte sur 4 (3 d'arme, 1 hors arme) après les
  objectifs de l'Entrepôt ou toutes les 3 vagues nettoyées (2 en solo).
- **Secours coop** : 20 s pour réanimer un allié (3 s près de lui) ; sinon
  réapparition après 6 s. Toute l'équipe à terre = défaite.
- **Ennemis** : sept archétypes, élites Résistant / Traqueur, Commandant (aura
  de cadence), Colosse (charge et frappe de zone).
- **Score** partagé en coop, grade D à S.

## Technique

Simulation 60 Hz et rendu jusqu'à 120 Hz, IA (BFS, couverture), réseau UDP
port 5577, protocole v5, hôte autoritaire. Voir
[architecture](docs/architecture.md), [protocole](docs/network-protocol.md),
[distribution](docs/distribution.md).

| Fichier | Rôle |
|---|---|
| `main.py`, `runtime.py` | États, rendu, horloge |
| `game.py`, `survival.py`, `objectives.py` | Missions, vagues, objectifs |
| `entities.py`, `ai.py`, `weapons.py` | Entités, IA, armes |
| `raycaster.py`, `hud.py`, `particles.py` | Rendu et interface |
| `network.py`, `coop.py` | Réseau LAN |
| `settings.py`, `menu.py`, `gamepad.py`, `touch_controls.py` | Config et entrées |
| `assets.py`, `resources.py`, `sounds.py` | Ressources et audio |

## Développement

```bash
python -m pip install ".[dev]"
ruff check .
python -m coverage run -m unittest discover -s tests && python -m coverage report
python -m pip install ".[build]" && python -m PyInstaller --clean --noconfirm call_of_python.spec
```

Licence [MIT](LICENSE).
