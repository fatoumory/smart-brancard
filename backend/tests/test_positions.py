# Position des agents : détections de balises BLE (simulées) et dernière position connue

import pytest

from database import SessionLocal
from models.enums import StatutMission
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, REANIMATION = 1, 2, 13

BRANCARDIER_A = {"nom_utilisateur": "cisse@test.fr", "prenom": "Amadou", "nom": "Cissé",
                 "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
BRANCARDIER_B = {"nom_utilisateur": "diop@test.fr", "prenom": "Fatou", "nom": "Diop",
                 "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


@pytest.fixture()
def reg(client):
    db = SessionLocal()
    charger_graphe_json(db)
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


def compte(client, reg, donnees):
    client.post("/auth/register", json=donnees, headers=reg)
    return login(client, donnees["nom_utilisateur"], donnees["mot_de_passe"])


def test_statut_accepte_existe():
    # Ordre du cycle de vie : PROPOSE -> ACCEPTE -> EN_TRANSIT
    noms = [s.value for s in StatutMission]
    assert noms.index("PROPOSE") < noms.index("ACCEPTE") < noms.index("EN_TRANSIT")


def test_detection_et_position(client, reg):
    agent = compte(client, reg, BRANCARDIER_A)
    assert client.get("/detections/me", headers=agent).json() is None  # jamais détecté

    r = client.post("/detections", json={"noeud_id": URGENCES}, headers=agent)
    assert r.status_code == 201, r.text
    assert r.json()["noeud_nom"] == "Urgences"

    # La position est la dernière détection
    client.post("/detections", json={"noeud_id": RADIOLOGIE}, headers=agent)
    assert client.get("/detections/me", headers=agent).json()["noeud_id"] == RADIOLOGIE


def test_position_dans_la_liste_des_agents(client, reg):
    a = compte(client, reg, BRANCARDIER_A)
    compte(client, reg, BRANCARDIER_B)  # B n'est jamais détecté
    client.post("/detections", json={"noeud_id": URGENCES}, headers=a)
    client.post("/detections", json={"noeud_id": REANIMATION}, headers=a)

    agents = {u["nom_utilisateur"]: u for u in
              client.get("/utilisateurs?role=BRANCARDIER", headers=reg).json()}
    assert agents["cisse@test.fr"]["position_noeud_id"] == REANIMATION
    assert agents["cisse@test.fr"]["position_noeud_nom"] == "Réanimation"
    assert agents["cisse@test.fr"]["position_date"] is not None
    assert agents["diop@test.fr"]["position_noeud_id"] is None


def test_detection_lieu_inconnu(client, reg):
    agent = compte(client, reg, BRANCARDIER_A)
    assert client.post("/detections", json={"noeud_id": 999}, headers=agent).status_code == 404


def test_detection_reservee_aux_brancardiers(client, reg):
    medecin = compte(client, reg, MEDECIN)
    assert client.post("/detections", json={"noeud_id": URGENCES}, headers=medecin).status_code == 403
    assert client.post("/detections", json={"noeud_id": URGENCES}, headers=reg).status_code == 403
    assert client.post("/detections", json={"noeud_id": URGENCES}).status_code == 401
