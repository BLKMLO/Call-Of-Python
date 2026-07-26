# Changelog

## [Non publié] — 2026-07-25

Passe d'amélioration libre : corrections de bugs, robustesse, performances
et couverture de tests. Aucun changement de gameplay ni de rendu visuel.

### Corrections

- **Visée du sniper qui fuyait entre deux états d'IA** (`ai.py`) : les
  transitions attaque→couvert, couvert→poursuite et poursuite→veille
  n'annulaient pas l'anticipation de tir. Un sniper surpris en pleine mise
  en joue gardait la pose à genou en patrouillant et, surtout, tirait
  **instantanément** à son retour en combat, sans la télégraphie de 0,75 s.
  `cancel_aim()` est désormais appelé sur ces trois transitions, comme
  l'exigeait l'invariant documenté.
- **Rechargement automatique silencieux** (`game.py`, `coop.py`) : vider le
  chargeur lançait bien le rechargement, mais sans le son — seul le
  rechargement manuel (touche R) était audible.
- **Roulade encore possible après la victoire** (`game.py`) : pendant le
  délai de fin de niveau, toutes les actions étaient gelées sauf la
  roulade ; elle suit maintenant la même garde `outcome is None`.
- **Textes « 50 vagues » obsolètes** : le mode survie se termine à la
  vague 30 (`FINAL_WAVE`) depuis longtemps, mais le sous-titre de victoire
  (`main.py`), l'écran du Sceau (`menu.py`) et les docstrings de
  `survival.py` parlaient encore de 50 vagues. Le sous-titre est maintenant
  construit depuis `FINAL_WAVE`.

### Robustesse

- **`settings.py` : crash au démarrage sur JSON profondément imbriqué.**
  La limite de 64 KiB autorisait ~30 000 niveaux d'imbrication, au-delà de
  la limite de récursion de Python : `RecursionError` n'était pas intercepté
  et le jeu plantait au lancement. Il est maintenant attrapé (comme dans
  `network.py`) et un test de régression verrouille le cas.
- **`network.py` : double bind UDP silencieux sous Windows.** `SO_REUSEADDR`
  y laissait un second processus écouter le port 5577 en même temps que
  l'hôte, avec répartition aléatoire des datagrammes entre les deux.
  `SO_EXCLUSIVEADDRUSE` est utilisé sous Windows : le second hôte échoue
  proprement (« port déjà utilisé »). `SO_REUSEADDR` est conservé ailleurs.
- **`menu.py` : polices reconstruites à chaque frame.** Chaque menu créait
  5 à 10 objets `SysFont` par frame (recherche et chargement du fichier de
  police). Elles sont maintenant mutualisées dans un cache module-level
  (`_sysfont`), comportement visuel identique.

### Performances (rendu visuel strictement identique)

- **`hud.py`** : les icônes des emplacements d'armes étaient remises à
  l'échelle à chaque frame → cache par arme ; les libellés statiques
  (« INTÉGRITÉ », nom d'arme, chiffres 1-4, titre du niveau, « LE COLOSSE »)
  étaient re-rendus 60×/s → cache borné (256 entrées) invalidé avec les
  polices dans `resize()` ; la minimap copiait toute sa surface de fond
  chaque frame → la base statique est blittée directement, seuls les points
  mobiles sont dessinés par-dessus.
- **`particles.py`** : la liste des particules n'est reconstruite que
  lorsqu'une particule expire (plus d'allocation par frame entre les
  combats).
- **`game.py`** : les bascules de caméra (roulade et caméra de mort)
  copiaient tout l'écran avant `rotozoom`, qui ne fait que lire sa source
  → copie plein écran supprimée sur les deux chemins.
- **`raycaster.py`** :
  - `zoom_screen()` (mise en joue) allouait une surface ~½ mégapixel à
    chaque frame → tampon unique réutilisé, réalloué seulement si la taille
    change ;
  - le caractère de texture de repli (`next(iter(tex_cols))`) était
    reconstruit pour chaque colonne de mur → calculé une fois dans
    `set_level()` ;
  - le fondu des murs d'énergie (limite du monde lunaire) copiait chaque
    colonne à chaque frame → alpha quantifié par pas de 16 et variantes
    estompées mémoïsées sous une clé dédiée du cache FIFO (la surface
    partagée du chemin opaque n'est jamais mutée).

### Tests

- **`tests/test_smoke.py` (nouveau, 8 tests)** : comble la dette documentée
  des smoke tests historiques jamais commités. Couvre le boot (réglages,
  banque de sons avec et sans mixer), la campagne (120 frames, mort avec
  caméra cinématique jusqu'à `finished`, victoire), le Déferlement (départ
  des vagues, `spawn_queue` en `deque`, `survival_info`), le rendu et le
  clic de tous les menus aux résolutions extrêmes, une partie coop réelle
  en loopback UDP (join → instantané → `synced`, rendu des deux côtés,
  fermeture propre des sockets), le round-trip des réglages avec JSON
  tronqué, et la lecture de tous les effets et musiques.
- **`tests/test_cleanup.py`** : +1 test (JSON imbriqué au-delà de la limite
  de récursion).
- Suite complète : **43 tests, tous verts** (contre 34 avant la passe).
