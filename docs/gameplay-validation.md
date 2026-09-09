# Validation gameplay 0.5.0

Chaque étape possède son commit jouable et sa recette solo/UDP loopback aux
résolutions 800×600 et 1280×720. Les tests unitaires exercent les timers au pas
fixe et les choix par graine isolée. Les captures ont été inspectées pendant
les étapes ; les rapports ci-dessous proviennent de la machine de travail.

| Étape | Médiane 800×600 (ms) | p95 (ms) | Médiane 1280×720 (ms) | p95 (ms) | UDP max (octets) |
|---|---:|---:|---:|---:|---:|
| 1 | 5.977 | 6.426 | 10.501 | 12.402 | 530 |
| 2 | 6.494 | 9.681 | 10.881 | 14.419 | 530 |
| 3 | 5.979 | 8.607 | 10.246 | 11.649 | 538 |
| 4 | 6.044 | 11.856 | 10.294 | 11.254 | 550 |
| 5 | 5.97 | 8.977 | 10.625 | 13.423 | 568 |
| 6 | 6.345 | 11.979 | 10.296 | 11.98 | 598 |
| 7 | 6.231 | 10.788 | 10.609 | 16.432 | 653 |
| 8 | 6.048 | 7.444 | 10.496 | 13.219 | 697 |
| 9 | 6.133 | 6.93 | 10.387 | 10.812 | 705 |
| 10 | 6.324 | 7.579 | 10.761 | 15.582 | 718 |

Mesure : graine 101, SDL vidéo/audio dummy, simulation + rendu, 80 images dont
20 de chauffe, 24 ennemis vivants. Le scénario intègre progressivement les
élites, le Commandant, le Colosse et une grenade active. La charge du conteneur
varie : ces valeurs ne sont ni un comparatif contrôlé ni une garantie de FPS.
Le wrapper du socket vérifie chaque datagramme envoyé dans les scénarios contre
la limite de 1 200 octets ; les tests du transport couvrent aussi la fragmentation.

Validation finale : 145 tests réussis, Ruff sans erreur, couverture 78 % avec
branches (seuil 70 %), compilation, wheel 0.5.0 construit et démarrage depuis
une installation hors du clone. La CI répète la recette sur Windows et Ubuntu ;
son résultat doit être consulté sur la PR, sans le déduire des tests locaux.

```bash
ruff check .
python -m coverage run -m unittest discover -s tests -v
python -m coverage report
python tools/validate_gameplay.py --stage 10 --output gameplay-qa
python -m pip wheel . --no-deps --wheel-dir dist
```

La recette de mission place les joueurs aux objectifs pour isoler leurs contrats.
Restent à éprouver en jeu humain : parcours complet sans téléportation, plaisir
et difficulté de l’équilibrage, commandes sur matériel tactile/manette et LAN
multi-machine avec latence réelle. Le protocole reste destiné à un LAN de confiance.
Aucune nouvelle sauvegarde de progression ni migration n’est introduite.
