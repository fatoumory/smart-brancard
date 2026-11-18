# Comparaison : test de charge Locust et simulation

Conditions : 8 agents, période journee, 3 transports par séjour (7.8 demandes/h), 7.1 h d'hôpital, temps accéléré ×15 pour Locust.
Simulation : 200 journées identiques ; médiane et fourchette 5e-95e centile.

| Urgence | Missions Locust | Attente moyenne Locust (min) | Attente moyenne simulée (min) | Dans le délai, Locust | Dans le délai, simulation |
|---|---|---|---|---|---|
| URGENT | 5 | 2.0 | 1.4 (0.2 à 3.1) | 60 % | 83 % (33 % à 100 %) |
| HAUTE | 10 | 2.5 | 1.4 (0.5 à 2.4) | 100 % | 100 % (100 % à 100 %) |
| MOYENNE | 26 | 2.1 | 1.5 (0.8 à 2.0) | 100 % | 100 % (100 % à 100 %) |
| BASSE | 24 | 2.0 | 1.5 (0.9 à 2.1) | 100 % | 100 % (100 % à 100 %) |
