# Sprint 5 : tenue en charge, dimensionnement et sécurité

## 1. Objectifs

Le Sprint 5 vérifie trois points avant la démonstration :

1. **Tenue en charge** : le serveur répond-il assez vite quand de nombreux agents utilisent l'application en même temps ?
2. **Dimensionnement** : combien de brancardiers faut-il, selon le moment de la journée, pour respecter les délais garantis de prise en charge (URGENT 3 min, HAUTE 8 min, MOYENNE 15 min, BASSE 30 min) ?
3. **Sécurité** : chaque route de l'API n'est-elle accessible qu'aux rôles autorisés ?

## 2. Données et hypothèses

Le jury a insisté sur la pertinence locale du projet. Plutôt que des bases étrangères (MIMIC-III, données de soins intensifs américaines), le volume de demandes est calibré sur des **données officielles sénégalaises** :

> Ministère de la Santé et de l'Action sociale (MSAS), Direction de la Planification, de la Recherche et des Statistiques, *Annuaire des statistiques sanitaires et sociales*, éditions 2020 et 2021.

L'hôpital de référence est l'**Hôpital Général Idrissa Pouye (HOGIP, Grand Yoff, Dakar)**. C'est un hôpital général dont les services correspondent à ceux du prototype : urgences, radiologie, bloc opératoire, réanimation, cardiologie, laboratoire.

| Donnée | Valeur | Source |
|---|---|---|
| Hospitalisations par an | 12 615 (≈ 35 admissions par jour) | Annuaire 2021, tableau 80 |
| Lits installés | 235 | Annuaire 2020, tableau 22 |
| Taux d'occupation des lits | 55 % | Annuaire 2020, tableau 22 |

À partir de ces données, les hypothèses suivantes ont été posées. Elles sont toutes regroupées dans `loadtest/hypotheses.py` :

| Hypothèse | Valeur retenue |
|---|---|
| Transports par séjour (admission, examens, bloc, sortie) | 3 (analyse de sensibilité : 2 à 4) |
| Répartition dans la journée | 75 % des transports entre 8 h et 18 h ; pic de fin de matinée à 1,5 fois la moyenne |
| Répartition des urgences | URGENT 5 %, HAUTE 15 %, MOYENNE 40 %, BASSE 40 % |
| Durées hors trajet | installation du patient 3 min, remise à l'arrivée 2 min |
| Comportement des agents | réponse en 5 à 20 s, 90 % d'acceptations ; un refus pour urgence prioritaire retient l'agent 15 min |

Avec 3 transports par séjour, on obtient **7,8 demandes par heure en journée, 11,7 au pic et 1,9 la nuit**.

Seul le nombre de transports par séjour est une estimation sans donnée publiée. C'est pourquoi il est testé de 2 à 4.

## 3. Méthodes

Trois approches complémentaires, avec les mêmes hypothèses :

**3.1 Tests de charge (Locust).**
- Des utilisateurs virtuels utilisent l'API réelle comme dans la réalité :
  - un médecin crée des demandes à des instants aléatoires (processus de Poisson) ;
  - des brancardiers reçoivent les propositions, acceptent ou refusent, se rendent auprès du patient, scannent son bracelet, le transportent et confirment l'arrivée ;
  - un régulateur consulte son tableau de bord.
- Le passage des badges devant les récepteurs de salle est simulé, comme dans le prototype.
- **Temps accéléré.** Pour simuler une journée en quelques dizaines de minutes, le temps est accéléré (×15) : les demandes arrivent 15 fois plus vite et chaque étape dure 15 fois moins. Les attentes mesurées sont ensuite ramenées à l'échelle réelle.
- Deux scénarios sont prévus :
  - « réaliste » : 8 agents, charge de l'HOGIP ;
  - « charge » : 50 agents, demande au pic.

**3.2 Modèle analytique.**
- La file des demandes est modélisée comme une file M/M/c à priorités non préemptives : arrivées poissonniennes, *c* agents, service par ordre d'urgence.
- L'attente moyenne de chaque niveau d'urgence est donnée par la formule de Cobham (Cobham, A., « Priority assignment in waiting line problems », *Operations Research*, 2(1), 1954), à partir de la probabilité d'attente d'Erlang C.

