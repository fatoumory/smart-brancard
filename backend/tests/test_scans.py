# Scans de traçabilité : prise en charge (NFC + QR bracelet), clôture (NFC), forçage en urgence (CDC §5.5)

import pytest

from database import SessionLocal
from models.enums import StatutAgent
from models.patient import Patient
from models.utilisateur import Brancardier
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, REANIMATION = 1, 2, 13
TAG_URGENCES, TAG_REANIMATION, TAG_RADIOLOGIE = "NFC-RDC-URG", "NFC-E1-REA", "NFC-RDC-RAD"
BRACELET_DUPONT, BRACELET_AUTRE = "QR-00000001", "QR-00000002"

MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


@pytest.fixture()
def reg(client):
    db = SessionLocal()
    charger_graphe_json(db)
    db.add(Patient(id=1, id_hospitalisation="00000001", prenom="Jean", nom="Dupont",
                   code_bracelet=BRACELET_DUPONT))
    db.add(Patient(id=2, id_hospitalisation="00000002", prenom="Awa", nom="Mbaye",
                   code_bracelet=BRACELET_AUTRE))
    db.commit()
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


@pytest.fixture()
def medecin(client, reg):
    client.post("/auth/register", json=MEDECIN, headers=reg)
    return login(client, "diallo@test.fr", "medecin123")


def agent(client, reg, identifiant, position=URGENCES):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": position}, headers=entetes)
    return agent_id, entetes


def mission_acceptee(client, medecin, entetes, urgence="URGENT"):
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": urgence}).json()
    assert client.put(f"/missions/{m['id']}/accept", headers=entetes).status_code == 200
    return m["id"]


def depart(client, mission_id, entetes, **corps):
    return client.post(f"/missions/{mission_id}/scan-depart", json=corps, headers=entetes)


def arrivee(client, mission_id, entetes, tag=TAG_REANIMATION):
    return client.post(f"/missions/{mission_id}/scan-arrivee", json={"tag_nfc": tag}, headers=entetes)


def lire_agent(agent_id):
    db = SessionLocal()
    try:
        a = db.get(Brancardier, agent_id)
        return a.statut, a.compteur_mission
    finally:
        db.close()


def test_cycle_complet(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a", position=RADIOLOGIE)
    mission_id = mission_acceptee(client, medecin, entetes)

    r = depart(client, mission_id, entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET_DUPONT)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "EN_TRANSIT"
    # Le scan prouve que l'agent est au point de départ
    assert client.get("/detections/me", headers=entetes).json()["noeud_id"] == URGENCES

    r = arrivee(client, mission_id, entetes)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "TERMINE"
    assert lire_agent(agent_id) == (StatutAgent.DISPONIBLE, 1)   # libéré, une mission de plus
    assert client.get("/detections/me", headers=entetes).json()["noeud_id"] == REANIMATION
    assert client.get("/missions/moi", headers=entetes).json() is None

    # Journal complet, avec la méthode de vérification de chaque étape (CDC §7.3)
    lignes = client.get(f"/missions/{mission_id}/historique", headers=medecin).json()
    assert [(l["statut_modifie_en"], l["methode_verification"]) for l in lignes] == [
        ("EN_ATTENTE", "MANUEL"), ("PROPOSE", "MANUEL"), ("ACCEPTE", "MANUEL"),
        ("EN_TRANSIT", "SCAN_CODE_QR"), ("TERMINE", "BADGE_NFC")]
    assert lignes[-1]["auteur_id"] == agent_id


def test_codes_insensibles_a_la_casse_et_aux_espaces(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission_acceptee(client, medecin, entetes)
    r = depart(client, mission_id, entetes, tag_nfc=" nfc-rdc-urg ", code_bracelet="qr-00000001")
    assert r.status_code == 200, r.text


def test_mauvaise_salle_au_depart(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission_acceptee(client, medecin, entetes)
    r = depart(client, mission_id, entetes, tag_nfc=TAG_RADIOLOGIE, code_bracelet=BRACELET_DUPONT)
    assert r.status_code == 422 and "point de départ" in r.json()["detail"]
    assert client.get("/missions/moi", headers=entetes).json()["statut"] == "ACCEPTE"


def test_mauvais_patient(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission_acceptee(client, medecin, entetes)
    # Identitovigilance : le bracelet d'un autre patient est refusé
    r = depart(client, mission_id, entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET_AUTRE)
    assert r.status_code == 422 and "bracelet" in r.json()["detail"]
    r = depart(client, mission_id, entetes, tag_nfc=TAG_URGENCES)   # bracelet non scanné
    assert r.status_code == 422


def test_forcage_en_urgence_vitale(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission_acceptee(client, medecin, entetes, urgence="URGENT")
    r = depart(client, mission_id, entetes, forcer_urgence=True)
    assert r.status_code == 200 and r.json()["statut"] == "EN_TRANSIT"
    lignes = client.get(f"/missions/{mission_id}/historique", headers=medecin).json()
    assert lignes[-1]["methode_verification"] == "FORCE_URGENCE"   # forçage tracé


def test_forcage_interdit_hors_urgence(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    mission_id = mission_acceptee(client, medecin, entetes, urgence="HAUTE")
    r = depart(client, mission_id, entetes, forcer_urgence=True)
    assert r.status_code == 422 and "URGENT" in r.json()["detail"]


def test_mauvaise_salle_a_l_arrivee(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a")
    mission_id = mission_acceptee(client, medecin, entetes)
    depart(client, mission_id, entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET_DUPONT)
    r = arrivee(client, mission_id, entetes, tag=TAG_RADIOLOGIE)
    assert r.status_code == 422 and "destination" in r.json()["detail"]
    assert lire_agent(agent_id)[0] == StatutAgent.EN_MISSION   # toujours en transport


def test_etapes_dans_l_ordre(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "URGENT"}).json()
    # Proposée mais pas encore acceptée : pas de prise en charge
    r = depart(client, m["id"], entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET_DUPONT)
    assert r.status_code == 409
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    # Acceptée mais pas encore prise en charge : pas de clôture
    assert arrivee(client, m["id"], entetes).status_code == 409


def test_seul_l_agent_de_la_mission_peut_scanner(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    _, autre = agent(client, reg, "b", position=REANIMATION)
    mission_id = mission_acceptee(client, medecin, entetes)
    r = depart(client, mission_id, autre, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET_DUPONT)
    assert r.status_code == 404
    assert depart(client, mission_id, medecin, forcer_urgence=True).status_code == 403


def test_agent_libere_recoit_la_mission_suivante(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "seul")
    premiere = mission_acceptee(client, medecin, entetes)
    seconde = client.post("/missions/create", headers=medecin, json={
        "patient_id": 2, "noeud_source_id": RADIOLOGIE, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "MOYENNE"}).json()
    assert seconde["statut"] == "EN_ATTENTE"   # le seul agent est occupé

    depart(client, premiere, entetes, tag_nfc=TAG_URGENCES, code_bracelet=BRACELET_DUPONT)
    arrivee(client, premiere, entetes)
    moi = client.get("/missions/moi", headers=entetes).json()
    assert moi["id"] == seconde["id"] and moi["statut"] == "PROPOSE"
