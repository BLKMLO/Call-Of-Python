# Protocole LAN v3

Le transport utilise UDP/IPv4 et des objets JSON compacts. L'hote est
autoritaire : un client ne declare jamais ses degats, munitions, cadence ou
invulnerabilite.

`join` doit contenir `v: 3`. Toute autre version recoit `incompatible` sans
allocation de joueur. `welcome` fournit l'identifiant, le `session_id` et la
sequence d'evenements. Les entrees portent `iq`, les instantanes `sq`, et les
evenements fiables sont acquittes par `ea`.

## Transport

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
