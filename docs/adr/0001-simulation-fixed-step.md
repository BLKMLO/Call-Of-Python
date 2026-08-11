# ADR 0001 — Simulation a pas fixe

Statut : accepte le 11 aout 2026.

La logique avance a 60 Hz via un accumulateur. Le rendu est borne a 120 Hz et
peut produire zero ou plusieurs pas. Un retard ne peut executer que huit pas
par image ; l'excedent est mesure puis abandonne.

Cela rend l'equilibrage reproductible et empeche un gel de fenetre de creer
une grande impulsion. Une future interpolation peut utiliser `alpha`.
