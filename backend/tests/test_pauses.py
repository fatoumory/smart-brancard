# Pauses des brancardiers : durée, fin gérée par le serveur (gerer_reprise_service_auto)

from datetime import datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.enums import StatutAgent
from models.patient import Patient
from models.utilisateur import Brancardier
from services.assignation_service import gerer_reprise_service_auto
from services.graphe_service import charger_graphe_json
from services.taches_fond import executer_taches_periodiques
from tests.conftest import login

URGENCES, REANIMATION = 1, 13

MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}
AGENT = {"nom_utilisateur": "cisse@test.fr", "prenom": "Amadou", "nom": "Cissé",
         "mot_de_passe": "brancard123", "role": "BRANCARDIER"}


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
def agent(client, reg):
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    entetes = login(client, "cisse@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": URGENCES}, headers=entetes)
    return agent_id, entetes


def pause(client, entetes, **duree):
    return client.patch("/utilisateurs/me/statut", json={"statut": "EN_PAUSE", **duree}, headers=entetes)


def lire_agent(agent_id):
    db = SessionLocal()
    try:
        a = db.get(Brancardier, agent_id)
        return a.statut, a.fin_pause
    finally:
        db.close()


def finir_la_pause(agent_id):
    """Simule l'écoulement du temps : la fin de pause est déjà passée"""
    db = SessionLocal()
    db.get(Brancardier, agent_id).fin_pause = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    db.close()


def test_pause_avec_duree(client, agent):
    _, entetes = agent
    r = pause(client, entetes, duree_pause_minutes=10)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "EN_PAUSE"
    fin = datetime.fromisoformat(r.json()["fin_pause"]).replace(tzinfo=timezone.utc)
    restant = fin - datetime.now(timezone.utc)
    assert timedelta(minutes=9) < restant <= timedelta(minutes=10)


def test_pause_par_defaut_15_minutes(client, agent):
    _, entetes = agent
    fin = datetime.fromisoformat(pause(client, entetes).json()["fin_pause"]).replace(tzinfo=timezone.utc)
    assert timedelta(minutes=14) < fin - datetime.now(timezone.utc) <= timedelta(minutes=15)


@pytest.mark.parametrize("minutes", [0, 61])
def test_duree_de_pause_limitee(client, agent, minutes):
    _, entetes = agent
    assert pause(client, entetes, duree_pause_minutes=minutes).status_code == 422


def test_pas_de_reprise_avant_la_fin(client, agent):
    agent_id, entetes = agent
    pause(client, entetes, duree_pause_minutes=10)
    db = SessionLocal()
    assert gerer_reprise_service_auto(db) == 0
    db.close()
    assert lire_agent(agent_id)[0] == StatutAgent.EN_PAUSE


def test_reprise_automatique_meme_telephone_eteint(client, reg, agent):
    agent_id, entetes = agent
    pause(client, entetes, duree_pause_minutes=5)
    # Une demande arrive pendant la pause : personne n'est libre, elle attend
    client.post("/auth/register", json=MEDECIN, headers=reg)
    medecin = login(client, "diallo@test.fr", "medecin123")
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    assert m["statut"] == "EN_ATTENTE"

    # La pause se termine sans aucune requête du téléphone : c'est la tâche de fond qui agit
    finir_la_pause(agent_id)
    executer_taches_periodiques()
    assert lire_agent(agent_id) == (StatutAgent.EN_MISSION, None)  # disponible, puis aussitôt sollicité
    assert client.get(f"/missions/{m['id']}", headers=medecin).json()["brancardier_id"] == agent_id


def test_retour_anticipe(client, agent):
    agent_id, entetes = agent
    pause(client, entetes, duree_pause_minutes=30)
    r = client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"}, headers=entetes)
    assert r.json()["statut"] == "DISPONIBLE" and r.json()["fin_pause"] is None


def test_indisponible_sans_fin_automatique(client, agent):
    agent_id, entetes = agent
    client.patch("/utilisateurs/me/statut", json={"statut": "INDISPONIBLE"}, headers=entetes)
    db = SessionLocal()
    assert gerer_reprise_service_auto(db) == 0
    db.close()
    assert lire_agent(agent_id) == (StatutAgent.INDISPONIBLE, None)


def test_refus_pour_urgence_prioritaire_met_en_pause(client, reg, agent):
    agent_id, entetes = agent
    client.post("/auth/register", json=MEDECIN, headers=reg)
    medecin = login(client, "diallo@test.fr", "medecin123")
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    client.put(f"/missions/{m['id']}/refuse", json={"motif": "URGENCE_PRIORITAIRE"}, headers=entetes)

    statut, fin = lire_agent(agent_id)
    assert statut == StatutAgent.EN_PAUSE and fin is not None
    # Quand il a fini, il repasse disponible lui-même (ou le serveur le fait à la fin de la pause)
    r = client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"}, headers=entetes)
    assert r.status_code == 200 and r.json()["fin_pause"] is None
