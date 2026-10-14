# Règles gameplay 0.7.0

## Mission Entrepôt

Récupérer le manifeste dans le bureau (25,5 ; 18,5), désactiver l’alarme
(24,5 ; 3,5), revenir au point d’extraction (1,5 ; 1,5) et y rester huit
secondes consécutives dans un rayon de 1,4 m. Quitter la zone remet le timer
à zéro. En coop, la présence d’au moins un joueur vivant suffit. E/LB/ACT. interagit à portée
avec ligne de vue ; un joueur mort ou en glissade ne peut pas interagir.

La même mission est disponible depuis le menu LAN, indépendante de la campagne.
L’hôte est seul responsable des objectifs, récompenses, dégâts et timers.

## Missions de campagne (0.7.0, solo)

Déclarées dans `level.py`, pilotées par `missions.MissionDirector` :

- **Métropole** : balise (14,5 ; 7,5), tenir le carrefour 30 s dans 2,6 m ;
  pendant l’étape, 2 renforts toutes les 6 s ÷ multiplicateur de renforts
  (8 s Recrue, 4 s Vétéran), plafond 12 × multiplicateur ; puis hélicoptère
  (27,5 ; 20,5).
- **Gouvernement** : dossiers (3,5 ; 11,5), (23,5 ; 15,5), (11,5 ; 3,5),
  otage (15,5 ; 12,5) à escorter jusqu’à (13,5 ; 24,5). L’otage (150 PV) suit
  le joueur (chemin BFS, 3 cases/s), attend au-delà de 9 m ; un ennemi plus
  proche de lui que du joueur le prend pour cible. Sa mort fait échouer la
  mission. 4 renforts × multiplicateur à sa libération.
- **Base militaire** : batteries (10,5 ; 6,5), (21,5 ; 2,5), (12,5 ; 15,5)
  avant 150 s × multiplicateur de compte à rebours, 3 renforts ×
  multiplicateur à chaque sabotage, puis exfiltration (1,5 ; 1,5).
- **Laboratoire** : générateurs (3,5 ; 1,5), (27,5 ; 7,5), (13,5 ; 17,5) ;
  tant qu’un tourne, le Colosse ne subit aucun dégât (teinte bleue).

Échec (otage mort, compte à rebours écoulé) : bandeau « MISSION ÉCHOUÉE »,
puis écran d’échec ; la campagne repart de zéro comme après une mort.

## Armes (0.7.0)

Dégâts par balle (`weapons.shot_damage`) : minigun ×0,6 contre le blindage
d’origine (lourd, Colosse, même possédés) ; pistolet ×1,4 contre le blindage
et ×1,75 en visée complète (lunette ≥ 90 %) ; fusil à pompe ×1,5 par plomb
à 2 m ou moins. Un plomb qui touche étourdit 0,5 s (blindé : moitié, sans
recul ; Colosse : jamais) et repousse de 0,35 m ; l’ennemi étourdi ne bouge ni
ne tire et baisse son bouclier. Un bouclier levé couvre ±60° devant le
porteur et ne laisse passer que 15 % des dégâts ; grenades et explosions
l’ignorent.

Minigun : munitions illimitées, rechargement impossible. Chaque tir ajoute
1 / (0,7 × capacité) de chaleur (70 tirs de base) ; à 100 %, surchauffe
jusqu’au refroidissement complet, en 0,85 × temps de recharge (2,21 s). Le
canon refroidit 0,3 s après le dernier tir. Lancement 0,4 s avant le premier
tir (local uniquement ; l’hôte LAN valide cadence et chaleur), déplacement
×0,65 pendant 0,2 s après chaque tir. Réserve et Chargeur rapide agissent
donc sur la chaleur.

## Améliorations et ressources

Chaque interaction de mission et chaque troisième vague entièrement nettoyée
(chaque deuxième en Déferlement solo)
ouvre une offre, sans limite de nombre par partie. Une offre montre jusqu’à
quatre cartes : trois d’arme, puis une quatrième toujours hors arme (bordure
ambre). Choisir avec F5/F6/F7/F8, croix gauche/haut/droite/bas, souris ou
tactile. Sans réponse pendant 12 secondes, la première carte est choisie. La
pause hôte fige le délai ; une pause locale ne suspend pas les autres joueurs.
Les offres simultanées attendent en file. Chaque bonus a son plafond ; un bonus
au plafond n’est plus proposé, et une offre peut donc avoir moins de cartes.

