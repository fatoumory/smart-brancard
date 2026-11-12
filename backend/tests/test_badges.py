# Badges BLE simulés : le récepteur d'une salle (ici le simulateur) signale le badge d'un agent

import pytest

from database import SessionLocal
from models.patient import Patient
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, REANIMATION = 1, 2, 13
TAG_URGENCES, BRACELET = "NFC-RDC-URG", "QR-00000001"

AGENT = {"nom_utilisateur": "cisse@test.fr", "prenom": "Amadou", "nom": "Cissé",
         "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


@pytest.fixture()
def reg(client):
    db = SessionLocal()
    charger_graphe_json(db)
    db.add(Patient(id=1, id_hospitalisation="00000001", prenom="Jean", nom="Dupont", code_bracelet=BRACELET))
    db.commit()
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


@pytest.fixture()
def medecin(client, reg):
    client.post("/auth/register", json=MEDECIN, headers=reg)
    return login(client, "diallo@test.fr", "medecin123")


@pytest.fixture()
def agent(client, reg):
    """Un brancardier dont le badge est capté en Radiologie"""
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    badge(client, reg, agent_id, RADIOLOGIE)
    return agent_id, login(client, "cisse@test.fr", "brancard123")


def mission_acceptee(client, medecin, entetes):
    """Une mission Urgences -> Réanimation, acceptée par l'agent"""
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    assert client.put(f"/missions/{m['id']}/accept", headers=entetes).status_code == 200
    return m["id"]


def badge(client, entetes, brancardier_id, noeud_id):
    return client.post("/detections/badge", json={"brancardier_id": brancardier_id, "noeud_id": noeud_id},
                       headers=entetes)


def test_le_badge_donne_la_position_de_l_agent(client, reg):
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    r = badge(client, reg, agent_id, URGENCES)
    assert r.status_code == 201, r.text
    assert r.json()["brancardier_id"] == agent_id and r.json()["noeud_nom"] == "Urgences"

    # L'agent n'a rien fait : sa position est connue grâce au badge
    badge(client, reg, agent_id, RADIOLOGIE)
    agent = login(client, "cisse@test.fr", "brancard123")
    assert client.get("/detections/me", headers=agent).json()["noeud_id"] == RADIOLOGIE


def test_badge_ou_lieu_inconnu(client, reg):
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    assert badge(client, reg, 999, URGENCES).status_code == 404
    assert badge(client, reg, agent_id, 999).status_code == 404
    # Le régulateur n'est pas un brancardier : il n'a pas de badge
    assert badge(client, reg, 1, URGENCES).status_code == 404


def test_le_telephone_sait_que_l_agent_est_arrive_au_depart(client, reg, medecin, agent):
    agent_id, entetes = agent
    mission_acceptee(client, medecin, entetes)
    assert client.get("/missions/moi", headers=entetes).json()["agent_au_depart"] is False

    badge(client, reg, agent_id, URGENCES)   # il entre aux Urgences : le récepteur capte son badge
    assert client.get("/missions/moi", headers=entetes).json()["agent_au_depart"] is True


def test_une_declaration_ne_prouve_pas_la_presence(client, reg, medecin, agent):
    _, entetes = agent
    mission_id = mission_acceptee(client, medecin, entetes)
    # L'agent dit lui-même être aux Urgences (« Je suis à ») : ce n'est pas une preuve
    client.post("/detections", json={"noeud_id": URGENCES}, headers=entetes)
    assert client.get("/missions/moi", headers=entetes).json()["agent_au_depart"] is False
    r = client.post(f"/missions/{mission_id}/scan-depart", json={"code_bracelet": BRACELET}, headers=entetes)
    assert r.status_code == 422 and "badge" in r.json()["detail"]


def test_avec_le_badge_le_bracelet_suffit(client, reg, medecin, agent):
    agent_id, entetes = agent
    mission_id = mission_acceptee(client, medecin, entetes)
    badge(client, reg, agent_id, URGENCES)

    r = client.post(f"/missions/{mission_id}/scan-depart", json={"code_bracelet": BRACELET}, headers=entetes)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "EN_TRANSIT"
    # Le bracelet est toujours vérifié : c'est lui qui garantit le bon patient
    lignes = client.get(f"/missions/{mission_id}/historique", headers=medecin).json()
    assert lignes[-1]["methode_verification"] == "SCAN_CODE_QR"


def test_badge_ailleurs_le_tag_reste_le_secours(client, reg, medecin, agent):
    _, entetes = agent   # badge capté en Radiologie, pas aux Urgences
    mission_id = mission_acceptee(client, medecin, entetes)
    r = client.post(f"/missions/{mission_id}/scan-depart", json={"code_bracelet": BRACELET}, headers=entetes)
    assert r.status_code == 422
    r = client.post(f"/missions/{mission_id}/scan-depart",
                    json={"tag_nfc": TAG_URGENCES, "code_bracelet": BRACELET}, headers=entetes)
    assert r.status_code == 200, r.text


def test_un_agent_ne_peut_pas_signaler_un_badge(client, reg):
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    agent = login(client, "cisse@test.fr", "brancard123")
    client.post("/auth/register", json=MEDECIN, headers=reg)
    medecin = login(client, "diallo@test.fr", "medecin123")
    assert badge(client, agent, agent_id, URGENCES).status_code == 403
    assert badge(client, medecin, agent_id, URGENCES).status_code == 403
    assert badge(client, {}, agent_id, URGENCES).status_code == 401
