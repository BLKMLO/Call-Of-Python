# ADR 0002 — Protocole v3 strict et MTU-aware

Statut : accepte le 11 aout 2026.

Les versions inconnues ne sont plus interpretees comme v1. Le handshake exige
une egalite stricte afin de ne jamais relacher silencieusement les validations
autoritaires.

Les charges de plus de 1 200 octets sont fragmentees dans l'application apres
compression. La reconstitution est bornee en taille, nombre et duree. Cette
decision evite la fragmentation IP et rend les erreurs mesurables.