**3.3 Simulation à événements discrets.** Le modèle analytique ignore la géographie de l'hôpital. Une simulation reprend donc exactement les règles de l'application :
- plan de l'hôpital et plus courts chemins (Dijkstra) ;
- ordre de la file : urgence, puis ancienneté ;
- choix de l'agent par le score du backend : temps de trajet + 0,5 min par mission déjà effectuée, temps de trajet seul pour une URGENT ;
- refus et retenue de 15 min.

La prise en charge est comptée au scan du bracelet, comme dans l'application. Chaque configuration est simulée sur 2 000 heures.

**Validation croisée.**
- La formule et la simulation donnent la même occupation des agents (par exemple 40 % et 41 % avec 4 agents en journée).
- Un test Locust d'une journée est comparé à 200 journées simulées dans les mêmes conditions.

## 4. Résultats

### 4.1 Tenue en charge

Avec 50 agents virtuels actifs simultanément (essai de 2 minutes), le serveur a traité 5 680 requêtes **sans aucune erreur**. Temps de réponse : médiane 25 ms ; 95 % des requêtes en moins de 120 ms.

Les seules réponses lentes (1,5 à 2 s) concernent les 50 connexions lancées à la même seconde. La vérification du mot de passe est volontairement coûteuse, pour se protéger des attaques par force brute. En usage réel, les agents ne se connectent pas tous en même temps.

