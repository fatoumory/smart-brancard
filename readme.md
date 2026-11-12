# Smart-Brancard

Système intelligent d'optimisation des flux de brancardage à l'hôpital (projet Cardio-Connect).

Un médecin ou un infirmier demande le transport d'un patient. L'application calcule l'itinéraire le plus rapide dans l'hôpital (algorithme de Dijkstra), puis l'attribue à un brancardier. Chaque étape est tracée dans un journal d'audit horodaté.

## Architecture

| Brique | Technologie | Rôle |
|---|---|---|
| Backend | Python, FastAPI | API REST, logique métier, Dijkstra |
| Base de données | PostgreSQL + PostGIS (Docker) | Comptes, patients, missions, graphe de l'hôpital, historique |
| Temps réel | WebSocket `/ws`, Redis Pub/Sub (Docker) | Les écrans sont prévenus dès qu'une donnée change |
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

Le régulateur crée les autres comptes depuis http://localhost:8000/docs (`POST /auth/register`, rôle `MEDECIN` ou `BRANCARDIER`). Il imprime ensuite la carte de connexion des brancardiers depuis l'écran **Comptes**. Le médecin admet un patient introuvable directement depuis la demande de transport.

Pour une démonstration, ouvrir l'écran **Simulateur** du régulateur : il remplace les badges BLE et fait se déplacer les agents de salle en salle.

**Après chaque `git pull`** : relancer `pip install -r requirements.txt` et `alembic upgrade head` dans `backend/`.

## Rôles

