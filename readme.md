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

Si le backend ne tourne pas sur http://localhost:8000, copier `frontend\.env.example` en `frontend\.env.local` et modifier `VITE_API_URL`.

**5. Comptes et données de test**

Le régulateur crée les autres comptes depuis http://localhost:8000/docs (`POST /auth/register`, rôle `MEDECIN` ou `BRANCARDIER`). Il n'y a pas encore d'écran d'admission : pour tester l'interface Médecin, admettre d'abord un patient avec `POST /patients`, connecté en médecin.

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

## Les écrans

Après la connexion, chaque rôle arrive sur son propre écran. Un utilisateur qui tape l'adresse d'un autre écran est renvoyé vers le sien.

| Écran | Adresse | Contenu |
|---|---|---|
| Connexion | `/login` | Choix du profil, puis identifiant et mot de passe. Le compte doit correspondre au profil choisi |
| Dashboard du régulateur | `/regulateur` | 4 indicateurs, file des missions triée par urgence avec filtres, itinéraire étape par étape (clic sur une ligne), agents et leur statut, activité de la journée. Rafraîchi toutes les 15 s |
| Demande de transport | `/medecin` | Recherche du patient admis (nom, prénom ou IPP), urgence et délai garanti, départ et arrivée choisis parmi les services, matériel, consigne |
| Suivi de la demande | `/medecin/suivi/{id}` | Les 4 étapes de la mission, avec l'heure de chacune lue dans le journal d'audit |
| Brancardier | `/brancardier` | Page provisoire : l'application mobile arrive au Sprint 3 |

Délais garantis selon l'urgence : **URGENT 3 min**, **HAUTE 8 min**, **MOYENNE 15 min**, **BASSE 30 min**.

## Application installable (PWA)

Le frontend est une Progressive Web App : on l'installe depuis le navigateur, sans passer par un store, et elle s'ouvre en plein écran comme une application.

Pour l'essayer, dans `frontend/` :
```powershell
npm run build
npm run preview
```
Ouvrir http://localhost:4173 dans Chrome, puis cliquer sur l'icône « Installer » de la barre d'adresse.

- Le service worker ne met en cache que les fichiers de l'application (JS, CSS, icônes), **jamais les réponses de l'API** : aucune donnée patient ne reste sur l'appareil (CDC §7.2).
- Une nouvelle version déployée est récupérée automatiquement.
- Sur un vrai téléphone, l'installation exige le HTTPS (prévu au Sprint 3).
- Les icônes sont générées à partir de `frontend/public/logo.svg` avec `npm run generate-pwa-assets`.

## Organisation du frontend

```
frontend/src/
├── pages/        Un fichier par écran (Login, Regulateur, Medecin, SuiviDemande, Brancardier)
├── components/   Éléments réutilisables : en-tête, badges, recherche de patient, cartes du dashboard
├── services/     Appels à l'API (api.js ajoute le jeton JWT), connexion, libellés des urgences et statuts
├── hooks/        useDonnees : chargement des données et rafraîchissement automatique
└── routes/       RouteProtegee : accès à un écran selon le rôle
```

Les valeurs échangées avec l'API (urgences, statuts, matériel…) sont celles des énumérations du backend (`backend/models/enums.py`). Leurs libellés et leurs couleurs sont définis une seule fois, dans `frontend/src/services/referentiel.js`.

## Tests

Dans `backend/`, avec le venv activé :
```powershell
pytest -q
```
Les tests utilisent une base SQLite temporaire : Docker n'est pas nécessaire.

Dans `frontend/`, vérification du code et compilation :
```powershell
npm run lint
npm run build
```

## Choix importants

- **Admission des patients** : le patient est enregistré à son arrivée (IPP généré). Une mission ne crée jamais de patient. Ce module simule le logiciel d'admission de l'hôpital. Dans un vrai déploiement, il pourrait être remplacé par un connecteur HL7 ou FHIR.
- **Identité provisoire** : un patient inconscient est admis sous le nom « INCONNU X-&lt;IPP&gt; », transporté normalement, puis identifié plus tard.
- **Journal d'audit immuable** : chaque changement de statut d'une mission ajoute une ligne horodatée. Un déclencheur PostgreSQL interdit de les modifier ou de les supprimer (CDC §7.3).
- **Aucune donnée clinique** n'est stockée, seulement l'identité et la logistique du transport (CDC §7.2).
- **Session de 8 h côté frontend** : le jeton JWT est gardé dans le navigateur. Un jeton expiré, ou une réponse 401 de l'API, renvoie à l'écran de connexion. La déconnexion efface le jeton et le rôle.
- **Rafraîchissement périodique** : le dashboard se met à jour toutes les 15 s et le suivi du médecin se rafraîchit à la demande. Les WebSockets du Sprint 4 remplaceront ces mécanismes.

## Avancement

- [x] Sprint 0 : environnement (Docker, PostgreSQL + PostGIS, Redis)
- [x] Sprint 1 : authentification JWT, rôles, modèles de données
- [x] Sprint 2 (backend) : graphe, Dijkstra, missions, admission des patients, historique, routes de lecture
- [x] Sprint 2 (frontend) : application installable (PWA), dashboard du régulateur, demande de transport et suivi du médecin
- [ ] Sprint 3 : attribution automatique, application mobile du brancardier, scans NFC et QR
- [ ] Sprint 4 : dictée vocale (Whisper), temps réel (WebSockets, Redis)
- [ ] Sprint 5 : tests de charge (Locust), données MIMIC-III, lancement en une commande
