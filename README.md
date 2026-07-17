# Call of Python — FPS en Python / pygame (raycasting)

FPS façon rétro (rendu pseudo-3D par raycasting, comme Wolfenstein 3D),
écrit en Python 3.12 avec **pygame comme seule dépendance externe** —
y compris le multijoueur LAN (sockets UDP de la bibliothèque standard).

Les graphismes utilisent un **pixel-art militaire/SF détaillé**, conçu pour
rester lisible dans un raycaster : textures 64×64 "pliées" sur les murs,
sprites directionnels affichés en billboards, armes en vue subjective et
illustration cinématique pour les menus. Le pack PNG livré dans `assets/`
est utilisé en priorité. `assets.py` conserve un générateur procédural de
secours : `python assets.py` complète seulement les fichiers manquants ;
`python assets.py --force-procedural` restaure explicitement les anciens
visuels procéduraux.

## Lancer le jeu

```bash
pip install -r requirements.txt   # installe pygame
python main.py
```

## Contrôles (par défaut, re-mappables dans Paramètres)

| Action              | Touche       |
|---------------------|--------------|
| Avancer / reculer   | `Z` / `S`    |
| Gauche / droite     | `Q` / `D`    |
| Sprint              | `Maj` (gauche ou droite) |
| Viser (horizontal + vertical) | Souris |
| Tirer               | Clic gauche (maintien = rafale pour les armes automatiques) |
| Mise en joue (lunette) | Clic droit (maintenu) — zoom, précision accrue, déplacement ralenti |
| Changer d'arme      | `1`–`4` ou molette |
| Recharger           | `R`          |
| Compteur de FPS     | `F3`         |
| Pause               | `Échap` (puis `M` pour revenir au menu) |

Le menu **Paramètres** règle la résolution, le volume, la sensibilité de
la souris et les touches (WASD possible). Sauvegardé dans `settings.json`.

## Histoire

Cinq niveaux pour remonter la piste de l'invasion — de l'**Entrepôt** aux
rues d'une **Métropole** sous couvre-feu, du palais du **Gouvernement**
tombé à la **Base militaire**, jusqu'au **Laboratoire** où attend le
Colosse. Mais en l'abattant, vous comprenez trop tard : il n'était pas
leur champion, il était **le Sceau** — et son portail lunaire est grand
ouvert. **Le Déferlement** se joue sur la Lune : les vagues surgissent
du portail, jusqu'à la trentième.

## Gameplay

