# Clôtures de secours : bouton « Arrivé » de l'agent, clôture par le régulateur

import pytest

from database import SessionLocal
from models.enums import StatutAgent
from models.patient import Patient
from models.utilisateur import Brancardier
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, REANIMATION = 1, 13
TAG_URGENCES, BRACELET = "NFC-RDC-URG", "QR-00000001"

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


def agent(client, reg, identifiant):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": URGENCES}, headers=entetes)
    return agent_id, entetes


def mission(client, medecin, entetes, prise_en_charge=True):
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    if prise_en_charge:
        r = client.post(f"/missions/{m['id']}/scan-depart",
                        json={"tag_nfc": TAG_URGENCES, "code_bracelet": BRACELET}, headers=entetes)
        assert r.json()["statut"] == "EN_TRANSIT"
    return m["id"]


def lire_agent(agent_id):
    db = SessionLocal()
    try:
        a = db.get(Brancardier, agent_id)
        return a.statut, a.compteur_mission
    finally:
        db.close()


def test_bouton_arrive_de_l_agent(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a")
    mission_id = mission(client, medecin, entetes)

    r = client.post(f"/missions/{mission_id}/arrivee", headers=entetes)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "TERMINE"
    assert lire_agent(agent_id) == (StatutAgent.DISPONIBLE, 1)
    # Rien n'a prouvé l'arrivée : la clôture est tracée comme manuelle, par l'agent
    derniere = client.get(f"/missions/{mission_id}/historique", headers=medecin).json()[-1]
    assert derniere["methode_verification"] == "MANUEL" and derniere["auteur_id"] == agent_id


def test_bouton_arrive_seulement_pendant_le_transport(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    _, autre = agent(client, reg, "b")
    mission_id = mission(client, medecin, entetes, prise_en_charge=False)
    assert client.post(f"/missions/{mission_id}/arrivee", headers=entetes).status_code == 409
    assert client.post(f"/missions/{mission_id}/arrivee", headers=autre).status_code == 404


def test_cloture_par_le_regulateur(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a")
    mission_id = mission(client, medecin, entetes)

    r = client.put(f"/missions/{mission_id}/cloturer", headers=reg)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "TERMINE"
    assert r.json()["brancardier_id"] == agent_id   # l'agent reste celui qui a transporté le patient
    assert lire_agent(agent_id) == (StatutAgent.DISPONIBLE, 1)
    derniere = client.get(f"/missions/{mission_id}/historique", headers=reg).json()[-1]
    assert derniere["methode_verification"] == "MANUEL"
    assert derniere["auteur_nom"] is not None and derniere["auteur_id"] != agent_id


def test_cloture_reservee_aux_missions_en_transit(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission(client, medecin, entetes, prise_en_charge=False)
    r = client.put(f"/missions/{mission_id}/cloturer", headers=reg)
    assert r.status_code == 409 and "réaffectez" in r.json()["detail"]
    assert client.put("/missions/999/cloturer", headers=reg).status_code == 404
    assert client.put(f"/missions/{mission_id}/cloturer", headers=medecin).status_code == 403
    assert client.put(f"/missions/{mission_id}/cloturer", headers=entetes).status_code == 403
