# Règles gameplay 0.5.0

## Mission Entrepôt

Récupérer le manifeste dans le bureau (25,5 ; 18,5), désactiver l’alarme
(24,5 ; 3,5), revenir au point d’extraction (1,5 ; 1,5) et y rester huit
secondes consécutives dans un rayon de 1,4 m. Quitter la zone remet le timer
à zéro. En coop, la présence d’au moins un joueur vivant suffit. Les autres
niveaux conservent leur condition d’élimination. E/LB/ACT. interagit à portée
avec ligne de vue ; un joueur mort ou en roulade ne peut pas interagir.

La même mission est disponible depuis le menu LAN, indépendante de la campagne.
L’hôte est seul responsable des objectifs, récompenses, dégâts et timers.

## Améliorations et ressources

Chaque interaction de mission et chaque troisième vague entièrement nettoyée
ouvre une offre, jusqu’à six choix par partie. Choisir parmi trois cartes avec
F5/F6/F7, croix gauche/haut/droite, souris ou tactile. Sans réponse pendant
12 secondes, la première carte est choisie. La pause hôte fige le délai ; une
pause locale ne suspend pas les autres joueurs. Les offres simultanées attendent
en file. Chaque bonus a deux niveaux maximum :

| Bonus | Effet par niveau |
|---|---|
| Impact | Dégâts +10 %, arrondi entier |
| Recharge | Temps -15 % |
| Capacité | Chargeur +20 %, arrondi entier |
| Précision | Dispersion -20 % |
| Cadence | Fréquence +8 % |

Les effets repartent des caractéristiques de base, sans cumul accidentel entre
ticks. La capacité ne fournit pas de munitions gratuites ; le ratio d’une
recharge en cours est conservé. Les choix continuent entre niveaux de campagne,
pas après une nouvelle partie. En coop, chacun reçoit son offre ; un nouvel
arrivant ne récupère pas les récompenses antérieures.

Les mêmes jalons rendent une grenade (maximum deux), même après les six choix.
Une vague submergée sans nettoyage ne donne pas sa récompense.

## Déferlement et adversaires

Dès la vague 4, les mutateurs changent par groupes de trois vagues, selon une
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
