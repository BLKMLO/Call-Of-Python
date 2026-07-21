# Call of Python — contexte de reprise GPT

Dernière mise à jour : 21 juillet 2026. Dépôt `BLKMLO/Call-Of-Python`,
branche distante de travail `claude/call_of_python_LLM`.

## Équilibrage des roulades et écran de mort

- La roulade du joueur dure désormais `0.55 s` à `4.55` cases/s : sa portée
  reste donc pratiquement inchangée (~`2.5` cases) et elle n'a plus aucun
  cooldown. Une nouvelle roulade reste refusée tant que les `0.55 s` de la
  précédente ne sont pas terminées. Elle n'est pas une parade instantanée
  pendant toute l'animation : `0.08 s` d'amorce vulnérable,
  `0.30 s` d'i-frames (`0.08 <= elapsed < 0.38`), puis `0.17 s` de
  récupération vulnérable. Même en les enchaînant, ces deux fenêtres exposées
  empêchent donc une invincibilité continue. `Player.roll_invulnerable` est
  l'autorité ; `roll_invuln` reste à zéro pour préserver la forme de l'ancien
  état.
- `RemotePlayer` applique exactement la même fenêtre côté hôte et côté client.
  Une évolution future de la roulade joueur doit donc maintenir ensemble les
  constantes de `Player`, leur reprise dans `RemotePlayer`, le clamp réseau
  de `rt` et l'allocation anti-téléportation basée sur `ROLL_SPEED`. Chaque
  déclenchement client incrémente aussi `Player.roll_sequence`, envoyé sous
  `rs` : l'hôte accepte une séquence strictement plus récente et rejette les
  vieux datagrammes UDP. Pour un ancien client sans `rs`, un front `rt=0` puis
  `rt>0` est exigé. Sans cela, retirer le cooldown permettrait à un paquet
  retardé de relancer une roulade fantôme.
- Le cooldown du soldat passe de `5.0` à `3.0 s`. Avec un cooldown prêt, un
  projectile réellement encaissé pose `Enemy.hit_roll_request` et l'IA roule
  latéralement par rapport à la source au pas d'IA suivant. La demande est
  volontairement consommée après résolution du coup complet : tous les plombs
  simultanés d'un fusil à pompe infligent leurs dégâts avant l'esquive. Un
  espace trop étroit conserve la courte nouvelle tentative de `0.35 s`.
  `EnemyAI.proactive_roll_delay` décale seulement les roulades spontanées au
  premier contact (`0.6..1.8 s`) ; il ne pollue pas `roll_cooldown` et ne peut
  donc pas empêcher la première réaction à une balle.
- L'écran de mort n'emploie plus les grandes lettres rouges espacées ni une
  surface/glyphe recréé chaque frame. `HUD.resize()` prépare un panneau sombre
  tactique, un titre sans espacement forcé, un état vital et une indication
  Entrée/Espace/clic. Les tailles se recalibrent à la résolution ; le fondu et
  l'indication animée utilisent `death_time`, puisque `HUD.update()` est figé
  pendant la cinématique. Les raccourcis historiques, dont Échap, continuent
  tous à avancer immédiatement vers l'écran de fin.

## Passe de nettoyage, robustesse et sécurité LAN

- `settings.py` ne fait plus confiance au JSON local : lecture limitée à
  `64 KiB`, racine obligatoirement objet, nombres finis et bornés, booléens
  stricts, progression plafonnée et IPv4 validée. Les keycodes inconnus,
  `Échap` et `F11` sont rejetés ; les doublons chargés sont réparés et un
  remappage en conflit échange les deux touches au lieu de rendre une action
  inaccessible. La sauvegarde passe par `settings.json.tmp`, `fsync`, puis
  `os.replace` : une interruption ne tronque plus le dernier fichier valide.
- Le menu LAN refuse une IPv4 mal formée avant la connexion. Le menu des
  touches rappelle que `F11` est global et qu'`Échap` annule la capture. En
  jeu, rechargement, changement d'arme et molette sont ignorés pendant la
  pause ou après la fin ; perdre le focus met en pause et libère la visée afin
  d'éviter un clic droit ou un mouvement de souris « coincé » au retour.
- `network.UdpPeer.receive()` n'accepte que des objets JSON, ignore aussi les
  imbrications invalides et ne traite jamais plus de `128` datagrammes dans
  une image. Cela empêche une liste JSON ou un flot UDP de faire planter ou
  d'affamer la boucle de rendu.
