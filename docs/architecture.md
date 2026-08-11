# Architecture

`main.py` pilote les ecrans et le rendu. En partie, `FixedStepClock` transforme
le temps de rendu en pas constants de 1/60 s. Le rendu reste libre et ne
modifie pas l'etat de jeu.

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