| Rôle | Ce qu'il peut faire |
|---|---|
| `REGULATEUR` | Créer, désactiver les comptes et générer les cartes de connexion, superviser toutes les missions, réaffecter, annuler ou clôturer une mission, traiter les alertes, bloquer un ascenseur ou un couloir, faire tourner le simulateur de badges |
| `MEDECIN` | Prescripteur (médecin ou infirmier) : admettre un patient, créer une mission, suivre ses propres demandes |
| `BRANCARDIER` | Recevoir, accepter ou refuser les missions, scanner le bracelet (et les tags de salle en secours), appeler le régulateur, changer son statut (disponible, pause de 30 ou 45 min, indisponible) |

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
| `POST /auth/carte` | brancardier | Connexion en scannant sa carte QR (même jeton de 8 h) |
| `POST /auth/register` | régulateur | Créer un compte |
| `PATCH /utilisateurs/{id}` | régulateur | Désactiver ou réactiver un compte (jamais de suppression) |
| `POST /utilisateurs/{id}/carte` | régulateur | Générer la carte de connexion d'un brancardier (l'ancienne ne fonctionne plus) |
| `PATCH /utilisateurs/me/statut` | brancardier | Disponible, pause de 30 ou 45 min, indisponible |
| `POST /patients` | prescripteur | Admettre un patient (IPP et bracelet `QR-<IPP>` générés, identité provisoire possible) |
| `GET /patients?recherche=` | prescripteur | Rechercher un patient par nom, prénom ou IPP |
| `PATCH /patients/{id}` | prescripteur | Valider ou corriger une identité (l'IPP ne change jamais) |
| `GET /noeuds` | tous | Lieux de l'hôpital (`?type_noeud=SERVICE` pour les formulaires) |
| `GET /aretes` · `PATCH /aretes/{id}` | régulateur | Voir, bloquer ou débloquer un couloir ou un ascenseur |
| `POST /missions/create` | prescripteur | Créer une mission. L'itinéraire est calculé et enregistré |
| `GET /missions` | régulateur, prescripteur | Missions triées par urgence. Un prescripteur ne voit que les siennes |
| `GET /missions/{id}` | régulateur, prescripteur | Détail d'une mission |
| `GET /missions/{id}/historique` | régulateur, prescripteur | Journal d'audit de la mission |
| `GET /missions/moi` · `GET /missions/moi/journal` | brancardier | Sa mission en cours ; ses missions terminées du jour |
| `PUT /missions/{id}/accept` · `PUT /missions/{id}/refuse` | brancardier | Répondre à une mission proposée (refus avec motif) |
| `POST /missions/{id}/scan-depart` | brancardier | Prise en charge : bracelet, plus le tag de la salle si le badge n'a pas été détecté |
| `POST /missions/{id}/scan-arrivee` · `POST /missions/{id}/arrivee` | brancardier | Clôture de secours : par le tag de la salle, ou bouton « Arrivé » |
| `POST /missions/{id}/appel-regulateur` | brancardier | Appeler le régulateur (bracelet illisible, scans refusés) |
| `PUT /missions/{id}/reaffecter` · `annuler` · `cloturer` | régulateur | Réaffecter ou annuler avant le transport ; clôturer une mission restée en transit |
| `GET /alertes` · `PUT /alertes/{id}/traiter` | régulateur | Alertes en cours (appels des agents), et leur traitement |
| `POST /detections/badge` | régulateur | Simulateur de badges : le badge d'un agent est capté dans une salle |
| `GET /missions/saturation` | régulateur | Saturation de la flotte : missions en attente, en retard, agents disponibles, ordre de la file |
| `WS /ws` | tous | Temps réel : après connexion (1er message `{"jeton": ...}`), reçoit `{"type": "maj", "sujets": [...]}` à chaque changement |

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
| Connexion | `/login` | Choix du profil, puis identifiant et mot de passe. Le brancardier peut aussi scanner sa carte (« Scanner ma carte ») |
| Dashboard du régulateur | `/regulateur` | Bandeau « Saturation flotte », appels des agents, 5 indicateurs, file des missions (réaffecter, annuler, clôturer), agents et leur position, activité de la journée, blocage des ascenseurs et couloirs. Mis à jour en temps réel |
| Simulateur de badges | `/regulateur/simulateur` | Plan de l'hôpital : on pose chaque agent dans une salle, son badge y est capté toutes les 5 s |
| Comptes | `/regulateur/comptes` | Impression des cartes de connexion, désactivation et réactivation des comptes |
| Demande de transport | `/medecin` | Recherche du patient (ou admission s'il est introuvable), urgence et délai garanti, départ et arrivée, matériel, consigne |
| Mes demandes · Suivi | `/medecin/demandes` · `/medecin/suivi/{id}` | Les demandes du médecin, puis les étapes de chacune avec l'agent, sa position et l'arrivée estimée |
| Brancardier | `/brancardier` | Application mobile : annonce vocale des missions, accepter ou refuser (motifs en images), caméra ouverte seule au départ, bracelet seul, arrivée détectée, bouton « Arrivé », appel au régulateur, pauses, mode hors ligne |

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
- Sur un vrai téléphone, l'installation exige le HTTPS (voir ci-dessous).
- Les icônes sont générées à partir de `frontend/public/logo.svg` avec `npm run generate-pwa-assets`.

### Tester sur un vrai téléphone (caméra, NFC)

La caméra (scan du bracelet QR) et Web NFC (tags muraux) ne fonctionnent qu'en **HTTPS**. Le PC et le téléphone doivent être sur le même Wi-Fi. Backend lancé normalement, puis dans `frontend/` :
```powershell
npm run dev:mobile
```
Ouvrir sur le téléphone l'adresse **https://&lt;IP du PC&gt;:5173** affichée par Vite (ligne « Network »), puis accepter l'avertissement du certificat auto-signé (« Paramètres avancés » → « Continuer »).

- Les appels à l'API passent par le proxy `/api` du serveur Vite : pas de réglage CORS à changer côté backend.
- **NFC** : Chrome sur Android uniquement. Chaque tag contient un enregistrement texte avec le code de la salle (ex. `NFC-RDC-URG`, voir `backend/data/graphe_hopital.json`) ; une application comme « NFC Tools » permet de l'écrire.
- **Secours** (téléphone sans NFC, démonstration) : un QR code contenant le même texte, collé à côté du tag, se scanne avec la caméra. La saisie au clavier reste possible en dernier recours.
- Le bracelet du patient est un QR code contenant `QR-<IPP>` (ex. `QR-00000004`).

## Organisation du frontend

```
frontend/src/
├── pages/        Un fichier par écran (Login, Regulateur, Medecin, SuiviDemande, Brancardier)
├── components/   Éléments réutilisables : en-tête, badges, recherche de patient, cartes du dashboard
├── services/     Appels à l'API (api.js ajoute le jeton JWT), connexion, libellés des urgences et statuts
├── hooks/        useDonnees : chargement des données, rechargées par le temps réel (WebSocket)
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
- **Badges BLE (Sprint 4)** : un récepteur de salle signale le badge d'un agent (`POST /detections/badge`) ; dans le prototype, c'est le simulateur de badges. Chaque détection garde son origine (badge, scan ou déclaration) : seuls le badge et le scan prouvent la présence. Avec le badge, le bracelet suffit au départ ; 30 s de présence dans la salle d'arrivée terminent la mission (méthode `BALISE`) ; l'agent redevient disponible à sa sortie, ou 10 min après. Le tag de la salle, le bouton « Arrivé » et la clôture par le régulateur restent en secours.
- **Pauses** : 30 min, ou 45 min pour le repas, refusées si elles laisseraient moins de `MIN_AGENTS_DISPONIBLES` agents disponibles (`.env`, 1 par défaut). Le serveur remet l'agent disponible à la fin.
- **Carte de connexion** : le régulateur génère pour chaque brancardier un code imprimé en QR, donné une seule fois ; seule son empreinte SHA-256 est gardée. Une nouvelle carte rend l'ancienne inutilisable ; le mot de passe reste valable.
- **Actions hors ligne** : le téléphone peut renvoyer une action avec son heure réelle (`horodatage_client`), refusée si elle est dans le futur, avant la mission ou vieille de plus de 30 min ; le journal garde les deux heures. Une action déjà enregistrée et renvoyée n'est pas comptée deux fois.
- **File d'attente avec vieillissement** : l'URGENT passe toujours en premier ; les autres missions sont servies par échéance (création + délai garanti). Une mission BASSE qui attend depuis longtemps passe donc devant une MOYENNE qui vient d'arriver. La flotte est « saturée » quand au moins `SEUIL_SATURATION` missions (`.env`, 3 par défaut) attendent et qu'il y en a plus que d'agents disponibles.
- **Temps réel** : à chaque validation en base, le serveur repère les tables modifiées et envoie seulement le sujet (`missions`, `agents`, `alertes`, `graphe`) aux écrans connectés au WebSocket `/ws`. L'écran recharge alors ses données par les routes habituelles, qui vérifient les droits : aucune donnée patient ne passe par le WebSocket. Avec `REDIS_URL`, les sujets passent par Redis Pub/Sub, pour plusieurs processus du serveur. Les écrans se rechargent aussi toutes les 30 s, en secours.
- **Annonces vocales** : sonnerie (Web Audio), vibration (Android) et voix française du navigateur. Le navigateur bloque le son avant un premier toucher : le bouton « Activer le son » le débloque à l'ouverture.
- **Hors ligne côté téléphone** : seule la mission en cours est gardée, et elle est effacée à la déconnexion. Les actions faites sans réseau attendent, puis partent dans l'ordre, avec leur heure réelle, au retour du réseau.

## Avancement

- [x] Sprint 0 : environnement (Docker, PostgreSQL + PostGIS, Redis)
- [x] Sprint 1 : authentification JWT, rôles, modèles de données
- [x] Sprint 2 (backend) : graphe, Dijkstra, missions, admission des patients, historique, routes de lecture
- [x] Sprint 2 (frontend) : application installable (PWA), dashboard du régulateur, demande de transport et suivi du médecin
- [x] Sprint 3 : attribution automatique, application mobile du brancardier, scans NFC et QR
- [x] Sprint 4 : parcours à gestes réduits (badges simulés, bracelet seul, arrivée détectée, annonce vocale), pauses, appels au régulateur, carte de connexion, hors ligne, comptes, temps réel (WebSocket, Redis), saturation de la flotte. La dictée vocale (Whisper) passe en perspective
- [ ] Sprint 5 : tests de charge (Locust), données MIMIC-III, lancement en une commande
