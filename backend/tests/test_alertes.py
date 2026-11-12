# Appel du régulateur par un agent bloqué, et traitement de l'alerte sur le dashboard

import pytest

from database import SessionLocal
from models.patient import Patient
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, REANIMATION = 1, 13

MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


@pytest.fixture()
def reg(client):
    db = SessionLocal()
    charger_graphe_json(db)
    db.add(Patient(id=1, id_hospitalisation="00000001", prenom="Jean", nom="Dupont", code_bracelet="QR-00000001"))
    db.commit()
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


@pytest.fixture()
def medecin(client, reg):
    client.post("/auth/register", json=MEDECIN, headers=reg)
    return login(client, "diallo@test.fr", "medecin123")


def agent(client, reg, identifiant):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": URGENCES}, headers=entetes)
    return agent_id, entetes


def mission(client, medecin, entetes, accepter=True):
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "URGENT"}).json()
    if accepter:
        client.put(f"/missions/{m['id']}/accept", headers=entetes)
    return m["id"]


def appeler(client, mission_id, entetes, raison="BRACELET_ILLISIBLE"):
    return client.post(f"/missions/{mission_id}/appel-regulateur", json={"raison": raison}, headers=entetes)


def test_l_agent_appelle_le_regulateur(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a")
    mission_id = mission(client, medecin, entetes)

    r = appeler(client, mission_id, entetes)
    assert r.status_code == 201, r.text
    alerte = r.json()
    assert alerte["mission_id"] == mission_id and alerte["brancardier_id"] == agent_id
    assert alerte["raison"] == "BRACELET_ILLISIBLE" and alerte["lieu_nom"] == "Urgences"
    assert alerte["traitee"] is False

    # Le régulateur la voit dans les alertes en cours
    en_cours = client.get("/alertes?traitee=false", headers=reg).json()
    assert [a["id"] for a in en_cours] == [alerte["id"]]


def test_un_second_appel_ne_cree_pas_de_doublon(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission(client, medecin, entetes)
    premier = appeler(client, mission_id, entetes).json()
    second = appeler(client, mission_id, entetes, raison="ECHECS_SCAN").json()
    assert second["id"] == premier["id"]
    assert len(client.get("/alertes", headers=reg).json()) == 1


def test_le_regulateur_traite_l_alerte(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission(client, medecin, entetes)
    alerte_id = appeler(client, mission_id, entetes).json()["id"]

    r = client.put(f"/alertes/{alerte_id}/traiter", headers=reg)
    assert r.status_code == 200, r.text
    assert r.json()["traitee"] is True and r.json()["date_traitement"] is not None
    assert client.get("/alertes?traitee=false", headers=reg).json() == []
    assert len(client.get("/alertes?traitee=true", headers=reg).json()) == 1
    # Après traitement, un nouvel appel crée une nouvelle alerte
    assert appeler(client, mission_id, entetes).json()["id"] != alerte_id


def test_appel_seulement_sur_sa_mission_en_cours(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    _, autre = agent(client, reg, "b")
    mission_id = mission(client, medecin, entetes, accepter=False)   # proposée, pas encore acceptée
    assert appeler(client, mission_id, entetes).status_code == 409
    assert appeler(client, mission_id, autre).status_code == 404
    assert appeler(client, 999, entetes).status_code == 404
    assert appeler(client, mission_id, entetes, raison="INCONNUE").status_code == 422


def test_alertes_reservees_au_regulateur(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    assert client.get("/alertes", headers=entetes).status_code == 403
    assert client.get("/alertes", headers=medecin).status_code == 403
    assert client.put("/alertes/1/traiter", headers=medecin).status_code == 403
    assert client.put("/alertes/999/traiter", headers=reg).status_code == 404
