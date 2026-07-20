# Call of Python — contexte de reprise GPT

Dernière mise à jour : 20 juillet 2026. Dépôt `BLKMLO/Call-Of-Python`,
branche distante de travail `claude/call_of_python_LLM`.

## Corrections de cette passe

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
- Le sniper possède `AIM_DELAY = 1.25`. Lorsque son arme est prête, il passe
  en `aiming`, s'immobilise et utilise `assets/enemy_sniper_aim.png` (un genou
  au sol). Le tir part à la première frame après 1,25 s. Perdre la ligne de
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
- Le délai de 1,25 s s'ajoute au temps entre deux tirs (`FIRE_DELAY = 2.3`) :
  le cooldown commence après le tir, pas au début de la mise en joue.
- Une exposition de `1.0` ne doit jamais être pénalisée par le bonus de
  couvert. L'exposition est bornée entre `0.0` et `1.0`.
- Toute évolution de l'état réseau ennemi doit rester tolérante aux
  instantanés plus courts afin qu'un client mis à jour ne plante pas avec un
  hôte plus ancien.

## Validation disponible

`tests/test_requested_changes.py` couvre : marges de la voiture, conception et
échelle du siège, topologie des portes du laboratoire, courbe de couvert,
délai/annulation/pose du sniper et compatibilité coop 8/9 champs.

Commande utilisée :

```bash
PYTHONPATH=/tmp/call-of-python-pygame:. \
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
python -m unittest discover -s tests -v
```

Un smoke test supplémentaire instancie et rend le niveau Laboratoire complet
en vidéo SDL factice (800×600), avec un sniper forcé en pose `aiming`.
