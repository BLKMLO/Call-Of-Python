# Architecture

`BossPattern` produit les transitions annonce/charge/frappe/récupération.
`Game._tick_boss` remplace l'IA standard seulement pendant une séquence active ;
l'IA et les stats de phase existantes restent actives entre ces séquences.
La charge découpe ses déplacements en pas <=0,1 m et les impacts sont dédupliqués
par victime. `hazards.py` projette le tracé au sol avant l'ADS et vérifie le
z-buffer. Les clients n'avancent pas les patterns ; ils affichent leur instantané.

`elites.py` applique une fois les variantes et recalcule l'aura booléenne du
Commandant. L'IA multiplie uniquement le délai du prochain tir ; dégâts, seuils
du boss et délais existants de sniper/roulade sont conservés. `sprite_kind`
sépare l'archétype réseau des PNG réutilisés (Commandant = silhouette soldat).
Les variantes dérivées occupent un cache LRU de 128 surfaces maximum.

`coop_support.Rescue` gère les timers à terre et les secours. Les joueurs à
0 PV restent inactifs ; le résultat du moteur restaure 40 PV sur place ou
60 PV au spawn. Une seule progression est comptée par victime ; les helpers
ne multiplient pas la vitesse. L'hôte annule un secours client si sa dernière
entrée date de plus de 350 ms. `Pings` limite débit, durée et cardinalité des
marqueurs. `support_ui.py` rend ces états et recycle au plus quatre billboards.

`mutators.py` choisit une variation bornée avec un générateur isolé. La file
Déferlement stocke `(type, vague_origine, mutateur)` ; les multiplicateurs sont
appliqués une fois au spawn. Une submersion ne rééquilibre pas la file ancienne.
Le boss est exclu des effets. Le client reçoit l'identifiant pour l'annonce,
les positions et la vie maximale résultantes pour le rendu.

`SessionUpgrades` détient uniquement l'état de partie : récompenses dédupliquées,
tirages isolés par graine, propositions, délai fixe, niveaux plafonnés. Les effets
reconstruisent les specs d'armes depuis `WEAPON_SPECS` sans les muter ; une signature
évite de reconstruire à chaque tick. Les munitions et le ratio de recharge sont
préservés. Le joueur transféré entre niveaux porte ce contexte temporaire.
`upgrade_ui.py` partage rectangles de choix et affichage pour souris/tactile.

`objectives.py` contient les définitions immuables et la progression d'une
mission. Aucune dépendance SDL ni réseau : seul le simulateur autoritaire
appelle `interact/update`, les clients lisent les instantanés validés.

`Level.config.objectives` déclare la séquence de l'Entrepôt. `Game` vérifie la
portée et la ligne de vue, avance les timers au pas fixe et choisit la victoire
par mission si elle existe. Les cartes sans objectifs gardent l'élimination.
`MissionMarker` produit une surface réutilisée pour la balise ; le HUD rend
la direction, la distance et l'action sans modifier l'état de mission.

L'hôte LAN peut exécuter la mission Entrepôt (`mission_mode=True`) via
`Game.update`, ou les vagues via `SurvivalGame.update`. Le client charge le
monde local correspondant au mode connu du handshake. Le protocole v4 porte
les interactions acquittées et les instantanés de mission ; aucun client
ne décide de la progression. Les transitions LAN ne débloquent pas la campagne.

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
La simulation réseau continue pendant la pause locale ; le protocole v4,
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
