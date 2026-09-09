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

Dans les menus : flèches haut/bas ou croix directionnelle pour sélectionner,
Entrée/Espace ou A (Croix) pour valider, Échap ou B (Rond) pour revenir.
Les flèches gauche/droite règlent l'option sélectionnée. La souris reste
utilisable ; déplacer le pointeur lui redonne la sélection visuelle.
La saisie d'une nouvelle adresse IP et le remappage des touches nécessitent
encore un clavier ; B annule leur saisie sans quitter le sous-menu.

En pause : Start reprend, B (Rond) retourne au menu. Une pause imposée par
l'hôte est indiquée « PAUSE HÔTE » et seul l'hôte peut la lever. Après une
pause ou un changement de partie, relâcher les gâchettes avant de tirer ou
viser à nouveau. A (Croix) passe la caméra de mort après son verrou de trois
secondes. F3 affiche les FPS du rendu, indépendamment de la simulation à 60 Hz.

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

Le mode accepte un hote et trois clients sur UDP/5577. Le protocole v4 refuse
explicitement toute autre version. L'hote valide deplacements, collisions,
roulades, cadence, chargeurs et degats.

## Points techniques

Colosse : annonce de 1,2 s avant une charge rectiligne, puis 1,2 s de
récupération. Dès la phase 2, il alterne avec une frappe sur une zone verrouillée
de rayon 1,8 m. Sortez du tracé au sol ou utilisez la fenêtre d'invulnérabilité
de roulade. Murs et obstacles arrêtent la charge ; chaque attaque ne touche
qu'une fois chaque joueur. Les deux packs de changement de phase sont conservés.

Bestiaire : Résistant (bleu : +35 % vie, -10 % vitesse), Traqueur (rouge :
+15 % vitesse, délai entre tirs -10 %), Commandant (doré : cadence des alliés
à moins de 5 m accélérée de 25 % avec ligne de vue). Éliminez le Commandant
pour supprimer son aura. Trois élites et un Commandant vivants au maximum.
Ils apparaissent dans l'Entrepôt ; en Déferlement, élites dès la vague 4 et
Commandant aux vagues 5/15/25. Les boss ne reçoivent ni aura ni variante élite.

Secours coop : un joueur à terre peut être réanimé pendant 20 s. Approchez à
1,4 m puis Interagir (E/LB/ACT.) pour commencer un secours de 3 s ; rester près
de lui. Dégâts, roulade, perte de vue ou nouvel appui annulent le secours. Le
tir est bloqué pendant l'action. Réanimation sur place à 40 PV et 2 s de bouclier.
Sans secours, réapparition au spawn après 6 s supplémentaires à 60 PV. Si toute
l'équipe tombe, la partie est perdue. Signal : C (remappable), Back/View ou
SIG. en tactile ; durée 5 s, délai 2 s, portée 12 m, quatre marqueurs maximum.

Déferlement : dès la vague 4, un mutateur annoncé fait varier les vagues par
groupes de trois : assaut rapide (+15 % vitesse), blindés (+20 % vie, -10 %
vitesse), tirs croisés (certains miliciens remplacés par des soldats).
Les vagues 10/20/30 sont neutres ; les ennemis des vagues précédentes conservent
leurs effets. Le plafond reste de 24 ennemis vivants, sans hausse de leurs dégâts.

Améliorations de partie : après les deux interactions de l'Entrepôt, ou chaque
troisième vague nettoyée, choisir une des trois cartes avec F5–F7, gauche/haut/
droite sur la croix manette, clic ou tactile. Après 12 s, le premier choix est
retenu. Impact, recharge, capacité, précision et cadence ont deux niveaux au
maximum ; six choix par partie. Aucun bonus n'est enregistré dans les sauvegardes.
La capacité supplémentaire se remplit au prochain rechargement. La pause de
l'hôte fige le délai ; une pause locale d'un client ne suspend pas la partie.

- simulation a pas fixe de 60 Hz, rendu decouple jusqu'a 120 Hz ;
- raycasting multi-couches, murs variables, portes, z-buffer et billboards ;
- IA avec perception, BFS, couverture, contournement et esquives ;
- cache billboards LRU borne a 64 Mio et cache mural FIFO incremental ;
- UDP compresse, fragmente en datagrammes de 1 200 octets maximum, reassemble
  avec limites de taille/temps et limite par adresse source ;
- protocole sequence, evenements fiables acquittes et inventaire autoritaire ;
- ressources resolues en mode source, wheel et PyInstaller ;
- 113 tests et seuil de couverture CI de 70 %.

Des fichiers audio `menu`, `survival`, `reload` et `1` a `5` peuvent etre
places dans `assets/sound/` aux formats OGG, MP3, WAV ou FLAC.

## Architecture

Évolution gameplay en cours : le moteur déclaratif `objectives.py` fournit
interaction, déplacement vers une zone, défense chronométrée et élimination.
L'Entrepôt demande de récupérer le manifeste, désactiver l'alarme du bureau,
puis tenir l'extraction pendant 8 secondes consécutives. Les balises vertes
et le HUD guident le parcours. Interagir : **E** (remappable), **LB** ou bouton
tactile **ACT.** ; la roulade bloque l'interaction. Quitter la zone remet le
compteur à zéro, la pause le fige. Les autres niveaux gardent leur victoire
par élimination. Dans le menu LAN, **Héberger (Mission Entrepôt en coop)**
permet de jouer cette mission à quatre ; rejoindre charge automatiquement
la bonne carte. La progression est commune, même en arrivant en cours de partie.
Tous les participants doivent utiliser le protocole v4 de cette version.

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
