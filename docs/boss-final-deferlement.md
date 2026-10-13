# Boss final du Déferlement — conception (non codé)

Statut : **préparation uniquement**. Aucune ligne de jeu n'existe pour ce boss ;
`tests/test_deferlement_rework.py` vérifie qu'aucune classe `FinalBoss` n'a été
ajoutée par erreur. Toutes les valeurs ci-dessous sont des **propositions de
départ à régler en jeu**, pas des mesures.

## Idée

Le Colosse était le Sceau. Le Déferlement est la horde qui passe par le portail.
Le boss final est **ce qui pousse la horde** : une créature géante, « le
Gardien du Seuil » (nom provisoire), qui sort du portail central à la fin de la
vague 30. Battre ce boss donne la victoire du mode, au lieu de la simple fin
de la vague 30.

## Déroulé proposé

1. La vague 30 se joue normalement. Quand elle est nettoyée (ou à la
   submersion), aucune vague 31 n'arrive : le portail s'emballe (particules,
   tremblement d'écran, musique).
2. Le Gardien émerge du portail (`SurvivalGame._portal_center()`), avec la même
   poussée de sortie que les autres ennemis (`emerge`), mais lente.
3. Combat en trois phases, sur le modèle de `Boss` (seuils 2/3 et 1/3 de vie,
   `sync_phase_from_health`, annonces HUD et packs de soin aux transitions).
4. Victoire quand il meurt : `outcome = "victory"`, score `wave:boss` à prévoir.

## Phases proposées

| Phase | Vie | Attaques | Renforts |
| --- | --- | --- | --- |
| 1 | 100 % → 66 % | Balayage frontal (cône), tirs lents à forte dispersion | Aucun |
| 2 | 66 % → 33 % | + onde de choc circulaire annoncée au sol (évitable en glissant) | 4 miliciens sortent du portail toutes les 20 s |
| 3 | 33 % → 0 | Charges du Colosse enchaînées, cadence accrue | Kamikazes par 2, plafond de `MAX_ALIVE` respecté |

Les attaques au sol réutilisent le tracé de `hazards.py` (annonce visible avant
les dégâts). La glissade (avec ou sans la carte « Glissade fantôme ») doit
toujours permettre d'esquiver une attaque annoncée.

## Points d'intégration dans le code

- **Entité** : nouvelle sous-classe de `Boss` dans `entities.py` (KIND
  `final_boss`), `IS_BOSS = True`, `IMPACT_TYPE = "armor"`. Rayon de collision
  plus grand que le Colosse (0,38) : vérifier `level.can_stand` autour du portail
  et le pathfinding sur la carte lunaire.
- **Taille à l'écran** : `SPRITE_HEIGHT` nettement supérieur à 1. Le raycaster
  plafonne la taille des billboards de très près (voir `llm.md`) : à revoir
  pour ce seul ennemi, sinon il paraîtra petit au contact.
- **Sprites** : nouveau jeu `enemy_final_boss_*` (idle, walk, walk2, fire,
  dead, vues `_back` et `_side`) au format des autres ennemis, puis passage de
  `tools/clean_sprites.py --check`. Une variante possédée se fait déjà
  automatiquement (`assets.get_possessed`).
- **Patterns** : étendre `BossPattern` (ou un `FinalBossPattern`) avec les
  états `sweep` et `shockwave` ; garder la règle « une attaque touche une seule
  fois par victime » et l'arrêt sur les murs.
- **Vagues** : `survival.py`, au lieu de `outcome = "victory"` à la vague
  `FINAL_WAVE`, démarrer la phase boss ; le HUD de vague affiche « GARDIEN ».
- **Coop LAN** : nouveau `KIND` et nouveaux états de pattern dans les
  instantanés → nouvelle version de protocole (v6) et mise à jour de
  `docs/network-protocol.md`.
- **Musique** : prévoir `assets/sound/final_boss.<ext>` et une clé de musique
  dédiée dans `sounds.MUSIC_PROFILES` / `_custom_music_path`.

## Questions ouvertes (à trancher avant de coder)

- Le Gardien remplace-t-il la vague 30 ou vient-il après ?
- Vie de base : multiple du Colosse (1 650 PV) à fixer après essais.
- Faut-il un point de non-retour (portail fermé, plus de soins au sol) ?
