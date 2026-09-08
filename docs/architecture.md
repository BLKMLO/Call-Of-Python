# Architecture

`main.py` pilote les ecrans et le rendu. En partie, `FixedStepClock` transforme
le temps de rendu en pas constants de 1/60 s. Le rendu reste libre et ne
modifie pas l'etat de jeu.

Le compteur `game.fps` est alimenté par `pygame.time.Clock.get_fps()` dans
la boucle de rendu, jamais par `1 / dt` dans la simulation fixe. Il vaut zéro
avant les premiers échantillons SDL et inclut la limitation de rendu à 120 Hz.

`MenuBase` conserve une sélection par identifiant, ignore les séparateurs et
réutilise `on_click` pour les actions clavier/manette. Aucun faux événement
clavier n'est envoyé au remappage depuis la manette. La saisie IP reste au
clavier, avec validation/annulation accessibles à la manette.

`main.py` ouvre le contrôleur des menus, le ferme avant la création d'une
partie et le rouvre au retour ou à la transition de fin. Les contrôleurs de
partie gardent leur cycle de vie existant. `reset_gameplay_input` purge
souris, tactile, actions manette et tirs clients en attente lors des pauses,
reprises et pertes de focus. Les gâchettes doivent revenir au repos pour
être réarmées. Le client purge aussi lors de la levée d'une pause hôte.
La simulation réseau continue pendant la pause locale ; le protocole v3,
les séquences et la validation autoritaire ne changent pas.

Responsabilites principales :

- `game.py` orchestre une mission ;
- `survival.py` ajoute les vagues et le directeur de pression ;
- `entities.py`, `weapons.py` et `ai.py` portent les regles ;
- `raycaster.py`, `hud.py`, `particles.py` et `sounds.py` produisent la vue ;
- `network.py` ne connait que le transport ;
- `coop.py` porte l'autorite hote et la replication ;
- `difficulty.py`, `runtime.py` et `version.py` centralisent les politiques.

## Invariants

- axe Y vers le bas, angle croissant vers la droite ;
- ADS par post-traitement, jamais par changement de FOV a chaque image ;
- cache mural FIFO a eviction unitaire ; cache billboards LRU borne en octets ;
- nouveaux champs reseau ajoutes en fin de ligne ;
- l'hote calcule vie, munitions, cadence, degats, roulades et collisions ;
- les visuels proceduraux n'ecrasent le pack qu'avec `--force-procedural`.

Une evolution du protocole modifie `PROTOCOL_VERSION`, la documentation et les
tests adversariaux dans la meme PR. Une option persistante est validee et
bornee dans `Settings.load()`.