| Bonus | Type | Effet par niveau | Plafond |
|---|---|---|---|
| Impact | Arme | Dégâts +10 %, arrondi entier | 10 |
| Chargeur rapide | Arme | Temps de recharge -15 % du temps de base | 5 |
| Réserve | Arme | Chargeur +20 %, arrondi entier | 10 |
| Stabilité | Arme | Dispersion -20 % de la dispersion de base | 4 |
| Mécanisme | Arme | Fréquence +8 % | 10 |
| Artificier | Hors arme | +1 grenade maximum, stock rempli | 4 |
| Glissade fantôme | Hors arme | Invulnérable pendant toute la glissade | 1 |
| Blindage | Hors arme | +20 PV maximum, et 20 PV rendus | 5 |
| Élan | Hors arme | +25 % de vitesse, donc de distance, de glissade | 2 |
| Balles explosives | Pistolet | Éclats : 40 % des dégâts à 1,2 m (ligne de vue) | 1 |
| Chevrotine lourde | Fusil à pompe | Étourdissement ×2, recul ×1,7, bout portant 3,5 m | 1 |
| Perforantes | Fusil d’assaut | La balle touche aussi l’ennemi suivant (60 %) | 1 |
| Refroidissement | Minigun | Chaleur par tir ×0,7 | 1 |

Les effets repartent des caractéristiques de base, sans cumul accidentel entre
ticks. La capacité ne fournit pas de munitions gratuites ; le ratio d’une
recharge en cours est conservé. Les choix continuent entre niveaux de campagne,
pas après une nouvelle partie. En coop, chacun reçoit son offre ; un nouvel
arrivant ne récupère pas les récompenses antérieures.

Les mêmes jalons rendent une grenade (maximum deux, plus un par niveau
d’Artificier).
Une vague submergée sans nettoyage ne donne pas sa récompense.

## Déferlement et adversaires

En solo, le Déferlement n'applique ni mutateur ni élite (Commandant, Colosses
et montée de vie/dégâts par vague conservés). En coop LAN :
dès la vague 4, les mutateurs changent par groupes de trois vagues, selon une
rotation reproductible : rapide (+15 % vitesse), blindé (+20 % vie, -10 %
vitesse), tirs croisés (un milicien sur quatre devient soldat). Les vagues
10/20/30 sont neutres et les boss sont exclus. Une file d’apparition conserve
ses paramètres d’origine quand la vague suivante commence. Le plafond reste
24 ennemis vivants et 60 cadavres.

Résistant bleu : +35 % vie, -10 % vitesse. Traqueur rouge : +15 % vitesse et
délai de prochain tir ×0,9. Au plus trois élites vivants. Commandant doré :
220 PV de base, aura à 5 m avec ligne de vue, délai de tir des alliés ×0,8
(cadence +25 %), sans cumul, ni effet sur un boss ou un autre Commandant.
Sa mort retire immédiatement l’aura. Au plus un vivant ; en Déferlement,
apparition aux vagues 5/15/25, élites dès la vague 4. Leurs modifications
s’ajoutent aux paramètres de difficulté et de vague, sans altérer le catalogue.

Le Colosse annonce sa cible pendant 1,2 s, charge à 5,5 m/s pendant au plus
0,65 s, puis récupère 1,2 s. Dès la phase 2, il alterne avec une frappe de
rayon 1,8 m. Le tracé au sol indique la cible verrouillée. Dégâts de base :
24 pour la charge, 28 pour la frappe ; une seule touche par joueur et attaque.
Murs, collisions et invulnérabilité de roulade sont respectés. Les packs aux
seuils de vie 2/3 et 1/3 restent déclenchés une seule fois chacun.

Porte-boucliers : dans le Déferlement, un soldat sur trois dès la vague 7 ;
en campagne, un soldat sur trois (Gouvernement) ou sur deux (Base). Vitesse
×0,85. Essaims : vagues 8, 12, 16, 24, 28 (une sur quatre dès la 8e, hors
Colosse), 3 + vague // 6 kamikazes × multiplicateur d’ennemis, vitesse ×1,25.