- La coop reste hôte-autoritaire mais valide désormais réellement les entrées
  clientes : quatre joueurs maximum (hôte + 3), adresse source exacte,
  identifiants typés, coordonnées/angles finis, déplacement plafonné puis
  sous-échantillonné contre les collisions, et roulade/i-frames démarrées par
  l'horloge de l'hôte. Le numéro monotone `rs`, ou un front montant pour les
  anciens clients, empêche donc `rt=0.5` répété ou retardé de redéclencher une
  action sans nouvelle commande.
- Les tirs distants sont bornés à `32` événements par paquet, à `20` crédits
  par seconde avec capacité `14`, aux dégâts maximaux légitimes d'une arme
  Mk. IV et à `0.18 rad` autour de l'orientation annoncée. Les rafales locales
  en attente sont elles aussi plafonnées : une reconnexion ne rejoue pas cinq
  secondes de minigun d'un coup. Ce n'est pas un système anti-triche Internet,
  mais les téléportations, dégâts arbitraires et dénis de service LAN les plus
  évidents ne sont plus acceptés.
- Tous les instantanés reçus sont vérifiés avant indexation : lignes trop
  courtes, types d'ennemis inconnus, `NaN`/infinis, événements incomplets,
  santé, vague et positions hors bornes sont ignorés. La santé et la mort
  envoyées par l'hôte restent autoritaires même si le client affiche encore
  un bouclier ou une roulade. Les coéquipiers reçoivent côté hôte le même
  bouclier de spawn/réapparition de `3 s` que le joueur local.
- Optimisations sans changement de gameplay : sprite d'arme HUD redimensionné
  une fois par résolution/arme, volume du canal musical écrit seulement lors
  d'un changement, file d'apparitions du Déferlement passée de `list.pop(0)`
  à `deque.popleft()`, et un seul appel horloge par frame de portail.

## Passe roulades, Lune et menu

- Le milicien `Grunt`, seul ennemi du premier niveau, passe de `SPEED = 1.7`
  à `2.55` (+50 %). Sa cadence reste strictement `FIRE_DELAY = 1.3` : ne pas
  confondre mobilité et fréquence de tir lors d'un futur équilibrage.
- Le militaire `Soldier` possède `CAN_ROLL = True`. En combat et avec un côté
  praticable, l'IA effectue une roulade latérale de `1.0 s`, à `2.8` cases/s,
  avec invincibilité pendant toute l'animation et cooldown de `3.0 s` entre
  deux déclenchements. Il ne navigue, ne vise et ne tire pas pendant l'action.
  Les trois frames sont `assets/enemy_soldier_roll_0..2.png` (`64x96`).
- Le sprint a été supprimé. La touche configurable `roulade` (Maj par défaut)
  déclenche une roulade joueur de `0.55 s`, vitesse `4.55`, i-frames centrales
  de `0.30 s` et aucun cooldown après l'animation. La direction suit ZQSD, ou
  avance par défaut. Les longues impulsions sont sous-échantillonnées : un pic
  de `dt` ne traverse pas un mur. Tir, ADS et rotation de vue sont suspendus ;
  la caméra bascule et l'arme s'abaisse. Le HUD indique « en cours » ou
  « prête ». Les anciens `settings.json` contenant `sprint` sont migrés
  automatiquement vers `roulade`.
- La coop ajoute roulade/temps restant après les anciens champs des joueurs
  et des ennemis. Les formats historiques 7 champs (joueurs), 8 champs
  (ennemis) et 9 champs (ennemis avec `aiming`) restent acceptés. L'hôte
  applique les i-frames des clients distants : la protection n'est pas
  seulement cosmétique côté client.
- Dans `MAP_MOON`, toutes les crevasses `V` sont remplacées par des cristaux
  `k` / `prop_alien_crystal` (`96x112`, largeur monde `0.88`) montrant un alien
  emprisonné. Chaque cristal bloque déplacement/pathfinding par sa case et
  balles/perception par un cercle de rayon `0.46`; le rendu reste un billboard
  irrégulier qui masque naturellement ce qui est derrière par ordre de
  profondeur. Le régolithe utilise `moon_ground`: grain et cratères gris sont
  précalculés au changement de résolution, sans primitives ajoutées par frame.
- Le portail lunaire n'a plus de pied ni de support : anneau ovale complet,
  vortex animé conservé, `v_offset` oscillant autour de `0.11` pour la
  lévitation. Les quatre frames restent en `79x117` et partagent une boîte
  opaque `71x108` en `(4, 2)`.
