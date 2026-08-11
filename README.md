# Call of Python — FPS Python / pygame

FPS retro en pseudo-3D par raycasting, jouable en solo et en cooperation LAN.
Le jeu propose une campagne de cinq missions, un mode survie de 30 vagues,
six archetypes ennemis, quatre armes evolutives et une direction pixel-art
militaire/SF.

## Installation

```bash
python -m pip install .
call-of-python
```

Le lancement depuis un clone reste possible avec `python main.py`. La
combinaison supportee est Python 3.12 avec pygame 2.6.1. Les tags produisent
aussi des distributions autonomes Windows et Linux dans GitHub Actions.

Le pack PNG livre est toujours prioritaire. `python assets.py` genere
uniquement les fichiers absents. Seule la commande suivante remplace les
visuels existants par les anciens fallbacks proceduraux :

```bash
python assets.py --force-procedural
```

## Controles

| Action | Clavier / souris | Manette SDL |
|---|---|---|
| Deplacement | ZQSD | Stick gauche |
| Vue | Souris | Stick droit |
| Tir | Clic gauche | Gachette droite ou RB |
| Mise en joue | Clic droit | Gachette gauche |
| Roulade | Maj | A / Croix |
| Recharger | R | X / Carre |
| Changer d'arme | 1–4 ou molette | Y / Triangle |
| Pause | Echap | Start |
| FPS | F3 | — |
| Plein ecran | F11 | — |

Les touches clavier sont remappables. Les manettes Xbox, PlayStation et
compatibles passent par les mappings SDL, avec zone morte et vibration courte
sur les degats. Les commandes tactiles multi-doigts restent disponibles.

Les Parametres exposent aussi : volumes separes, sensibilite, FOV 60–90 degres,
secousses de camera 0/50/100 %, ADS en maintien ou bascule et trois difficultes.

## Modes

### Campagne

Entrepot, Metropole, Gouvernement, Base militaire puis Laboratoire. L'arsenal
est conserve entre les missions. Le Colosse final possede trois phases et
libere deux packs de vie avant de reveler le portail lunaire.

### Le Deferlement

Trente vagues lunaires de creatures possedees, avec submersion progressive,
ravitaillement periodique et un Colosse toutes les dix vagues. Un directeur
ajuste legerement la cadence d'apparition selon la sante du joueur et la
pression deja presente ; il ne modifie jamais les degats, la composition ou
le nombre d'ennemis prevu.

Le mode accepte un hote et trois clients sur UDP/5577. Le protocole v3 refuse
explicitement toute autre version. L'hote valide deplacements, collisions,
roulades, cadence, chargeurs et degats.

## Points techniques

- simulation a pas fixe de 60 Hz, rendu decouple jusqu'a 120 Hz ;
- raycasting multi-couches, murs variables, portes, z-buffer et billboards ;
- IA avec perception, BFS, couverture, contournement et esquives ;
- cache billboards LRU borne a 64 Mio et cache mural FIFO incremental ;
- UDP compresse, fragmente en datagrammes de 1 200 octets maximum, reassemble
  avec limites de taille/temps et limite par adresse source ;
- protocole sequence, evenements fiables acquittes et inventaire autoritaire ;
- ressources resolues en mode source, wheel et PyInstaller ;
- 89 tests et couverture globale superieure au seuil CI de 70 %.

Des fichiers audio `menu`, `survival`, `reload` et `1` a `5` peuvent etre
places dans `assets/sound/` aux formats OGG, MP3, WAV ou FLAC.

## Architecture

| Fichier | Role |
|---|---|
| `main.py`, `runtime.py` | Etats, rendu et horloge fixe |
| `game.py`, `survival.py` | Gameplay de mission et vagues |
| `difficulty.py` | Profils et directeur de pression |
| `entities.py`, `ai.py`, `weapons.py` | Entites, comportements et arsenal |
| `raycaster.py`, `hud.py`, `particles.py` | Rendu du monde et interface |
| `network.py`, `coop.py`, `version.py` | Transport et replication LAN |
| `settings.py`, `menu.py` | Configuration et ecrans |
| `gamepad.py`, `touch_controls.py` | Manette et tactile |
| `assets.py`, `resources.py`, `sounds.py` | Ressources et audio |

Voir [`docs/architecture.md`](docs/architecture.md),
[`docs/network-protocol.md`](docs/network-protocol.md) et
[`docs/distribution.md`](docs/distribution.md).

## Qualite et distribution

```bash
python -m pip install ".[dev]"
ruff check .
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
python -m pip wheel . --no-deps --wheel-dir dist
```

Executable local :

```bash
python -m pip install ".[build]"
python -m PyInstaller --clean --noconfirm call_of_python.spec
```

Le projet est distribue sous licence [MIT](LICENSE).
