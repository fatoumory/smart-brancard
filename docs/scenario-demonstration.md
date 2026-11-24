# Scénario de démonstration : le nouveau parcours

Ce scénario montre, en une quinzaine de minutes, le parcours complet d'un transport avec le simulateur de badges :
- la demande du médecin ;
- l'annonce vocale au brancardier ;
- le bracelet seul au départ ;
- l'arrivée détectée sans geste de l'agent.

Il montre aussi le réglage issu de l'analyse du Sprint 5 : des agents postés au centre de chaque étage et réservés aux URGENT.

Toutes les données viennent de `backend/seed_demo.py`, chargé automatiquement par `docker compose up` (`DEMO=1`).

## 1. Préparation (5 min avant)

1. Lancer l'application : `docker compose up --build` à la racine du projet (voir `readme.md`).
2. Imprimer `docs/demo/bracelets.html`, ou l'ouvrir sur un second écran : ce sont les bracelets des patients et les QR de secours des salles.
3. Ouvrir trois sessions séparées. Chaque session garde sa connexion dans le navigateur : il faut donc un navigateur, ou un profil, par personne.

| Qui | Où | Adresse | Identifiant (mot de passe `demo1234`) |
|---|---|---|---|
| Régulateur | PC, Chrome | http://localhost:8088 | `regulateur@demo.sn` |
| Médecin | PC, fenêtre de navigation privée | http://localhost:8088 | `dr.diallo@demo.sn` |
| Brancardier | Téléphone, même Wi-Fi que le PC | https://&lt;IP du PC&gt;:8443 | `ibrahima.fall@demo.sn` |

- **Sur le téléphone :** accepter l'avertissement du certificat (« Paramètres avancés », puis « Continuer »). Sans HTTPS, la caméra ne s'ouvre pas.
- **Sans téléphone :** une troisième fenêtre réduite à la largeur d'un téléphone (Edge par exemple) fait l'affaire. Le bracelet se tape alors au clavier.
- **Brancardier :** toucher « Activer le son » dès la connexion. Le navigateur bloque le son avant un premier toucher.

### L'équipe de démonstration

C'est l'équipe de jour recommandée par l'analyse de la file d'attente (rapport Sprint 5, § 4.3) : 4 agents polyvalents, et 2 agents postés au centre de chaque étage, réservés aux URGENT.

| Agent | Réglage | À poser dans le simulateur |
|---|---|---|
| Ousmane Gueye | posté au Hall central - RDC, **URGENT seulement** | Hall central - RDC |
| Khady Faye | postée au Palier central - Étage 1, **URGENT seulement** | Palier central - Étage 1 |
| Ibrahima Fall | polyvalent (le téléphone) | Consultations externes |
| Fatou Sow | polyvalente | Laboratoire |
| Cheikh Ba | polyvalent | Réanimation |
| Aminata Diop | polyvalente | Cardiologie |

**Régulateur :** ouvrir **Simulateur**, choisir chaque agent puis cliquer sur sa salle. Laisser cet onglet ouvert : il envoie les badges toutes les 5 s. Ouvrir le **Dashboard** dans un second onglet.

## 2. Le réglage « agent posté, réservé aux URGENT »

**Régulateur :** ouvrir **Comptes**.
- La colonne « Poste d'attente » montre le poste d'Ousmane et de Khady, avec la case « URGENT seulement » cochée.
- Dans **Agents terrain** du dashboard, ils portent le badge rouge « URGENT seulement ».

**À dire :** la simulation a montré que le délai URGENT de 3 min dépend surtout de la *place* des agents, pas de leur nombre.
- Avec 6 agents sans poste, 68 % des URGENT sont pris en charge à temps.
- Avec 2 agents postés au centre des étages et réservés aux URGENT, on passe à 94 %.
- Les autres missions restent dans leur délai dans 97 à 100 % des cas.

## 3. Transport ordinaire : la mission va au polyvalent

**Médecin :** nouvelle demande pour **Abdoulaye Diouf**, urgence **MOYENNE**, de **Urgences** vers **Radiologie**.

