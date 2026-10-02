# Smart-Brancard

Système intelligent d'optimisation des flux de brancardage à l'hôpital (projet Cardio-Connect).

Un médecin ou un infirmier demande le transport d'un patient. L'application calcule l'itinéraire le plus rapide dans l'hôpital (algorithme de Dijkstra), puis l'attribue à un brancardier. Chaque étape est tracée dans un journal d'audit horodaté.

## Architecture

| Brique | Technologie | Rôle |
|---|---|---|
| Backend | Python, FastAPI | API REST, logique métier, Dijkstra |
| Base de données | PostgreSQL + PostGIS (Docker) | Comptes, patients, missions, graphe de l'hôpital, historique |
| Temps réel | Redis (Docker) | Statuts des agents, file d'attente (Sprint 4) |
| Frontend | React, Vite (PWA) | Dashboard du régulateur, interface Médecin, application du brancardier |

## Lancer le projet

Prérequis : Docker Desktop, Python 3.10 ou plus, Node.js.

**1. Configuration (une seule fois)**
```powershell
copy .env.example .env
copy backend\.env.example backend\.env
```
Dans `backend/.env`, renseigner `SECRET_KEY`. Le fichier explique comment la générer.

**2. Base de données**
```powershell
docker compose up -d
```

**3. Backend** (dans `backend/`)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
python seed_graphe.py
python seed.py --nom-utilisateur regulateur@hopital.fr --nom Diallo --prenom Awa
uvicorn main:app --reload
```
- `alembic upgrade head` crée et met à jour les tables.
- `seed_graphe.py` charge le plan de l'hôpital.
- `seed.py` crée le premier compte régulateur. Le mot de passe est demandé, et sa saisie est masquée.

L'API répond sur http://localhost:8000, et sa documentation interactive est sur **http://localhost:8000/docs**.

**4. Frontend** (dans `frontend/`)
```powershell
npm install
npm run dev
```
L'application est disponible sur http://localhost:5173.

**Après chaque `git pull`** : relancer `pip install -r requirements.txt` et `alembic upgrade head` dans `backend/`.

## Rôles

| Rôle | Ce qu'il peut faire |
|---|---|
| `REGULATEUR` | Créer les comptes, superviser toutes les missions, bloquer un ascenseur ou un couloir |
| `MEDECIN` | Prescripteur (médecin ou infirmier) : admettre un patient, créer une mission, suivre ses propres demandes |
| `BRANCARDIER` | Changer son statut (disponible, pause…). La réception et la réalisation des missions arrivent au Sprint 3 |

## Le graphe de l'hôpital

Le plan est décrit dans `backend/data/graphe_hopital.json` :
- **20 nœuds sur 2 niveaux** (RDC et étage 1) : 8 services, 6 couloirs, 4 nœuds d'ascenseur (2 ascenseurs × 2 étages) et 2 dépôts de matériel, un par étage, chacun avec fauteuils, lits et oxygène ;
- **20 arêtes**, dont le poids est un temps de trajet **en minutes**. Pour un ascenseur, ce poids vaut l'attente moyenne plus la durée du trajet : A = 2,5 min, B = 1,5 min ;
- **pas d'escalier** : un brancard passe toujours par un ascenseur.

Dijkstra (NetworkX) calcule le plus court chemin. Une arête **bloquée** par le régulateur (ascenseur en panne, couloir fermé) est exclue du calcul suivant.

| Trajet de référence | Durée | Passage |
|---|---|---|
| Urgences → Réanimation | 5,0 min | ascenseur B |
| Urgences → Bloc opératoire | 4,0 min | ascenseur A |
| Urgences → Bloc, ascenseur A bloqué | 7,0 min | détour par l'ascenseur B |

## Principales routes de l'API

| Route | Rôle | Usage |
|---|---|---|
| `POST /auth/login` | tous | Connexion, renvoie un jeton JWT valable 8 h |
| `POST /auth/register` | régulateur | Créer un compte |
| `POST /patients` | prescripteur | Admettre un patient (IPP et bracelet `QR-<IPP>` générés, identité provisoire possible) |
| `GET /patients?recherche=` | prescripteur | Rechercher un patient par nom, prénom ou IPP |
| `PATCH /patients/{id}` | prescripteur | Valider ou corriger une identité (l'IPP ne change jamais) |
| `GET /noeuds` | tous | Lieux de l'hôpital (`?type_noeud=SERVICE` pour les formulaires) |
| `GET /aretes` · `PATCH /aretes/{id}` | régulateur | Voir, bloquer ou débloquer un couloir ou un ascenseur |
| `POST /missions/create` | prescripteur | Créer une mission. L'itinéraire est calculé et enregistré |
| `GET /missions` | régulateur, prescripteur | Missions triées par urgence. Un prescripteur ne voit que les siennes |
| `GET /missions/{id}` | régulateur, prescripteur | Détail d'une mission |
| `GET /missions/{id}/historique` | régulateur, prescripteur | Journal d'audit de la mission |

La liste complète, avec les formats et les codes d'erreur, se trouve dans http://localhost:8000/docs.

## Organisation du backend

```
backend/
├── models/       Tables de la base (SQLAlchemy)
├── schemas/      Données reçues et renvoyées par l'API (Pydantic)
├── routes/       Routes de l'API : reçoivent la requête, vérifient les droits, répondent
├── services/     Logique métier réutilisable (Dijkstra, admission, historique, authentification)
├── migrations/   Évolutions de la base (Alembic)
├── data/         Plan de l'hôpital (graphe_hopital.json)
└── tests/        Tests automatiques (pytest)
```

## Tests

Dans `backend/`, avec le venv activé :
```powershell
pytest -q
```
Les tests utilisent une base SQLite temporaire : Docker n'est pas nécessaire.

## Choix importants

- **Admission des patients** : le patient est enregistré à son arrivée (IPP généré). Une mission ne crée jamais de patient. Ce module simule le logiciel d'admission de l'hôpital. Dans un vrai déploiement, il pourrait être remplacé par un connecteur HL7 ou FHIR.
- **Identité provisoire** : un patient inconscient est admis sous le nom « INCONNU X-&lt;IPP&gt; », transporté normalement, puis identifié plus tard.
- **Journal d'audit immuable** : chaque changement de statut d'une mission ajoute une ligne horodatée. Un déclencheur PostgreSQL interdit de les modifier ou de les supprimer (CDC §7.3).
- **Aucune donnée clinique** n'est stockée, seulement l'identité et la logistique du transport (CDC §7.2).

## Avancement

- [x] Sprint 0 : environnement (Docker, PostgreSQL + PostGIS, Redis)
- [x] Sprint 1 : authentification JWT, rôles, modèles de données
- [x] Sprint 2 (backend) : graphe, Dijkstra, missions, admission des patients, historique, routes de lecture
- [ ] Sprint 3 : attribution automatique, application mobile du brancardier, scans NFC et QR
- [ ] Sprint 4 : dictée vocale (Whisper), temps réel (WebSockets, Redis)
- [ ] Sprint 5 : tests de charge (Locust), données MIMIC-III, lancement en une commande
