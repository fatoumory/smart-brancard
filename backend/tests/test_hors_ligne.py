# Actions faites hors ligne : heure réelle vérifiée et gardée, actions renvoyées comptées une seule fois

from datetime import datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.detection import Detection
from models.mission import Mission
from models.patient import Patient
from models.utilisateur import Brancardier
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
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    entetes = login(client, "cisse@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": URGENCES}, headers=entetes)
    return agent_id, entetes


def il_y_a(minutes):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def mission_creee_il_y_a(client, medecin, minutes):
    """Une mission créée il y a quelques minutes (une action hors ligne ne peut pas la précéder)"""
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    db = SessionLocal()
    db.get(Mission, m["id"]).date_creation = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    db.commit()
    db.close()
    return m["id"]


def depart(client, mission_id, entetes, **corps):
    return client.post(f"/missions/{mission_id}/scan-depart", json=corps, headers=entetes)


def lignes(client, mission_id, entetes, statut):
    return [l for l in client.get(f"/missions/{mission_id}/historique", headers=entetes).json()
            if l["statut_modifie_en"] == statut]


def test_un_scan_hors_ligne_garde_son_heure_reelle(client, medecin, agent):
    _, entetes = agent
    mission_id = mission_creee_il_y_a(client, medecin, 10)
    client.put(f"/missions/{mission_id}/accept", headers=entetes)

    heure = il_y_a(3)   # scan fait dans l'ascenseur, envoyé 3 min plus tard
    r = depart(client, mission_id, entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET, horodatage_client=heure)
    assert r.status_code == 200, r.text
    ligne = lignes(client, mission_id, medecin, "EN_TRANSIT")[0]
    assert ligne["horodatage_client"] is not None and ligne["horodatage"] > ligne["horodatage_client"]
    # La prise en charge retenue est l'heure réelle du scan
    prise = datetime.fromisoformat(r.json()["date_prise_en_charge"]).replace(tzinfo=timezone.utc)
    assert abs(prise - datetime.fromisoformat(heure)) < timedelta(seconds=1)


@pytest.mark.parametrize("decalage_min, creee_il_y_a_min", [
    (-10, 10),   # dans le futur
    (15, 10),    # avant la création de la mission
    (45, 120),   # plus de 30 min avant l'envoi
])
def test_une_heure_incoherente_est_refusee(client, medecin, agent, decalage_min, creee_il_y_a_min):
    _, entetes = agent
    mission_id = mission_creee_il_y_a(client, medecin, creee_il_y_a_min)
    client.put(f"/missions/{mission_id}/accept", headers=entetes)
    r = depart(client, mission_id, entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET,
               horodatage_client=il_y_a(decalage_min))
    assert r.status_code == 422 and "heure" in r.json()["detail"]
    assert client.get("/missions/moi", headers=entetes).json()["statut"] == "ACCEPTE"


def test_une_acceptation_renvoyee_n_est_comptee_qu_une_fois(client, medecin, agent):
    _, entetes = agent
    mission_id = mission_creee_il_y_a(client, medecin, 1)
    assert client.put(f"/missions/{mission_id}/accept", headers=entetes).status_code == 200
    r = client.put(f"/missions/{mission_id}/accept", headers=entetes)   # la réponse s'était perdue
    assert r.status_code == 200 and r.json()["statut"] == "ACCEPTE"
    assert len(lignes(client, mission_id, medecin, "ACCEPTE")) == 1


def test_les_scans_renvoyes_ne_sont_comptes_qu_une_fois(client, medecin, agent):
    agent_id, entetes = agent
    mission_id = mission_creee_il_y_a(client, medecin, 1)
    client.put(f"/missions/{mission_id}/accept", headers=entetes)
    for _ in range(2):
        assert depart(client, mission_id, entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET).status_code == 200
    for _ in range(2):
        r = client.post(f"/missions/{mission_id}/arrivee", headers=entetes)
        assert r.status_code == 200 and r.json()["statut"] == "TERMINE"
    assert len(lignes(client, mission_id, medecin, "EN_TRANSIT")) == 1
    assert len(lignes(client, mission_id, medecin, "TERMINE")) == 1
    db = SessionLocal()
    assert db.get(Brancardier, agent_id).compteur_mission == 1   # une seule mission comptée
    db.close()


def test_un_refus_renvoye_n_est_pas_compte_deux_fois(client, medecin, agent):
    _, entetes = agent
    mission_id = mission_creee_il_y_a(client, medecin, 1)
    corps = {"motif": "MATERIEL_DEFECTUEUX"}
    assert client.put(f"/missions/{mission_id}/refuse", json=corps, headers=entetes).status_code == 200
    # La mission n'est plus la sienne : le refus renvoyé est ignoré proprement
    assert client.put(f"/missions/{mission_id}/refuse", json=corps, headers=entetes).status_code == 404
    refus = [l for l in client.get(f"/missions/{mission_id}/historique", headers=medecin).json()
             if l["motif_refus"] is not None]
    assert len(refus) == 1


def test_la_presence_est_verifiee_a_l_heure_du_scan(client, reg, medecin, agent):
    agent_id, entetes = agent
    mission_id = mission_creee_il_y_a(client, medecin, 10)
    client.put(f"/missions/{mission_id}/accept", headers=entetes)
    # Badge capté aux Urgences il y a 3 min, puis en Radiologie maintenant (il est reparti avec le patient)
    client.post("/detections/badge", json={"brancardier_id": agent_id, "noeud_id": URGENCES}, headers=reg)
    db = SessionLocal()
    for d in db.query(Detection).filter(Detection.brancardier_id == agent_id):
        d.date_heure = d.date_heure - timedelta(minutes=3)
    db.commit()
    db.close()
    client.post("/detections/badge", json={"brancardier_id": agent_id, "noeud_id": RADIOLOGIE}, headers=reg)

    # Sans heure : on regarde maintenant, il n'est plus aux Urgences
    assert depart(client, mission_id, entetes, code_bracelet=BRACELET).status_code == 422
    # Avec l'heure réelle du scan (il y a 3 min) : il y était bien
    r = depart(client, mission_id, entetes, code_bracelet=BRACELET,
               horodatage_client=(datetime.now(timezone.utc) - timedelta(minutes=3) + timedelta(seconds=5)).isoformat())
    assert r.status_code == 200, r.text
