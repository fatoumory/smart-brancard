# Actions d'exception du régulateur : réaffectation manuelle et annulation (maquette)

import pytest

from database import SessionLocal
from models.enums import StatutAgent
from models.patient import Patient
from models.utilisateur import Brancardier
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, REANIMATION = 1, 2, 13

MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


@pytest.fixture()
def reg(client):
    db = SessionLocal()
    charger_graphe_json(db)
    db.add(Patient(id=1, id_hospitalisation="00000001", prenom="Jean", nom="Dupont",
                   code_bracelet="QR-00000001"))
    db.commit()
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


@pytest.fixture()
def medecin(client, reg):
    client.post("/auth/register", json=MEDECIN, headers=reg)
    return login(client, "diallo@test.fr", "medecin123")


def agent(client, reg, identifiant, position, statut=None):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": position}, headers=entetes)
    if statut:
        client.patch("/utilisateurs/me/statut", json={"statut": statut}, headers=entetes)
    return agent_id, entetes


def demande(client, medecin):
    return client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()


def reaffecter(client, reg, mission_id, agent_id):
    return client.put(f"/missions/{mission_id}/reaffecter", json={"brancardier_id": agent_id}, headers=reg)


def statut_agent(agent_id):
    db = SessionLocal()
    try:
        return db.get(Brancardier, agent_id).statut
    finally:
        db.close()


def test_reaffectation_d_une_mission_proposee(client, reg, medecin):
    premier, _ = agent(client, reg, "premier", URGENCES)
    choisi, entetes_choisi = agent(client, reg, "choisi", REANIMATION)
    m = demande(client, medecin)
    assert m["brancardier_id"] == premier

    r = reaffecter(client, reg, m["id"], choisi)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "PROPOSE" and r.json()["brancardier_id"] == choisi
    assert statut_agent(premier) == StatutAgent.DISPONIBLE     # libéré
    assert statut_agent(choisi) == StatutAgent.EN_MISSION
    # L'agent choisi doit encore accepter
    assert client.put(f"/missions/{m['id']}/accept", headers=entetes_choisi).status_code == 200

    # Journal : proposition manuelle, au nom du régulateur (pas un badge « Auto »)
    reg_id = client.get("/auth/me", headers=reg).json()["id"]
    lignes = client.get(f"/missions/{m['id']}/historique", headers=reg).json()
    assert (lignes[2]["statut_modifie_en"], lignes[2]["auteur_id"]) == ("PROPOSE", reg_id)


def test_reaffectation_apres_acceptation(client, reg, medecin):
    # Cas prévu : l'agent a accepté puis rencontre un problème en chemin ; le régulateur réaffecte
    premier, entetes = agent(client, reg, "premier", URGENCES)
    choisi, _ = agent(client, reg, "choisi", REANIMATION)
    m = demande(client, medecin)
    client.put(f"/missions/{m['id']}/accept", headers=entetes)

    r = reaffecter(client, reg, m["id"], choisi)
    assert r.status_code == 200 and r.json()["brancardier_id"] == choisi
    assert client.get("/missions/moi", headers=entetes).json() is None


def test_reaffectation_d_une_mission_en_attente(client, reg, medecin):
    choisi, _ = agent(client, reg, "choisi", URGENCES, statut="EN_PAUSE")
    m = demande(client, medecin)
    assert m["statut"] == "EN_ATTENTE"
    # En pause : le régulateur ne peut pas le choisir
    assert reaffecter(client, reg, m["id"], choisi).status_code == 409
    client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"},
                 headers=login(client, "choisi@test.fr", "brancard123"))
    # Il est redevenu disponible : la file d'attente lui a déjà proposé la mission
    assert client.get(f"/missions/{m['id']}", headers=reg).json()["brancardier_id"] == choisi


def test_reaffectation_refusee(client, reg, medecin):
    occupe, _ = agent(client, reg, "occupe", URGENCES)
    m = demande(client, medecin)
    autre = demande(client, medecin)   # en attente : le seul agent est occupé
    assert reaffecter(client, reg, autre["id"], occupe).status_code == 409   # agent déjà en mission
    assert reaffecter(client, reg, m["id"], occupe).status_code == 409       # déjà le sien
    assert reaffecter(client, reg, m["id"], 999).status_code == 409          # agent inconnu
    assert reaffecter(client, reg, 999, occupe).status_code == 404           # mission inconnue


def test_annulation(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    r = client.put(f"/missions/{m['id']}/annuler", headers=reg)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "ANNULE" and r.json()["brancardier_id"] is None
    assert statut_agent(agent_id) == StatutAgent.DISPONIBLE
    assert client.get("/missions/moi", headers=entetes).json() is None
    # Le médecin voit l'annulation dans son suivi
    assert client.get(f"/missions/{m['id']}", headers=medecin).json()["statut"] == "ANNULE"
    # Une mission annulée ne se modifie plus
    assert client.put(f"/missions/{m['id']}/annuler", headers=reg).status_code == 409


def test_agent_libere_par_l_annulation_recoit_la_suivante(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "seul", URGENCES)
    m = demande(client, medecin)
    suivante = demande(client, medecin)
    client.put(f"/missions/{m['id']}/annuler", headers=reg)
    assert client.get("/missions/moi", headers=entetes).json()["id"] == suivante["id"]


def test_pas_d_action_pendant_le_transport(client, reg, medecin):
    _, entetes = agent(client, reg, "a", URGENCES)
    choisi, _ = agent(client, reg, "choisi", REANIMATION)
    m = demande(client, medecin)
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    client.post(f"/missions/{m['id']}/scan-depart", headers=entetes,
                json={"tag_nfc": "NFC-RDC-URG", "code_bracelet": "QR-00000001"})
    # Le patient est dans les couloirs : ni réaffectation ni annulation
    assert reaffecter(client, reg, m["id"], choisi).status_code == 409
    assert client.put(f"/missions/{m['id']}/annuler", headers=reg).status_code == 409


def test_actions_reservees_au_regulateur(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    assert client.put(f"/missions/{m['id']}/annuler", headers=medecin).status_code == 403
    assert client.put(f"/missions/{m['id']}/annuler", headers=entetes).status_code == 403
    assert reaffecter(client, medecin, m["id"], agent_id).status_code == 403
