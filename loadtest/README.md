# Tests de charge (Sprint 5)

Des brancardiers, un médecin et un régulateur virtuels utilisent l'API comme dans la réalité :
le médecin demande des transports, les agents acceptent (90 %) ou refusent, vont chercher le patient,
scannent son bracelet, le transportent et appuient sur « Arrivé ».

## Hypothèses

Elles sont dans [hypotheses.py](hypotheses.py) et viennent de l'*Annuaire des statistiques sanitaires et
sociales* du Ministère de la Santé et de l'Action sociale (éditions 2020 et 2021). L'hôpital de référence est
l'Hôpital Général Idrissa Pouye (Dakar) : 12 615 hospitalisations en 2021, soit environ 35 admissions par jour.

Seul le nombre de transports par séjour est supposé : 3 par défaut, testé de 2 à 4.

```
python hypotheses.py      # affiche les demandes par heure utilisées
```

## Scénarios

| Scénario | Agents | Demande | But |
|---|---|---|---|
| `realiste` (défaut) | 8 | journée, environ 8 demandes/h | attente avant prise en charge par urgence, comparée au modèle de file d'attente |
| `charge` | 50 | pic, temps accéléré ×60 | le serveur tient-il ? (temps de réponse, erreurs) |

Variables possibles : `SCENARIO`, `NB_AGENTS`, `PERIODE` (`journee`, `pic`, `nuit`), `TRANSPORTS` (2 à 4),
`ACCEL` (accélération du temps), `DUREE_MIN` (durée en minutes réelles, 6 par défaut).

Le script lance lui-même tous les acteurs : inutile de passer `-u`, `-r` ou `--run-time` à Locust.
Le chronomètre part après la préparation des comptes et des patients.

**Temps accéléré.** Avec `ACCEL=10`, une heure d'hôpital dure 6 minutes : les demandes arrivent 10 fois plus
vite et chaque étape (trajet, installation, transport) dure 10 fois moins. Les attentes mesurées sont
remises à l'échelle réelle dans les résultats. Limite : les délais fixes du serveur (30 à 60 s pour répondre,
exclusion de 5 min après un refus, preuve de présence de 2 min) ne sont pas accélérés.

## Lancement

Prérequis : le backend tourne (`uvicorn main:app` dans `backend/`, avec la base Docker) et un compte
régulateur existe. Le script crée lui-même ses comptes de test (`locust.*@smartbrancard.local`) et des
patients à identité inconnue.

Utiliser `127.0.0.1` et non `localhost` : sous Windows, `localhost` essaie d'abord l'IPv6 et ajoute
environ 2 s à chaque nouvelle connexion, ce qui fausserait les temps mesurés.

```bash
source backend/venv/Scripts/activate
pip install -r loadtest/requirements.txt
cd loadtest

# Scénario réaliste : 1 h d'hôpital (6 min réelles)
REG_UTILISATEUR=<regulateur> REG_MOT_DE_PASSE=<mot de passe> \
  locust -f locustfile.py --headless --host http://127.0.0.1:8000 --csv resultats/realiste

# Sensibilité : 4 transports par séjour, au pic
TRANSPORTS=4 PERIODE=pic REG_UTILISATEUR=... REG_MOT_DE_PASSE=... \
  locust -f locustfile.py --headless --host http://127.0.0.1:8000

# Montée en charge : 50 agents pendant 5 min
SCENARIO=charge DUREE_MIN=5 REG_UTILISATEUR=... REG_MOT_DE_PASSE=... \
  locust -f locustfile.py --headless --host http://127.0.0.1:8000 --csv resultats/charge
```

Sans `--headless`, l'interface de Locust s'ouvre sur http://localhost:8089 (courbes en direct).

## Résultats (`resultats/`, non versionné)

- `*_missions.csv` : une ligne par mission, avec l'attente avant prise en charge (minutes d'hôpital)
  et si le délai garanti est respecté ;
- `*_synthese.json` : par urgence, l'attente moyenne, le 90e percentile et la part dans le délai ;
- avec `--csv`, les fichiers de Locust : temps de réponse de chaque route, erreurs.

À la fin, les missions de test encore en cours sont annulées.