Lors du test réaliste (8 agents, 7 h d'hôpital), le serveur a traité 11 822 requêtes. 99 % ont reçu une réponse en moins de 180 ms, et toutes les missions ont été menées à leur terme.

### 4.2 Nombre d'agents nécessaires

Critère : 95 % des missions HAUTE, MOYENNE et BASSE prises en charge dans leur délai garanti.

| Transports par séjour | Journée | Pic de fin de matinée | Nuit |
|---|---|---|---|
| 2 | 4 agents | 4 agents | 2 agents |
| **3 (hypothèse de base)** | **4 agents** | **5 agents** | **3 agents** |
| 4 | 5 agents | 6 agents | 3 agents |

Avec l'hypothèse de base, il faut **4 agents en journée, 5 au pic et 3 la nuit**, chacun occupé environ 40 % du temps. Le résultat varie peu entre 2 et 4 transports par séjour : le dimensionnement est donc robuste à l'hypothèse la moins sûre.

### 4.3 Le cas des URGENT

Le délai URGENT (3 min) est plus court que de nombreux trajets du plan : 1 à 5,5 min d'un service à l'autre (3,6 min en moyenne), à cause des changements d'étage. Ajouter des agents ne suffit pas :

| Agents (journée) | URGENT pris en charge en 3 min |
|---|---|
| 4 | 50 % |
| 8 | 76 % |
| 12 | 85 % (agents occupés 13 % du temps) |

**Le problème est la position des agents, pas leur nombre.** La simulation a donc testé des agents postés : entre deux missions, ils reviennent attendre à un point fixe.

| Organisation (journée) | Agents | URGENT en 3 min | HAUTE / MOYENNE / BASSE dans le délai |
|---|---|---|---|
| Application actuelle | 4 | 48 % | 96 / 99 / 100 % |
| Application actuelle | 8 | 77 % | 100 % |
| 1 agent posté aux Urgences | 6 | 68 % | 100 % |
| 2 agents postés (un par étage), non réservés | 6 | 82 % | 100 % |
| **2 agents postés (un par étage), réservés aux URGENT** | **6** | **94 %** | **97 / 100 / 100 %** |

**Recommandation :** en journée, 4 agents polyvalents et 2 agents postés au centre de chaque étage, réservés aux URGENT. Depuis ce point central, chaque agent posté atteint tous les services de son étage en 1,75 min au plus.

Un seul agent aux Urgences aide peu : les services de l'étage sont à 4 ou 5 min de lui. Le résultat reste le même si l'on suppose que les URGENT partent surtout des Urgences (95 %).

### 4.4 Comparaison entre le test réel et la simulation

| Urgence | Attente moyenne Locust | Attente moyenne simulée (fourchette attendue) | Dans le délai : Locust | Dans le délai : simulation |
|---|---|---|---|---|
| URGENT | 2,0 min | 1,4 (0,2 à 3,1) | 60 % | 83 % (33 à 100 %) |
| HAUTE | 2,5 min | 1,4 (0,5 à 2,4) | 100 % | 100 % |
| MOYENNE | 2,1 min | 1,5 (0,8 à 2,0) | 100 % | 100 % |
| BASSE | 2,0 min | 1,5 (0,9 à 2,1) | 100 % | 100 % |

Les deux méthodes concordent sur le respect des délais. L'attente mesurée par Locust est supérieure d'environ 0,5 min. Ce surcoût vient de la méthode d'accélération : le téléphone virtuel interroge le serveur une fois par seconde réelle, soit 15 s d'hôpital à chaque étape. Avec seulement 5 URGENT, le résultat de Locust sur ce niveau reste dans la fourchette attendue.

Cette comparaison a aussi permis de corriger trois erreurs du script de test lui-même. Sans un second point de vue, elles auraient faussé les mesures :
- comptes d'agents de test restés disponibles sans utilisateur ;
- trajet nul compté comme 2 min ;
- clôture des missions en fin de test.

## 5. Sécurité : contrôle d'accès

Une matrice déclare, pour chacune des 36 routes de l'API, qui a le droit de l'appeler : public, tout utilisateur connecté, ou une liste de rôles. Des tests automatiques vérifient que :

1. la matrice couvre toutes les routes : une route ajoutée sans être déclarée fait échouer les tests, sa protection ne peut donc pas être oubliée ;
2. chaque rôle non autorisé reçoit un refus (403) sur chaque route ;
3. sans jeton, avec un jeton falsifié ou avec une authentification d'un autre type, l'accès est refusé (401) ;
4. un compte désactivé perd l'accès immédiatement, même avec un jeton encore valide ;
5. un médecin ne peut pas consulter les missions d'un autre médecin. La réponse est « introuvable » (404) plutôt que « interdit », pour ne pas révéler leur existence.

L'efficacité des tests a été vérifiée : en ouvrant volontairement une route réservée au régulateur à un médecin, les tests ont bien échoué. L'ensemble du backend compte désormais 210 tests automatiques, tous réussis.

## 6. Limites

- **Années de référence.** Les annuaires 2020 et 2021 couvrent la période de la COVID-19, où l'activité hospitalière a pu être inhabituelle.
- **Complétude des données.** L'annuaire signale lui-même que les données des établissements publics de santé remontées dans DHIS2 sont parfois incomplètes. Le chiffre de l'Hôpital Principal de Dakar (2 449 hospitalisations pour 94 909 journées) étant incohérent, il n'a pas été retenu.
- **Transports par séjour.** Aucune donnée publiée n'existe sur ce point : il a été traité par une analyse de sensibilité (2 à 4).
- **Plan de l'hôpital.** Les distances viennent du plan simplifié du prototype (deux niveaux, temps de couloir estimés), et non du plan réel de l'HOGIP. Les conclusions sur les URGENT dépendent directement de ces distances.
- **Origine des URGENT.** La variante « URGENT surtout depuis les Urgences » est une hypothèse sans donnée.
- **Accélération du temps.** Elle introduit un léger surcoût dans les attentes mesurées par Locust (environ 0,5 min). Par ailleurs, les délais fixes du serveur ne sont pas accélérés : délais de réponse, exclusion de 5 min après un refus.
- **Environnement de test.** Les tests ont tourné sur un ordinateur portable, et non sur un serveur hospitalier. L'essai à 50 agents n'a duré que 2 minutes.

## 7. Perspectives

- Ajouter dans l'application un réglage « agent réservé aux URGENT » et un poste d'attente par agent, pour appliquer la recommandation du § 4.3.
- Refaire l'analyse avec le plan réel de l'HOGIP et des relevés de transports sur quelques semaines (nombre par séjour, origine des URGENT).
- Recalibrer les hypothèses avec un annuaire hors période COVID dès sa publication.

## Reproduire les résultats

Tout se trouve dans `loadtest/` (voir `loadtest/README.md`) :
- `python hypotheses.py` : les débits de demandes ;
- `python analyse_file_attente.py` : les tableaux 4.2 et 4.3, environ 20 s ;
- `locust -f locustfile.py ...` : les tests de charge ;
- `python analyse_file_attente.py --comparer resultats/<test>_synthese.json` : la comparaison 4.4 ;
- `pytest tests/test_securite.py` (dans `backend/`) : la sécurité.
