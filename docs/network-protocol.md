# Protocole LAN v4

Le transport utilise UDP/IPv4 et des objets JSON compacts. L'hote est
autoritaire : un client ne declare jamais ses degats, munitions, cadence ou
invulnerabilite.

`join` doit contenir `v: 4`. Toute autre version recoit `incompatible` sans
allocation de joueur. `welcome` fournit l'identifiant, le `session_id` et la
sequence d'evenements. Les entrees portent `iq`, les instantanes `sq`, et les
evenements fiables sont acquittes par `ea`.

## Missions (v4)

`welcome.mode` vaut `survival` ou `warehouse`. Le client charge uniquement une
carte locale connue ; aucune carte ni définition exécutable ne traverse le LAN.
Les joueurs doivent mettre le jeu à jour ensemble ; les hôtes v4 refusent v3.

`in.ix` vaut `null` ou `[numéro_action, index_objectif]`. Le client répète la
même demande jusqu'à `snap.ia` (dernier numéro consommé), sans prédire la
progression. L'hôte consomme une seule fois chaque numéro strictement croissant,
borné à 31 bits, puis contrôle l'objectif courant, la position acceptée,
la ligne de vue, la vie, la roulade et la pause. Même une demande hors portée
est acquittée : se déplacer ensuite ne la transforme pas en interaction.
Le numéro d'objectif empêche une ancienne demande de valider le suivant.

`snap.ms = [index_objectif, secondes_défense]` transmet l'état autoritaire,
y compris aux nouveaux arrivants. Le client rejette les index régressifs et
les timers non finis ou hors durée. Les objectifs terminés et la victoire
sont répétés dans les instantanés ; le chronomètre avance seulement sur l'hôte.
Une pause locale purge les interactions encore en attente côté client ; un
datagramme déjà envoyé peut avoir été accepté avant cette pause.

## Transport

Grenades : `in.gr` est une séquence 31 bits, consommée même si charges/cooldown
refusent le lancer. `snap.gm=[charges,cooldown,dernière_séquence]` acquitte ;
`snap.gr` contient au plus huit `[id,propriétaire,x,y,fusée]`. Ni trajectoire
ni dégâts proposés par le client. Effets `ex`, éliminations distantes `[gk,pid,compte]`
dans le journal fiable pour les statistiques individuelles.

`en[15]` est `null` ou `[état,attaque,x_cible,y_cible,temps]` pour un Colosse.
États connus : idle/warn/charge/recover ; attaques charge/slam. Coordonnées et
timer (0–10 s) sont bornés. Les impacts passent par la santé autoritaire ;
l'effet de frappe utilise l'événement d'explosion fiable existant `ex`.

La ligne `en` ajoute aux 13 champs antérieurs l'identifiant élite (`""`,
`bulwark`, `hunter`) puis le booléen entier d'aura. `commander` est un type
ennemi connu. Le client utilise ces champs pour le rendu, et la santé maximale
répliquée ; il ne réapplique pas les multiplicateurs de santé.

Secours : `snap.rr` contient au plus quatre lignes `[pid, secondes_avant_respawn,
progression_secours, pid_secouriste]` (secouriste -1 si absent). La fenêtre de
secours correspond aux 20 premières secondes du délai total de 26 s. `ix`
commence/annule un secours proche avant de chercher une interaction de mission.
`in.lp: true` annule le secours et ignore le gameplay du client en pause locale.
Un silence d'entrée de 350 ms annule également le secours ; pas la partie.

Ping : `in.pg` est une séquence 31 bits, acquittée par `snap.ga`. `snap.pg`
contient `[pid,x,y,secondes]`, au plus quatre lignes. Le point est dérivé du
rayon de visée hôte, borné à 12 m et avant le mur ; aucune coordonnée de ping
cliente acceptée. Les états remplacent les anciens, sans effets cumulés.

`snap.wv.mutator` est vide ou vaut `rapid`, `armored`, `crossfire`. Les
identifiants inconnus sont ignorés. Les clients ne recalculent pas les effets
ennemis ; santé maximale et positions restent celles de l'hôte.

Les améliorations v4 utilisent `snap.ub = [id_offre, niveaux, propositions,
secondes_restantes, crédits_en_attente]`, individuel par client. `in.uc` vaut
`null` ou `[id_offre, index_choix]`. Les doublons ne peuvent choisir une offre
suivante. Le serveur reconstruit les armes depuis son catalogue ; le client
reçoit les effets, sans déclarer un bonus ni une valeur de dégâts. Une offre
expirée choisit son premier élément sur l'hôte. Les nouveaux arrivants gagnent
les récompenses futures, pas celles déjà acquises avant leur connexion.

- datagramme maximal : 1 200 octets ;
- compression zlib `Z1` a partir de 900 octets si utile ;
- fragmentation applicative `F1` apres compression ;
- 128 fragments, 65 507 octets reconstitues et TTL de 2 secondes au maximum ;
- 64 ensembles incomplets simultanes ;
- travail par tick et debit par adresse source bornes ;
- compteurs exportes par `network_diagnostics()`.

UDP reste non fiable. Les instantanes sont remplacables ; les evenements
critiques restent dans le journal borne jusqu'a acquittement.

Le protocole ne chiffre pas le trafic et n'authentifie pas l'identite sur un
LAN hostile. Ne pas exposer UDP/5577 sur Internet.
