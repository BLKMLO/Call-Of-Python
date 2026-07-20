# Call of Python — contexte de reprise GPT

Dernière mise à jour : 20 juillet 2026. Dépôt `BLKMLO/Call-Of-Python`,
branche distante de travail `claude/call_of_python_LLM`.

## Corrections de la passe combat et environnements

- Le sniper conserve sa pose de mise en joue à genou mais son anticipation
  passe de `1.25` à `0.75` seconde (`Sniper.AIM_DELAY`). Le cooldown de
  `2.3` secondes commence toujours après le tir : seule la télégraphie avant
  le coup est raccourcie.
- Les frames de tir de `grunt`, `soldier`, `heavy`, `boss` et du coéquipier
  `ally` ont été régénérées en vue strictement frontale. Arme et flash sont
  orientés vers le joueur ; chaque silhouette reste alignée au sol et garde
  une hauteur proche de sa frame `idle`, pour éviter tout pivot ou saut
  d'échelle au tir. Le kamikaze n'est pas concerné car il ne tire jamais.
- Le Laboratoire emploie trois textures dédiées claires :
  `wall_lab_tech.png`, `wall_lab_metal.png` et
  `wall_lab_reinforced.png`. Elles ne remplacent pas les murs historiques
  partagés avec les autres niveaux. `wall_sealed_portal.png` est lui aussi
  intégré à cette enceinte blanche, tout en gardant sa brèche verte enchaînée.
- Les niveaux terrestres ont désormais un panorama de nuages teinté par leur
  horizon. Il est généré une seule fois par niveau/résolution, boucle avec la
  rotation de la caméra et ne demande que deux blits par frame. Tout niveau
  dont la configuration contient `stars` — actuellement la Lune — le
  désactive automatiquement. La clé optionnelle `clouds: false` permet aussi
  de le couper explicitement dans un futur niveau.
- Vérification visuelle effectuée à `960x540` sur les cinq tirs, le
  Laboratoire et la Lune. La mesure SDL factice sur 120 frames n'a montré
  aucun coût marginal mesurable du panorama nuageux.

## Corrections de la passe précédente

- `assets/prop_car.png` a été régénéré : berline complète, avant droit non
  tronqué, contenu opaque `176x67` dans une toile transparente `192x80` avec
  marge sur les quatre côtés. La largeur monde reste `1.10`.
- `assets/prop_bench.png` est désormais un siège parlementaire individuel
  avec pupitre, et non une banquette double massive. Sa largeur monde passe de
  `0.97` à `0.46` dans `entities.PROP_SPECS`.
- Dans `MAP_LAB`, l'ancienne porte `(23, 14)` n'était reliée à une cloison que
  par son côté gauche. Elle est remplacée par un mur métallique `2` : toutes
  les portes restantes sont encadrées par des murs sur un axe.
- `ai.cover_adjusted_chance()` conserve la précision normale à exposition
  complète, mais renforce légèrement le couvert : facteur
  `0.28 + 0.72 * exposure` au lieu de `0.35 + 0.65 * exposure`.
- Le sniper possède `AIM_DELAY = 0.75`. Lorsque son arme est prête, il passe
  en `aiming`, s'immobilise et utilise `assets/enemy_sniper_aim.png` (un genou
  au sol). Le tir part à la première frame après 0,75 s. Perdre la ligne de
  vue, se replier au corps à corps, changer d'état, mourir ou perdre la cible
  annule la visée ; aucun tir ne reste stocké derrière un mur.
- La pose à genou a été régénérée pour corriger l'anatomie puis replacée en
  vue strictement frontale : genou gauche au sol, pied droit planté, épaules
  face caméra et canon raccourci pointé vers le joueur. La frame
  `enemy_sniper_fire.png` a été refaite dans la même pose avec un flash centré,
  afin d'éviter un pivot de profil au moment du tir. Ne pas réutiliser les
  versions intermédiaires avec deux pieds droits ou un long canon latéral.
- La coop transmet `aiming` comme neuvième champ de chaque ennemi. Le client
  accepte toujours les anciens instantanés à huit champs et affiche la pose
  du sniper sur les deux machines.
- Le fallback procédural `enemy_sniper_aim` est enregistré dans `assets.py` ;
  il ne remplace jamais le PNG livré tant que celui-ci existe.

## Invariants à préserver

- Les dimensions physiques des props reposent sur la boîte opaque, via
  `_height_for_visible_width`; ne pas compenser les marges transparentes en
  augmentant arbitrairement `SPRITE_HEIGHT`.
- Les poses à genou `aim` et `fire` sont contenues dans une toile `64x96`, avec
  une silhouette opaque plus basse (`44x74`, alignée au sol). Le moteur garde
  donc les pieds au sol et le personnage paraît réellement agenouillé sans
  modifier le raycaster.
- Le délai de 0,75 s s'ajoute au temps entre deux tirs (`FIRE_DELAY = 2.3`) :
  le cooldown commence après le tir, pas au début de la mise en joue.
- Une exposition de `1.0` ne doit jamais être pénalisée par le bonus de
  couvert. L'exposition est bornée entre `0.0` et `1.0`.
- Toute évolution de l'état réseau ennemi doit rester tolérante aux
  instantanés plus courts afin qu'un client mis à jour ne plante pas avec un
  hôte plus ancien.

## Validation disponible

`tests/test_requested_changes.py` contient 13 tests et couvre : marges de la
voiture, conception et échelle du siège, topologie des portes et blancheur des
murs du laboratoire, courbe de couvert, délai/annulation/pose du sniper,
compatibilité coop 8/9 champs, stabilité d'échelle des cinq tirs frontaux et
présence/absence correcte des nuages sur Terre/la Lune.

Commande utilisée :

```bash
PYTHONPATH=/tmp/call-of-python-pygame:. \
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
python -m unittest discover -s tests -v
```

Des rendus supplémentaires en vidéo SDL factice valident le Laboratoire, le
ciel lunaire et chaque nouvelle frame de tir à sa taille projetée en jeu.

## Portails (20 juillet 2026)

- Le portail lunaire utilise quatre PNG `assets/prop_portal_0..3.png`. La
  classe `Prop` sélectionne une frame toutes les `110 ms` avec
  `pygame.time.get_ticks()`. Les surfaces et leurs mises à l'échelle sont
  mises en cache : aucune rotation/composition n'est faite pendant le rendu.
- Les quatre frames font `79x117`, partagent la même boîte opaque
  (`78x115`) et gardent l'anneau immobile ; seul le vortex vert tourne et
  pulse. Le portail ne doit pas être retourné selon la parité de sa case.
- Dans `MAP_LAB`, le mur `(28, 18)`, derrière l'épaule du Colosse placé en
  `(25, 19)`, devient le caractère `4` / `wall_sealed_portal`. La texture
  montre un petit trou vert barré de chaînes : le Colosse est visuellement le
  Sceau qui retient le futur Déferlement. Ne pas le remettre en `(28, 19)` :
  dans l'axe central, le billboard du boss le masque entièrement.
- Ce mur spécial reste solide pour déplacements, tirs et pathfinding. Sa
  hauteur volontairement standard (`1.0`) en fait un panneau en retrait devant
  le mur technique extérieur et évite de répéter verticalement le petit sceau.
- Les animations de props sont locales et purement visuelles ; elles ne sont
  pas ajoutées aux instantanés coop.
