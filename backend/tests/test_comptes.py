# Désactivation et réactivation des comptes par le régulateur (jamais de suppression)

import pytest

from database import SessionLocal
from models.patient import Patient
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


def activer(client, reg, utilisateur_id, est_actif):
    return client.patch(f"/utilisateurs/{utilisateur_id}", json={"est_actif": est_actif}, headers=reg)


def test_un_compte_desactive_ne_peut_plus_se_connecter(client, reg):
    agent_id, entetes = agent(client, reg, "a")
    r = activer(client, reg, agent_id, False)
    assert r.status_code == 200, r.text
    assert r.json()["est_actif"] is False and r.json()["statut"] == "INDISPONIBLE"
    # Ni avec son mot de passe, ni avec un jeton obtenu avant
    r = client.post("/auth/login", data={"username": "a@test.fr", "password": "brancard123"})
    assert r.status_code == 403
    assert client.get("/auth/me", headers=entetes).status_code == 401
    # Le compte existe toujours (rien n'est supprimé)
    assert any(u["id"] == agent_id for u in client.get("/utilisateurs", headers=reg).json())


def test_sa_mission_acceptee_repart_vers_un_autre_agent(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a")
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    autre_id, _ = agent(client, reg, "b")   # arrive après : la mission est déjà prise

    assert activer(client, reg, agent_id, False).status_code == 200
    mission = client.get(f"/missions/{m['id']}", headers=medecin).json()
    assert mission["statut"] == "PROPOSE" and mission["brancardier_id"] == autre_id
    # Le retour en attente est tracé avec le régulateur et l'agent désactivé
    retour = [l for l in client.get(f"/missions/{m['id']}/historique", headers=reg).json()
              if l["statut_modifie_en"] == "EN_ATTENTE"][-1]
    assert retour["brancardier_id"] == agent_id and retour["auteur_id"] is not None


def test_impossible_pendant_un_transport(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a")
    m = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"}).json()
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    client.post(f"/missions/{m['id']}/scan-depart",
                json={"tag_nfc": TAG_URGENCES, "code_bracelet": BRACELET}, headers=entetes)

    r = activer(client, reg, agent_id, False)
    assert r.status_code == 409 and "clôturez" in r.json()["detail"]
    assert client.get("/auth/me", headers=entetes).json()["est_actif"] is True


def test_reactivation(client, reg):
    agent_id, _ = agent(client, reg, "a")
    activer(client, reg, agent_id, False)
    r = activer(client, reg, agent_id, True)
    assert r.json()["est_actif"] is True and r.json()["statut"] == "INDISPONIBLE"
    # Il se reconnecte, puis se signale lui-même disponible
    entetes = login(client, "a@test.fr", "brancard123")
    r = client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"}, headers=entetes)
    assert r.json()["statut"] == "DISPONIBLE"


def test_regles_de_la_desactivation(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a")
    moi = client.get("/auth/me", headers=reg).json()["id"]
    assert activer(client, reg, moi, False).status_code == 409   # pas son propre compte
    assert activer(client, reg, 999, False).status_code == 404
    assert activer(client, medecin, agent_id, False).status_code == 403
    assert activer(client, entetes, agent_id, False).status_code == 403
    # Un médecin peut aussi être désactivé
    medecin_id = client.get("/auth/me", headers=medecin).json()["id"]
    assert activer(client, reg, medecin_id, False).json()["est_actif"] is False
