# Call of Python — FPS Python / pygame

FPS rétro en pseudo-3D (raycasting), solo ou coop LAN jusqu'à 4 joueurs :
campagne de cinq missions, mode survie de 30 vagues, quatre armes évolutives.
Version gameplay **0.7.0**. Détails : [règles et équilibrage](docs/gameplay.md).

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

**Campagne** — chaque niveau a sa mission :

| Niveau | Mission |
|---|---|
| Entrepôt | Manifeste, alarme, 8 s d'extraction |
| Métropole | Balise de détresse, tenir le carrefour 30 s sous les renforts, hélicoptère |
| Gouvernement | Trois dossiers, libérer l'otage et l'escorter (les ennemis le visent ; s'il meurt, mission échouée) |
| Base militaire | Saboter trois batteries avant le lancement des missiles (150 s en Soldat), renforts à chaque sabotage, exfiltration |
| Laboratoire | Couper trois générateurs qui rendent le Colosse invulnérable, puis l'abattre |

L'arsenal est conservé d'un niveau à l'autre ; chaque interaction de mission
donne une carte d'amélioration.

**Le Déferlement** — 30 vagues sortant d'un portail, Colosse aux vagues 10/20/30,
Commandant aux vagues 5/15/25. Délai avant submersion : 30 s, puis par vague
−3 % en Recrue (12,4 s à la vague 30), −6 % en Soldat (5,0 s) et −10 % en Vétéran
(plancher de 4 s atteint dès la vague 21) ; planchers 8/6/4 s par tranche de 10 vagues ;
**+10 s si un Colosse est dans la vague**. Dès la vague 7, un soldat sur trois porte un bouclier frontal ;
dès la vague 8, une vague sur quatre amène un essaim de kamikazes rapides.
Des **contrats** optionnels (vagues 2, 5, 8…, ex. « 5 kamikazes au fusil à
pompe ») rapportent une carte bonus.

**Difficulté** (menu principal ou Paramètres ; le menu change de couleur :
vert Recrue, ambre Soldat, rouge Vétéran) :

| | Recrue | Soldat | Vétéran |
|---|---|---|---|
| Vie / dégâts ennemis | ×0,82 / ×0,72 | ×1 / ×1 | ×1,22 / ×1,28 |
| Ennemis par vague | ×0,8 | ×1 | ×1,25 |
| Délai de submersion par vague | −3 % | −6 % | −10 % |
| PV par vague nettoyée / entre niveaux | 20 / 55 | 12 / 40 | 6 / 25 |
| Bouclier d'arrivée | 4 s | 3 s | 2 s |
| Pack de vie (Déferlement) | chaque vague | toutes les 2 | toutes les 3 |
| Repos du Colosse | ×1,2 | ×1 | ×0,75 |
| Renforts / comptes à rebours | ×0,75 / ×1,25 | ×1 / ×1 | ×1,5 / ×0,8 | Vague nettoyée : 7 s de répit et +12 PV ; sinon la suivante arrive
par-dessus. En coop LAN : mutateurs et élites dès la vague 4.

## Armes

| Arme | Rôle |
|---|---|
| Pistolet | Perce le blindage (×1,4 contre lourds et Colosse), ×1,75 en visée complète |
| Fusil à pompe | ×1,5 à moins de 2 m, étourdit 0,5 s et repousse (baisse les boucliers) |
| Fusil d'assaut | Polyvalent |
| Minigun | Munitions illimitées mais surchauffe (70 tirs, refroidissement 2,2 s), 0,4 s de lancement, déplacement ×0,65 en tirant, ×0,6 contre le blindage |

Un bouclier levé ne laisse passer que 15 % des dégâts de face : contourner,
grenade ou fusil à pompe. Cartes propres à chaque arme : Balles explosives
(pistolet), Chevrotine lourde (pompe), Perforantes (fusil), Refroidissement
(minigun).

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
port 5577, protocole v6, hôte autoritaire. Voir
[architecture](docs/architecture.md), [protocole](docs/network-protocol.md),
[distribution](docs/distribution.md).

| Fichier | Rôle |
|---|---|
| `main.py`, `runtime.py` | États, rendu, horloge |
| `game.py`, `survival.py`, `objectives.py`, `missions.py` | Missions, vagues, objectifs |
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