- Le menu principal utilise un nouveau fond `1280x720`: soldat seul sur la
  Lune, arme abaissée, face à un portail gigantesque. Le panneau et les
  boutons occupent le tiers gauche laissé sombre par la composition ; police,
  libellés, records et pied de page ont été recalibrés à `1280x720` et
  `800x600`. Les autres menus restent centrés et leur mode compact a été
  resserré pour ne pas déborder après le changement de police.

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
- Le joueur n'a aucun cooldown mais `Player.start_roll()` doit toujours refuser
  un redéclenchement pendant `rolling`. Le cooldown soldat de `3.0 s` se mesure
  de déclenchement à déclenchement et inclut sa seconde de roulade. Ne jamais
  remplacer le déplacement sous-échantillonné par un unique grand pas
  collisionné.
- `MAP_MOON`, `PROP_CHARS`, `cover_circles`, le test de ligne de vue et le
  hitscan doivent rester cohérents : retirer seulement l'un d'eux rendrait un
  cristal traversable, invisible à l'IA ou perméable aux balles.
- Toute évolution de l'état réseau joueur/ennemi doit ajouter ses champs en
  fin de ligne et rester tolérante aux instantanés plus courts afin qu'un
  client mis à jour ne plante pas avec un hôte plus ancien.
- Toute donnée UDP est non fiable, même en LAN : ne jamais indexer un paquet
  avant validation, accepter `NaN`/`inf`, ou réintroduire une position, une
  invincibilité, des dégâts ou une cadence décidés sans borne par le client.
  La compatibilité des anciens instantanés concerne leur lecture, pas le
  relâchement des contrôles de l'hôte.
- `RemotePlayer.shield` est simulé par l'hôte. Une réapparition doit remettre
  santé, roulade, cooldown et bouclier ensemble ; côté client, un instantané
  de mort doit d'abord annuler bouclier/i-frames avant de poser le cadavre.
- Le cache `_weapon_scale_cache` appartient à une résolution HUD et doit être
  vidé dans `HUD.resize()`. La file `spawn_queue` est un `deque` : employer
  `extend` / `popleft`, jamais réintroduire `pop(0)` dans la boucle de vague.

## Validation disponible

La suite contient 34 tests. `tests/test_requested_changes.py` conserve les
22 non-régressions graphiques et de gameplay : marges de la
voiture, conception et échelle du siège, topologie des portes et blancheur des
murs du laboratoire, courbe de couvert, délai/annulation/pose du sniper,
compatibilité coop 8/9 champs, stabilité d'échelle des cinq tirs frontaux et
présence/absence correcte des nuages sur Terre/la Lune, vitesse du milicien,
roulades joueur/soldat (direction, i-frames, enchaînement/cooldown, collision,
frames et IA), compatibilité réseau de la roulade, cristaux de couverture et
nouveau fond de menu.

`tests/test_cleanup.py` ajoute 12 contrôles : paquets UDP bornés et non-objets,
réglages malformés/sauvegarde atomique, IPv4, conflits et touches réservées,
téléportation/`NaN`/spam de roulade, séquences de roulades enchaînées et
paquets retardés, budget de tir/dégâts, bouclier et mort autoritaires en coop,
commandes ignorées en pause, cache du sprite d'arme, mise en page de mort à
basse résolution et file d'apparitions en temps constant.

Commande utilisée :

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --with pygame \
  python -m unittest discover -s tests -v
```

Un smoke test SDL factice valide `Game`, `SurvivalGame`, le redimensionnement,
puis une vraie socket UDP locale entre `CoopHostGame` et `CoopClientGame`
jusqu'au premier instantané synchronisé et au rendu des deux côtés.

## Portails (20 juillet 2026)

- Le portail lunaire utilise quatre PNG `assets/prop_portal_0..3.png`. La
  classe `Prop` sélectionne une frame toutes les `110 ms` avec
  `pygame.time.get_ticks()`. Les surfaces et leurs mises à l'échelle sont
  mises en cache : aucune rotation/composition n'est faite pendant le rendu.
- Les quatre frames font `79x117`, partagent la même boîte opaque (`71x108`,
  en `(4, 2)`) et gardent l'anneau immobile ; seul le vortex vert tourne et
  pulse. L'anneau est fermé, sans support, et lévite. Le portail ne doit pas
  être retourné selon la parité de sa case.
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
