# Délai de réponse : sans réponse 30 s après la proposition, l'agent passe INDISPONIBLE
# et la mission est proposée à un autre agent (CDC §5.3, maquette)

from datetime import datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.enums import StatutAgent
from models.patient import Patient
from models.utilisateur import Brancardier
from services.assignation_service import gerer_propositions_expirees
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


def agent(client, reg, identifiant, position):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": position}, headers=entetes)
    return agent_id, entetes


def demande(client, medecin):
    return client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "URGENT"}).json()


def expirer(secondes_ecoulees):
    """Lance la vérification comme si `secondes_ecoulees` s'étaient écoulées depuis maintenant"""
    db = SessionLocal()
    try:
        return gerer_propositions_expirees(db, datetime.now(timezone.utc) + timedelta(seconds=secondes_ecoulees))
    finally:
        db.close()


def statut_agent(agent_id):
    db = SessionLocal()
    try:
        return db.get(Brancardier, agent_id).statut
    finally:
        db.close()


def test_le_telephone_recoit_l_heure_limite(client, reg, medecin):
    _, entetes = agent(client, reg, "a", URGENCES)
    demande(client, medecin)
    fin = datetime.fromisoformat(client.get("/missions/moi", headers=entetes).json()["fin_reponse"])
    restant = fin.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
    assert timedelta(seconds=25) < restant <= timedelta(seconds=30)


def test_pas_d_expiration_avant_30_secondes(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a", URGENCES)
    demande(client, medecin)
    assert expirer(20) == 0
    assert client.get("/missions/moi", headers=entetes).json()["statut"] == "PROPOSE"
    assert statut_agent(agent_id) == StatutAgent.EN_MISSION


def test_sans_reponse_la_mission_passe_au_suivant(client, reg, medecin):
    muet, entetes = agent(client, reg, "muet", URGENCES)
    suivant, _ = agent(client, reg, "suivant", RADIOLOGIE)
    m = demande(client, medecin)
    assert m["brancardier_id"] == muet

    assert expirer(31) == 1
    # L'agent qui n'a pas répondu n'est peut-être plus joignable : il passe INDISPONIBLE
    assert statut_agent(muet) == StatutAgent.INDISPONIBLE
    assert client.get("/missions/moi", headers=entetes).json() is None
    apres = client.get(f"/missions/{m['id']}", headers=medecin).json()
    assert apres["statut"] == "PROPOSE" and apres["brancardier_id"] == suivant

    # Journal : retour en attente décidé par le système, sans motif (ce n'est pas un refus)
    lignes = client.get(f"/missions/{m['id']}/historique", headers=medecin).json()
    assert [l["statut_modifie_en"] for l in lignes] == ["EN_ATTENTE", "PROPOSE", "EN_ATTENTE", "PROPOSE"]
    assert (lignes[2]["auteur_id"], lignes[2]["motif_refus"]) == (None, None)


def test_sans_reponse_et_personne_d_autre(client, reg, medecin):
    agent(client, reg, "seul", URGENCES)
    m = demande(client, medecin)
    expirer(31)
    apres = client.get(f"/missions/{m['id']}", headers=medecin).json()
    assert apres["statut"] == "EN_ATTENTE" and apres["brancardier_id"] is None
    assert apres["fin_reponse"] is None


def test_une_mission_acceptee_n_expire_pas(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    assert expirer(600) == 0
    assert client.get("/missions/moi", headers=entetes).json()["statut"] == "ACCEPTE"
    assert statut_agent(agent_id) == StatutAgent.EN_MISSION


def test_reponse_trop_tardive_refusee(client, reg, medecin):
    _, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    expirer(31)
    # L'agent répond après l'expiration : la mission ne lui est plus proposée
    assert client.put(f"/missions/{m['id']}/accept", headers=entetes).status_code == 404