- **5 niveaux** à thèmes différents, aux cartes vastes et variées —
  **Entrepôt** (allées de rayonnages alignés, bureau, quai de
  chargement), **Métropole** (gratte-ciel élancés aux fenêtres
  allumées, voitures abandonnées, périmètre bouclé par des barrières
  anti-émeute), **Gouvernement** (hémicycle circulaire de marbre et de
  boiseries, avec le parloir et sa tribune au centre, cerné de rangées
  de pupitres), **Base militaire**, et le **Laboratoire en assaut
  final** (couloirs desservant des salles à thème — spécimens, chimie,
  serveurs, médical — jusqu'à la chambre du Colosse). Chacun a sa carte,
  ses textures, ses décors, son ambiance et sa nappe musicale, et grouille
  d'ennemis (8 à 15 par niveau) avec armes et trousses de soins pour
  tenir. Le niveau suivant se débloque quand **tous les ennemis sont
  éliminés** ; le joueur y conserve son arsenal et récupère de la vie.
  **S'il meurt, il repart de zéro**. Le meilleur niveau atteint est
  mémorisé. À l'arrivée sur un niveau (ou sur le Déferlement), un
  **bouclier temporaire** (quelques secondes, vignette bleutée) rend le
  joueur invulnérable le temps de repérer les lieux.
- **Murs à hauteurs variables** : les gratte-ciel montent jusqu'au ciel
  (×3,4, blocs pleins entre lesquels on circule), les rayonnages et la
  rotonde du Gouvernement dominent le joueur, les barrières anti-émeute
  restent basses — la texture est empilée verticalement sur toute la
  hauteur du mur. Les portes ne sont placées que dans des murs de
  hauteur normale (jamais de vide au-dessus). Le rendu se fait **en
  couches** : le sommet d'un mur haut reste visible **derrière** un mur
  plus bas (un gratte-ciel dépasse d'une salle basse au premier plan),
  avec élagage des murs entièrement masqués pour rester rapide.
- **Caméra de mort** cinématique (façon Dark Souls) : à la mort, le
  protagoniste s'effondre — la vue bascule et plonge vers le ciel, la
  scène s'assombrit, puis « VOUS ÊTES MORT » apparaît en lettres rouges
  espacées, avant l'écran de fin.
- **Soleil dynamique** : chaque niveau a son heure, de 8h (Entrepôt,
  soleil bas et chaud) à midi (au plus haut) puis 19h (Laboratoire,
  soleil rouge à l'horizon et ciel de crépuscule). Il occupe une
  position fixe dans le monde (occulté par les bâtiments) et progresse
  au fil de la campagne.
- **Mise en joue (clic droit)** : lunette avec zoom optique, réticule et
  vignette circulaire, sensibilité et dispersion fortement réduites (tir
  de précision) au prix d'un déplacement ralenti.
- **Décors** : voitures, pupitres, tribune, paillasses, rochers, portail,
  crevasses — des billboards qui bloquent les déplacements (le
  pathfinding des ennemis les contourne) mais pas les balles ni les
  regards.
- **Le Déferlement (mode survie), sur la Lune** : une plaine de régolithe
  gris **entièrement plate**, striée de crevasses luisantes, sous un
  **ciel noir étoilé qui défile avec la rotation**, avec un **portail
  vert surnaturel** au centre d'où jaillit la horde. Pas de murs : les
  **limites du monde sont un champ d'énergie invisible qui ne se
  matérialise qu'à l'approche** (comme un mur transparent). Débloqué en
  brisant le Sceau (puis accessible depuis le menu). Des vagues de plus en
  plus grosses et dures, **jusqu'à la vague 30** ; un Colosse accompagne
  la horde toutes les 10 vagues. Une vague nettoyée accorde un répit et un
  peu de vie ; mais si elle n'est pas nettoyée à temps, **la suivante
  déferle par-dessus** — la submersion guette, et de plus en plus vite :
  le délai part de 30 secondes et se réduit de 10 % à chaque nouvelle
  vague (avec un plancher de 3 secondes). Trousses de soins toutes les 3
  vagues, **packs de vie toutes les 2 vagues**, armes améliorées toutes
  les 5. Le record de vagues
  est sauvegardé.
- **Portes coulissantes automatiques** sur les cartes : elles s'ouvrent
  à l'approche (du joueur comme des ennemis — l'IA les traverse), les
  balles et les regards passent par l'entrebâillement.
- **Multijoueur LAN en coopération** sur le Déferlement : un joueur
  **héberge** (il fait tourner la partie), les autres **rejoignent** par
  son adresse IP locale (port UDP 5577). Architecture hôte-autoritaire :
  chaque client simule son propre joueur (visée sans latence) et reçoit
  ~15 instantanés/s du monde ; les coéquipiers apparaissent en uniforme
  bleu. Un joueur à terre réapparaît après quelques secondes — la partie
  n'est perdue que si tous tombent en même temps.
- **5 types d'ennemis** : milicien, soldat, soldat lourd, **kamikaze**
  (très rapide, gilet explosif : il fonce et détone au contact — ou
  quand on l'abat, avec réactions en chaîne dans une grappe) et
  **sniper** (mortel à longue portée, il recule si on l'approche) —
  **plus un boss** (le Colosse, 550 PV, barre de vie dédiée). IA :
  détection à vue, **pathfinding BFS** (ils contournent murs, piliers et
  portes), **alerte des alliés** (un ennemi qui vous repère crie, un
  coup de feu attire le secteur), patrouille au repos, repli vers un
  point de couverture quand ils sont blessés. L'intelligence est adaptée
  au type d'ennemi : le **soldat** manoeuvre par le flanc ou par les
  arrières s'il perd le joueur de vue au lieu de foncer droit sur sa
  dernière position, et lui comme le **sniper** alternent couverture et
  brèves sorties pour tirer plutôt que de rester en terrain découvert ;
  les autres (milicien, lourd, kamikaze, boss) foncent plus simplement.
  En contrepartie, un joueur qui ne dépasse que partiellement d'une
  couverture expose moins de sa silhouette et est bien plus dur à
  toucher. Leurs vie et dégâts augmentent avec les niveaux. **Sprites
  directionnels** (on les voit de face, de dos ou de profil selon leur
  orientation), animations de marche/tir, barres de vie flottantes,
  **cadavres persistants** au sol.
- **Packs de vie cachés** : un par carte, hors minimap (dont une salle
  secrète derrière une porte dans la Base militaire). Bloc blanc à croix
  rouge dont les **étincelles vertes** trahissent la présence — soin
  complet. En survie, il réapparaît à chaque vague de Colosse.
- **Statistiques de partie** : éliminations, précision et temps de jeu,
  affichés en direct au HUD et en bilan sur les écrans de fin de niveau
  et de fin de partie (cumulés sur la campagne).
- **4 armes** : pistolet de départ, puis fusil à pompe, fusil d'assaut et
  minigun **à ramasser sur les cartes**. Une arme trouvée à un niveau
  supérieur est plus puissante (« Mk. II », « Mk. III »...) ; ramasser
  une arme déjà possédée la recharge ou l'améliore. Trousses de soins au
  sol également.
- **Sensations FPS** : visée verticale à la souris (y-shearing), sprint,
  tremblement d'écran (dégâts, grosses armes), marqueurs de touche,
  viseur dynamique qui s'écarte au tir, indicateurs de direction des
  dégâts reçus.
- **Audio spatial** : sons du monde atténués avec la distance et
  panoramiqués gauche/droite (stéréo) selon la direction ; **musique
  d'ambiance procédurale** propre à chaque niveau — le tout synthétisé
  en pur Python. Deux exceptions peuvent venir de vrais fichiers audio
  dans `assets/sound/` (absent par défaut, entièrement optionnel) : le
  son de rechargement (`reload.<ext>`) et la musique de chaque niveau
  (`1.<ext>` pour le niveau 1, `2.<ext>` pour le niveau 2... `menu.<ext>`
  et `survival.<ext>` pour le menu et le Déferlement) — extensions mp3,
  ogg, wav ou flac. En l'absence de fichier, le son ou la nappe
  synthétisé sert de musique par défaut.
- **Particules** : sang à l'impact (qui s'écrase au sol), gerbe à la
  mort, poussière teintée de la texture du mur touché, fondu de sortie.
- **Performances** : colonnes de murs et sprites mis à l'échelle
  mémoïsés (cache borné à éviction FIFO incrémentale — rapide en statique,
  sans pic en rotation), ombrage et brume pré-calculés, correction de
  perspective en table, lancer de rayons optimisé, zoom de visée en
  post-traitement, ligne de vue de l'IA cadencée — 110+ FPS en 1280x720
  sur tous les niveaux, sans pic de lag.
- HUD complet : arme en vue subjective animée (balancement, recul,
  éclair de bouche + lueur chaude qui éclaire la scène, abaissée au
  rechargement), compteur de munitions (rouge quand bas, invite
  « RECHARGEZ [R] » clignotante à vide), emplacements d'armes, minimap
  (ennemis, objets), voile rouge de dégâts, compteur de FPS optionnel.

## Architecture (pensée pour être étendue)

| Fichier        | Rôle |
|----------------|------|
| `main.py`      | Point d'entrée, machine à états (menu / jeu / Sceau / Déferlement / fin), musique |
| `settings.py`  | Paramètres + persistance JSON (résolution, volume, touches, progression, records) |
| `menu.py`      | Menu principal, paramètres, fin de niveau, écran du Sceau, game over / victoire |
| `game.py`      | Boucle de gameplay : entrées, tir hitscan multi-plombs, ramassages, alertes, portes, stats |
| `survival.py`  | Le Déferlement : vagues, submersion à 60 s, apparitions par les sas, ravitaillement |
| `network.py`   | Couche LAN : datagrammes UDP + JSON, sockets non bloquantes, sans thread |
| `coop.py`      | Coop LAN : hôte autoritaire (`CoopHostGame`) et client répliqué (`CoopClientGame`) |
| `level.py`     | Cartes ASCII + niveaux (thème, ennemis, armes, décors, difficulté) + portes coulissantes |
| `raycaster.py` | Rendu : murs texturés (DDA + z-buffer), portes, y-shearing, billboards, ciel étoilé, particules |
| `entities.py`  | `Player` (arsenal, pitch), `Grunt`/`Soldier`/`Heavy`/`Boss`, `Pickup`, `Prop`, sprites directionnels |
| `ai.py`        | Machine à états des ennemis (idle / chase / attack / cover) + pathfinding BFS |
| `weapons.py`   | Specs des armes + niveaux d'amélioration (Mk. II...) |
| `hud.py`       | Arme FP, viseur dynamique, marqueurs, panneau de vagues, minimap, barre de boss |
| `particles.py` | Particules 3D (sang, impacts, poussière, surgissements) |
| `sounds.py`    | Effets + musique d'ambiance synthétisés en pur Python, stéréo positionnelle |
| `assets.py`    | Chargement du pack PNG et fallback procédural pour les fichiers manquants |

### Pistes d'extension

- **Nouvelle arme** : un `WeaponSpec` dans `weapons.py` + ses sprites
  `fp_<id>` / `pickup_<id>` dans `assets.py`.
- **Nouveau niveau** : une grille ASCII + une entrée dans `LEVELS`
  (`level.py`) — thème, composition d'ennemis, armes au sol, décors.
- **Nouveau décor** : un sprite `prop_<id>` dans `assets.py`, une entrée
  dans `PROP_SPECS` (`entities.py`) et un caractère dans `PROP_CHARS`.
- **Nouveau type d'ennemi** : hériter d'`Enemy` (`entities.py`) et
  ajouter sa palette dans `assets.py` — l'IA est réutilisable telle quelle.
- **Nouvelles textures** : éditer ou ajouter les PNG de `assets/` directement ;
  un builder dans `assets.py` peut fournir un fallback procédural optionnel.
- **Multijoueur** : le protocole de `coop.py` (instantanés JSON) est
  simple à étendre — nouveaux événements, plus de joueurs, coop sur la
  campagne, voire un mode versus.