Contrats (vagues 2, 5, 8…, hors 10/20/30) : un défi tiré de façon
déterministe parmi ceux possibles dans la vague (kamikazes au pompe, lourds
au pistolet, snipers au fusil, ennemis à la grenade ou au pistolet,
porte-boucliers au pompe), objectif ramené au nombre de cibles prévues.
Rempli dans la vague : une carte bonus. Les éliminations de tous les joueurs
comptent en coop.

## Difficulté

| | Recrue | Soldat | Vétéran |
|---|---|---|---|
| Vie / dégâts ennemis | ×0,82 / ×0,72 | ×1 / ×1 | ×1,22 / ×1,28 |
| Intervalle d’apparition | ×1,20 | ×1 | ×0,86 |
| Ennemis par vague | ×0,8 | ×1 | ×1,25 |
| Délai de submersion | 30 × 0,97^(n−1) | 30 × 0,94^(n−1) | 30 × 0,90^(n−1) |
| PV vague nettoyée / entre niveaux | 20 / 55 | 12 / 40 | 6 / 25 |
| Bouclier d’arrivée | 4 s | 3 s | 2 s |
| Pack de vie (Déferlement) | chaque vague | 2 vagues | 3 vagues |
| Repos du Colosse | ×1,2 | ×1 | ×0,75 |
| Renforts / comptes à rebours | ×0,75 / ×1,25 | ×1 / ×1 | ×1,5 / ×0,8 |

Planchers de submersion 8/6/4 s par tranche de dix vagues ; nombre
d’ennemis par vague arrondi, au moins 3.

## Secours, signaux et grenades

Un joueur coop à terre peut être secouru pendant 20 s. E près de lui (1,4 m
et ligne de vue) commence un secours de 3 s ; rester proche, sans subir de dégâts
ni rouler. Un nouvel appui annule. Tir et grenade sont bloqués pendant l’action.
Plusieurs secouristes n’accélèrent pas la progression. Retour à 40 PV avec
2 s de bouclier ; sans secours, retour au spawn après 6 s supplémentaires,
à 60 PV. Si toute l’équipe tombe, défaite immédiate.

C/Back/SIG. pose un signal devant le mur visé, portée 12 m, durée 5 s, délai
2 s, au plus quatre signaux. Le serveur calcule le point depuis la visée.

G/clic stick droit/FRAG. lance une grenade : deux charges, délai 1 s, fusée
2 s, rebonds amortis, huit projectiles maximum. Rayon 2,7 m et dégâts décroissants
90→31 aux ennemis, 60→21 au lanceur ; les murs arrêtent le souffle. Pas de
souffle direct sur les alliés, mais les kamikazes gardent leurs explosions.
Les lancers répétés par le réseau sont dédupliqués et les clients ne calculent
ni explosion ni dégâts. La pause hôte fige la fusée.

## Score et grades

| Événement | Points |
|---|---:|
| Milicien / soldat / lourd / sniper / kamikaze | 100 / 150 / 220 / 180 / 80 |
| Commandant / Colosse | 450 / 1 500 |
| Variante élite éliminée | +100 |
| Objectif terminé | 500 |
| Vague entièrement nettoyée | 200 |
| Victoire | 500 |
| Mise à terre | -150, score plancher 0 |
| Secours réussi | 250, quatre crédits maximum |

Le score coop est commun ; éliminations et précision restent individuelles.
Chaque élimination, objectif achevé ou victoire n’est crédité qu’une fois. La cible
d’un niveau est le budget de ses ennemis initiaux + 500 par objectif + 500 de
victoire. La cible Déferlement vaut 20 000. Le grade porte sur le segment courant,
même si le total continue entre niveaux : D sous 25 %, C dès 25 %, B dès 50 %,
A dès 75 % et S dès 90 %. A et S exigent la victoire. Aucun classement persistant.

Ces paramètres privilégient les objectifs, la coopération et l’évitement des
mises à terre. Le bonus de secours plafonné limite le gain par réanimation
répétée. Le grade n’est pas un classement compétitif entre tailles d’équipe ou
difficultés : l’équilibrage subjectif doit encore être éprouvé en parties humaines.
