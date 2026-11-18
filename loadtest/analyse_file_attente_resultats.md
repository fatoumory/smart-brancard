# Résultats de l'analyse de la file d'attente

Généré par `python analyse_file_attente.py` : 2000 h simulées par configuration, hypothèses de `hypotheses.py` (HOGIP, annuaires MSAS 2020-2021).
Plan de l'hôpital : 8 services, trajet moyen d'un service à un autre 3.6 min (de 1.0 à 5.5 min).

## Agents nécessaires par période

Critère : 95 % des missions HAUTE, MOYENNE et BASSE prises en charge dans leur délai garanti (8, 15 et 30 min). L'attente est mesurée de la demande au scan du bracelet.

| Transports par séjour | Période | Demandes/h | Agents minimum (file stable) | Agents nécessaires | Occupation | URGENT pris en charge en 3 min |
|---|---|---|---|---|---|---|
| 2 | journée (8 h-18 h) | 5.2 | 2 | **4** | 27 % | 55 % |
| 2 | pic de fin de matinée | 7.8 | 2 | **4** | 41 % | 46 % |
| 2 | nuit (18 h-8 h) | 1.2 | 1 | **2** | 13 % | 43 % |
| 3 | journée (8 h-18 h) | 7.8 | 2 | **4** | 41 % | 50 % |
| 3 | pic de fin de matinée | 11.7 | 3 | **5** | 49 % | 50 % |
| 3 | nuit (18 h-8 h) | 1.9 | 1 | **3** | 12 % | 53 % |
| 4 | journée (8 h-18 h) | 10.4 | 3 | **5** | 44 % | 51 % |
| 4 | pic de fin de matinée | 15.6 | 4 | **6** | 54 % | 51 % |
| 4 | nuit (18 h-8 h) | 2.5 | 1 | **3** | 17 % | 51 % |

## Détail : 3 transports par séjour, journée

| Agents | Occupation (formule / simulation) | URGENT : attente moy. (min) / dans 3 min | HAUTE : attente moy. (min) / dans 8 min | MOYENNE : attente moy. (min) / dans 15 min | BASSE : attente moy. (min) / dans 30 min |
|---|---|---|---|---|---|
| 2 | 80 % / 87 % | 7.7 / 12 % | 8.3 / 56 % | 12.7 / 71 % | 71.8 / 42 % |
| 3 | 54 % / 56 % | 4.4 / 33 % | 4.4 / 87 % | 5.0 / 96 % | 7.0 / 96 % |
| 4 | 40 % / 41 % | 2.9 / 50 % | 3.0 / 96 % | 3.2 / 99 % | 3.3 / 100 % |
| 5 | 32 % / 31 % | 2.3 / 57 % | 2.3 / 99 % | 2.4 / 100 % | 2.4 / 100 % |
| 6 | 27 % / 26 % | 1.9 / 67 % | 2.0 / 100 % | 2.0 / 100 % | 2.0 / 100 % |
| 7 | 23 % / 22 % | 1.6 / 71 % | 1.7 / 100 % | 1.7 / 100 % | 1.7 / 100 % |
| 8 | 20 % / 19 % | 1.5 / 76 % | 1.5 / 100 % | 1.5 / 100 % | 1.5 / 100 % |
| 9 | 18 % / 17 % | 1.3 / 80 % | 1.4 / 100 % | 1.4 / 100 % | 1.4 / 100 % |
| 10 | 16 % / 15 % | 1.3 / 82 % | 1.3 / 100 % | 1.3 / 100 % | 1.3 / 100 % |
| 11 | 15 % / 13 % | 1.2 / 83 % | 1.2 / 100 % | 1.2 / 100 % | 1.2 / 100 % |
| 12 | 13 % / 12 % | 1.1 / 85 % | 1.2 / 100 % | 1.1 / 100 % | 1.2 / 100 % |

## Agents postés : tenir le délai URGENT

3 transports par séjour, journée. Un agent posté revient attendre à son poste après chaque mission ; « réservé » : il ne prend que les URGENT. En gras : 90 % des URGENT et 95 % des autres dans le délai.
La colonne « départ surtout des Urgences » est une variante (60 % Urgences, 20 % Réanimation, 20 % Bloc) : aucune donnée publiée ne donne l'origine des transports urgents.

| Agents | Organisation | URGENT en 3 min (départ au hasard) | URGENT en 3 min (départ surtout des Urgences) | HAUTE / MOYENNE / BASSE dans le délai |
|---|---|---|---|---|
| 4 | Application actuelle (aucun poste) | 48 % | 47 % | 96 % / 99 % / 100 % |
| 4 | 1 agent posté aux Urgences | 50 % | 56 % | 95 % / 99 % / 100 % |
| 4 | 1 agent posté aux Urgences, réservé aux URGENT | 51 % | 61 % | 88 % / 97 % / 98 % |
| 4 | 2 agents postés (hall RDC, palier de l'étage) | 63 % | 60 % | 96 % / 99 % / 100 % |
| 4 | 2 agents postés, réservés aux URGENT | 87 % | 86 % | 63 % / 78 % / 61 % |
| 5 | Application actuelle (aucun poste) | 61 % | 60 % | 99 % / 100 % / 100 % |
| 5 | 1 agent posté aux Urgences | 61 % | 65 % | 99 % / 100 % / 100 % |
| 5 | 1 agent posté aux Urgences, réservé aux URGENT | 60 % | 74 % | 96 % / 99 % / 100 % |
| 5 | 2 agents postés (hall RDC, palier de l'étage) | 72 % | 72 % | 99 % / 100 % / 100 % |
| 5 | 2 agents postés, réservés aux URGENT | 91 % | 91 % | 86 % / 96 % / 97 % |
| 6 | Application actuelle (aucun poste) | 68 % | 66 % | 100 % / 100 % / 100 % |
| 6 | 1 agent posté aux Urgences | 68 % | 71 % | 100 % / 100 % / 100 % |
| 6 | 1 agent posté aux Urgences, réservé aux URGENT | 69 % | 76 % | 99 % / 100 % / 100 % |
| 6 | 2 agents postés (hall RDC, palier de l'étage) | 82 % | 80 % | 100 % / 100 % / 100 % |
| 6 | 2 agents postés, réservés aux URGENT | **94 %** | 95 % | 97 % / 100 % / 100 % |
| 8 | Application actuelle (aucun poste) | 77 % | 81 % | 100 % / 100 % / 100 % |
| 8 | 1 agent posté aux Urgences | 76 % | 84 % | 100 % / 100 % / 100 % |
| 8 | 1 agent posté aux Urgences, réservé aux URGENT | 80 % | 87 % | 100 % / 100 % / 100 % |
| 8 | 2 agents postés (hall RDC, palier de l'étage) | 88 % | 90 % | 100 % / 100 % / 100 % |
| 8 | 2 agents postés, réservés aux URGENT | **96 %** | 97 % | 100 % / 100 % / 100 % |