**Ce qu'on voit :**
- La mission est proposée à **Ibrahima**, à 2,0 min des Urgences.
- Ousmane est plus près, à 1,5 min, mais il est réservé aux URGENT : il reste libre.
- Le téléphone sonne, vibre et annonce la mission à voix haute.

**Brancardier :**
1. Toucher **Accepter**.
2. **Régulateur, simulateur :** cliquer sur « Rejoindre le patient : Urgences » sous Ibrahima. Le badge est capté aux Urgences.
3. **Téléphone :** la caméra s'ouvre seule. Scanner le bracelet **QR-90000001**, ou le taper. La voix dit « Bon patient » et la mission passe en transit.
   - Pour montrer la sécurité, scanner d'abord un autre bracelet : la voix dit « Mauvais patient ».
4. **Simulateur :** cliquer sur « Déposer le patient : Radiologie ». Après 30 s de présence dans la salle, la mission se termine seule (méthode `BALISE` dans le journal), sans aucun geste de l'agent.
5. **Simulateur :** poser Ibrahima dans une autre salle. Il a quitté la Radiologie, il redevient disponible.

**Médecin :** dans « Mes demandes », le suivi montre chaque étape, avec son heure.

## 4. Urgence vitale : l'agent posté part tout de suite

**Brancardier :** se déconnecter (onglet Profil), puis se connecter avec `khady.faye@demo.sn`.
- L'écran « Disponible » indique « Vous recevez seulement les missions URGENT » et son poste : Palier central - Étage 1.

**Médecin :** nouvelle demande pour **Ndeye Mbaye**, urgence **URGENT**, de **Salle de réveil** vers **Réanimation**.

**Ce qu'on voit :**
- La mission va à **Khady**, à 1,5 min de la Salle de réveil depuis son poste.
- Elle tient le délai de 3 min. Les polyvalents les plus proches sont en Réanimation et en Cardiologie, à plus de 3 min.

**Le parcours est le même qu'au point 3 :** accepter, « Rejoindre le patient » dans le simulateur, bracelet **QR-90000002**, puis « Déposer le patient ».

**Après la remise du patient :**
- Le téléphone affiche « Ensuite, retournez à votre poste : Palier central - Étage 1 ».
- Dans le simulateur, le bouton « Retour au poste » remet Khady à son poste. Elle est de nouveau prête pour la prochaine urgence.

## 5. Saturation : le régulateur garde la main

**Médecin :** créer **7 demandes BASSE** à la suite (patients 3 à 7, n'importe quels services).

**Ce qu'on voit :**
- Les 4 premières sont proposées aux 4 polyvalents. Les 3 suivantes attendent, car Ousmane et Khady sont libres mais réservés aux URGENT.
- Le dashboard affiche le bandeau **« Saturation flotte »** : « 3 missions en attente pour 2 agents disponibles. 2 de ces agents sont réservés aux URGENT. »

**Régulateur, dans Comptes :**
1. Décocher « URGENT seulement » pour Ousmane.
2. Il redevient polyvalent et reçoit aussitôt la première mission de la file.
3. Le dashboard se met à jour en temps réel.

C'est au régulateur d'arbitrer entre la réserve pour l'urgence vitale et l'écoulement des autres transports.

**Agents simulés sans téléphone :**
- Une mission proposée à Fatou, Cheikh ou Aminata reste sans réponse. Au bout de 60 s, elle passe à l'agent suivant.
- Après deux propositions laissées sans réponse, l'agent passe « Indisponible ».
- C'est le comportement prévu quand un agent ne répond pas.

**S'il reste du temps, l'ascenseur en panne :** dans le dashboard, bloquer l'ascenseur B. Une nouvelle demande d'Urgences vers Réanimation passe alors par l'ascenseur A.

## Remise à zéro

Pour repartir de données propres après une démonstration :
```powershell
docker compose down -v
docker compose up --build
```
**Attention :** `-v` efface **toute** la base, y compris les comptes et les missions créés pendant le développement. Au redémarrage, seuls les comptes, l'équipe et les patients de démonstration sont recréés.
