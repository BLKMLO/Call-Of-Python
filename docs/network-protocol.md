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
