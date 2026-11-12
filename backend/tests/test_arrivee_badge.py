# Arrivée détectée par le badge (30 s dans la salle) et libération de l'agent à sa sortie

from datetime import datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.detection import Detection
from models.enums import StatutAgent
from models.patient import Patient
from models.utilisateur import Brancardier
from services.badge_service import liberer_agents_apres_mission
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, REANIMATION = 1, 2, 13
BRACELET, BRACELET_2 = "QR-00000001", "QR-00000002"

AGENT = {"nom_utilisateur": "cisse@test.fr", "prenom": "Amadou", "nom": "Cissé",
         "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


@pytest.fixture()
def reg(client):
    db = SessionLocal()
    charger_graphe_json(db)
    db.add(Patient(id=1, id_hospitalisation="00000001", prenom="Jean", nom="Dupont", code_bracelet=BRACELET))
    db.add(Patient(id=2, id_hospitalisation="00000002", prenom="Awa", nom="Mbaye", code_bracelet=BRACELET_2))
    db.commit()
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


@pytest.fixture()
def medecin(client, reg):
    client.post("/auth/register", json=MEDECIN, headers=reg)
    return login(client, "diallo@test.fr", "medecin123")


def badge(client, reg, agent_id, noeud_id):
    r = client.post("/detections/badge", json={"brancardier_id": agent_id, "noeud_id": noeud_id}, headers=reg)
    assert r.status_code == 201, r.text


def attendre(agent_id, secondes):
    """Simule le temps qui passe : toutes les détections de l'agent reculent dans le passé"""
    db = SessionLocal()
    for d in db.query(Detection).filter(Detection.brancardier_id == agent_id):
        d.date_heure = d.date_heure - timedelta(seconds=secondes)
    db.commit()
    db.close()


def arriver(client, reg, agent_id):
    """Badge capté dans la salle d'arrivée, puis de nouveau 40 s plus tard"""
    badge(client, reg, agent_id, REANIMATION)
    attendre(agent_id, 40)
    badge(client, reg, agent_id, REANIMATION)


def lire_agent(agent_id):
    db = SessionLocal()
    try:
        a = db.get(Brancardier, agent_id)
        return a.statut, a.compteur_mission
    finally:
        db.close()


@pytest.fixture()
def en_transit(client, reg, medecin):
    """Un agent qui transporte le patient des Urgences vers la Réanimation"""
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    entetes = login(client, "cisse@test.fr", "brancard123")
    badge(client, reg, agent_id, URGENCES)
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    r = client.post(f"/missions/{m['id']}/scan-depart", json={"code_bracelet": BRACELET}, headers=entetes)
    assert r.json()["statut"] == "EN_TRANSIT"
    return agent_id, entetes, m["id"]


def test_un_simple_passage_ne_termine_pas_la_mission(client, reg, medecin, en_transit):
    agent_id, _, mission_id = en_transit
    badge(client, reg, agent_id, REANIMATION)   # il vient d'entrer
    assert client.get(f"/missions/{mission_id}", headers=medecin).json()["statut"] == "EN_TRANSIT"


def test_trente_secondes_dans_la_salle_terminent_la_mission(client, reg, medecin, en_transit):
    agent_id, entetes, mission_id = en_transit
    arriver(client, reg, agent_id)   # toujours là 40 s plus tard

    assert client.get(f"/missions/{mission_id}", headers=medecin).json()["statut"] == "TERMINE"
    derniere = client.get(f"/missions/{mission_id}/historique", headers=medecin).json()[-1]
    assert derniere["methode_verification"] == "BALISE" and derniere["auteur_id"] is None
    assert derniere["brancardier_id"] == agent_id
    # Mission comptée, mais l'agent reste occupé : il remet le patient à l'équipe
    assert lire_agent(agent_id) == (StatutAgent.EN_MISSION, 1)
    assert client.get("/missions/moi", headers=entetes).json() is None


def test_une_sortie_entre_deux_remet_le_compteur_a_zero(client, reg, medecin, en_transit):
    agent_id, _, mission_id = en_transit
    badge(client, reg, agent_id, REANIMATION)
    attendre(agent_id, 40)
    badge(client, reg, agent_id, RADIOLOGIE)    # il est ressorti entre-temps
    attendre(agent_id, 20)
    badge(client, reg, agent_id, REANIMATION)   # présent depuis quelques secondes seulement
    assert client.get(f"/missions/{mission_id}", headers=medecin).json()["statut"] == "EN_TRANSIT"


def test_seul_le_badge_compte_dans_la_salle_d_arrivee(client, reg, medecin, en_transit):
    agent_id, entetes, mission_id = en_transit
    # Une déclaration (« Je suis à ») vieille de 40 s ne prouve pas 30 s de présence
    client.post("/detections", json={"noeud_id": REANIMATION}, headers=entetes)
    attendre(agent_id, 40)
    badge(client, reg, agent_id, REANIMATION)
    assert client.get(f"/missions/{mission_id}", headers=medecin).json()["statut"] == "EN_TRANSIT"


def test_en_sortant_de_la_salle_il_redevient_disponible(client, reg, medecin, en_transit):
    agent_id, entetes, _ = en_transit
    arriver(client, reg, agent_id)
    seconde = client.post("/missions/create", headers=medecin, json={
        "patient_id": 2, "noeud_source_id": RADIOLOGIE, "noeud_destination_id": URGENCES,
        "niveau_urgence": "MOYENNE"}).json()
    assert seconde["statut"] == "EN_ATTENTE"   # il remet encore le patient : pas de proposition

    badge(client, reg, agent_id, URGENCES)     # son badge est capté ailleurs : il est sorti
    moi = client.get("/missions/moi", headers=entetes).json()
    assert moi["id"] == seconde["id"] and moi["statut"] == "PROPOSE"


def test_reste_dans_la_salle_libere_apres_dix_minutes(client, reg, en_transit):
    agent_id, _, _ = en_transit
    arriver(client, reg, agent_id)
    badge(client, reg, agent_id, REANIMATION)   # toujours dans la salle : toujours occupé
    assert lire_agent(agent_id)[0] == StatutAgent.EN_MISSION

    db = SessionLocal()
    assert liberer_agents_apres_mission(db, datetime.now(timezone.utc) + timedelta(minutes=5)) == 0
    assert liberer_agents_apres_mission(db, datetime.now(timezone.utc) + timedelta(minutes=11)) == 1
    db.close()
    assert lire_agent(agent_id)[0] == StatutAgent.DISPONIBLE


def test_un_agent_en_mission_active_n_est_jamais_libere(client, reg, en_transit):
    agent_id, _, _ = en_transit
    db = SessionLocal()
    assert liberer_agents_apres_mission(db, datetime.now(timezone.utc) + timedelta(hours=1)) == 0
    db.close()
    assert lire_agent(agent_id)[0] == StatutAgent.EN_MISSION
