# File d'attente avec vieillissement et alerte « Saturation flotte » (CDC §5.4)

from datetime import datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.mission import Mission
from models.patient import Patient
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


def agent(client, reg, identifiant, position=URGENCES):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": position}, headers=entetes)
    return agent_id, entetes


def demande(client, medecin, urgence, cree_il_y_a_min=0):
    """Crée une mission ; cree_il_y_a_min la fait dater d'avant (elle a déjà attendu)"""
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": urgence}).json()
    if cree_il_y_a_min:
        db = SessionLocal()
        db.get(Mission, m["id"]).date_creation = datetime.now(timezone.utc) - timedelta(minutes=cree_il_y_a_min)
        db.commit()
        db.close()
    return m["id"]


def test_une_mission_qui_attend_depuis_longtemps_passe_devant(client, reg, medecin):
    # Aucun agent : tout reste en attente
    basse_ancienne = demande(client, medecin, "BASSE", cree_il_y_a_min=25)   # échéance dans 5 min
    moyenne = demande(client, medecin, "MOYENNE")                            # échéance dans 15 min
    haute = demande(client, medecin, "HAUTE")                                # échéance dans 8 min
    urgent = demande(client, medecin, "URGENT")
    file = client.get("/missions/saturation", headers=reg).json()["file"]
    # L'urgence vitale d'abord, puis l'échéance la plus proche : la BASSE a « vieilli »
    assert file == [urgent, basse_ancienne, haute, moyenne]

    # Un agent se libère : il reçoit la première de la file (l'URGENT)
    agent_id, _ = agent(client, reg, "a")
    assert client.get(f"/missions/{urgent}", headers=reg).json()["brancardier_id"] == agent_id
    # Le suivant reçoit la BASSE qui a attendu, pas la HAUTE qui vient d'arriver
    second, _ = agent(client, reg, "b")
    assert client.get(f"/missions/{basse_ancienne}", headers=reg).json()["brancardier_id"] == second


def test_saturation_flotte(client, reg, medecin):
    for _ in range(2):
        demande(client, medecin, "MOYENNE")
    etat = client.get("/missions/saturation", headers=reg).json()
    # 2 missions en attente : sous le seuil (3 par défaut)
    assert etat["sature"] is False and etat["missions_en_attente"] == 2 and etat["seuil"] == 3

    demande(client, medecin, "BASSE", cree_il_y_a_min=40)   # a dépassé ses 30 min garanties
    etat = client.get("/missions/saturation", headers=reg).json()
    assert etat["sature"] is True
    assert (etat["missions_en_attente"], etat["missions_en_retard"], etat["agents_disponibles"]) == (3, 1, 0)

    # Des agents arrivent : les missions leur sont proposées, la file se vide
    for nom in ("a", "b", "c"):
        agent(client, reg, nom)
    etat = client.get("/missions/saturation", headers=reg).json()
    assert etat["sature"] is False and etat["missions_en_attente"] == 0


def test_saturation_reservee_au_regulateur(client, reg, medecin):
    _, entetes = agent(client, reg, "a")
    assert client.get("/missions/saturation", headers=medecin).status_code == 403
    assert client.get("/missions/saturation", headers=entetes).status_code == 403
