# Réponse du brancardier : acceptation, refus avec motif et réaffectation (CDC §5.3)

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


def agent(client, reg, identifiant, position):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": position}, headers=entetes)
    return agent_id, entetes


def demande(client, medecin):
    r = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "URGENT"})
    assert r.status_code == 201, r.text
    return r.json()


def statut_agent(agent_id):
    db = SessionLocal()
    try:
        return db.get(Brancardier, agent_id).statut
    finally:
        db.close()


def test_l_agent_voit_sa_mission(client, reg, medecin):
    _, entetes = agent(client, reg, "a", URGENCES)
    assert client.get("/missions/moi", headers=entetes).json() is None
    m = demande(client, medecin)
    moi = client.get("/missions/moi", headers=entetes).json()
    assert moi["id"] == m["id"] and moi["statut"] == "PROPOSE"
    assert moi["patient_nom"] == "Dupont" and moi["itineraire_noms"][-1] == "Réanimation"


def test_acceptation(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)

    r = client.put(f"/missions/{m['id']}/accept", headers=entetes)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "ACCEPTE"
    assert statut_agent(agent_id) == StatutAgent.EN_MISSION

    # Décision explicite de l'agent, tracée avec son nom (CDC §7.3)
    lignes = client.get(f"/missions/{m['id']}/historique", headers=medecin).json()
    assert [l["statut_modifie_en"] for l in lignes] == ["EN_ATTENTE", "PROPOSE", "ACCEPTE"]
    assert lignes[-1]["auteur_id"] == agent_id

    # Une seconde réponse n'a plus de sens
    assert client.put(f"/missions/{m['id']}/accept", headers=entetes).status_code == 409
    assert client.put(f"/missions/{m['id']}/refuse", json={"motif": "FIN_SERVICE"},
                      headers=entetes).status_code == 409


def test_seul_l_agent_sollicite_peut_repondre(client, reg, medecin):
    agent(client, reg, "proche", URGENCES)
    _, autre = agent(client, reg, "loin", REANIMATION)
    m = demande(client, medecin)  # proposée au plus proche
    assert client.put(f"/missions/{m['id']}/accept", headers=autre).status_code == 404
    assert client.put("/missions/999/accept", headers=autre).status_code == 404
    assert client.put(f"/missions/{m['id']}/accept", headers=medecin).status_code == 403


def test_refus_reaffecte_au_suivant(client, reg, medecin):
    proche, entetes = agent(client, reg, "proche", URGENCES)
    suivant, _ = agent(client, reg, "suivant", RADIOLOGIE)
    m = demande(client, medecin)
    assert m["brancardier_id"] == proche

    r = client.put(f"/missions/{m['id']}/refuse", json={"motif": "MATERIEL_DEFECTUEUX"}, headers=entetes)
    assert r.status_code == 200, r.text
    assert r.json()["statut"] == "PROPOSE" and r.json()["brancardier_id"] == suivant
    # Matériel défectueux : l'agent ne peut plus transporter
    assert statut_agent(proche) == StatutAgent.INDISPONIBLE

    lignes = client.get(f"/missions/{m['id']}/historique", headers=medecin).json()
    assert [l["statut_modifie_en"] for l in lignes] == ["EN_ATTENTE", "PROPOSE", "EN_ATTENTE", "PROPOSE"]
    assert (lignes[2]["auteur_id"], lignes[2]["motif_refus"]) == (proche, "MATERIEL_DEFECTUEUX")
    assert lignes[3]["auteur_id"] is None   # nouvelle proposition de l'algorithme


def test_refus_sans_autre_agent(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "seul", URGENCES)
    m = demande(client, medecin)
    r = client.put(f"/missions/{m['id']}/refuse", json={"motif": "URGENCE_PRIORITAIRE"}, headers=entetes)
    # Personne d'autre : la mission attend dans la file, sans agent
    assert r.json()["statut"] == "EN_ATTENTE" and r.json()["brancardier_id"] is None
    # Urgence prioritaire : l'agent est retenu ailleurs, il passe en pause
    assert statut_agent(agent_id) == StatutAgent.EN_PAUSE
    assert client.get("/missions/moi", headers=entetes).json() is None


@pytest.mark.parametrize("motif, statut_attendu", [
    ("MATERIEL_DEFECTUEUX", StatutAgent.INDISPONIBLE),
    ("INDISPONIBILITE_PHYSIQUE", StatutAgent.INDISPONIBLE),
    ("FIN_SERVICE", StatutAgent.INDISPONIBLE),
    ("URGENCE_PRIORITAIRE", StatutAgent.EN_PAUSE),
])
def test_statut_de_l_agent_selon_le_motif(client, reg, medecin, motif, statut_attendu):
    agent_id, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    client.put(f"/missions/{m['id']}/refuse", json={"motif": motif}, headers=entetes)
    assert statut_agent(agent_id) == statut_attendu


def test_motif_obligatoire(client, reg, medecin):
    _, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    assert client.put(f"/missions/{m['id']}/refuse", json={}, headers=entetes).status_code == 422
    assert client.put(f"/missions/{m['id']}/refuse", json={"motif": "FLEMME"},
                      headers=entetes).status_code == 422
    # La mission est toujours proposée à l'agent
    assert client.get("/missions/moi", headers=entetes).json()["statut"] == "PROPOSE"
