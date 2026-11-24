# Poste d'attente et agent réservé aux URGENT (rapport Sprint 5, § 4.3)

import pytest

from database import SessionLocal
from models.patient import Patient
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, HALL_RDC, REANIMATION, PALIER_ETAGE = 1, 6, 13, 16

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


def agent(client, reg, identifiant, position, poste=None, reserve=False):
    """Crée un brancardier, règle son poste (avant qu'il soit disponible), puis le localise"""
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    if poste is not None or reserve:
        r = client.patch(f"/utilisateurs/{agent_id}/affectation", headers=reg,
                         json={"poste_id": poste, "reserve_urgent": reserve})
        assert r.status_code == 200, r.text
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": position}, headers=entetes)
    return agent_id, entetes


def demande(client, medecin, urgence):
    return client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": urgence}).json()


def test_un_agent_reserve_ne_recoit_pas_les_autres_missions(client, reg, medecin):
    # L'agent réservé est aux Urgences, juste à côté du patient ; le polyvalent est à l'étage
    reserve, _ = agent(client, reg, "r", URGENCES, poste=HALL_RDC, reserve=True)
    polyvalent, _ = agent(client, reg, "p", REANIMATION)
    # Une HAUTE va au polyvalent, plus loin : le réservé reste libre pour une URGENT
    assert demande(client, medecin, "HAUTE")["brancardier_id"] == polyvalent
    # L'URGENT va au plus proche, ici l'agent réservé
    assert demande(client, medecin, "URGENT")["brancardier_id"] == reserve


def test_une_urgent_va_au_plus_proche_reserve_ou_non(client, reg, medecin):
    agent(client, reg, "r", PALIER_ETAGE, poste=PALIER_ETAGE, reserve=True)
    polyvalent, _ = agent(client, reg, "p", URGENCES)
    assert demande(client, medecin, "URGENT")["brancardier_id"] == polyvalent


def test_seuls_des_agents_reserves_libres_la_mission_attend(client, reg, medecin):
    reserve, _ = agent(client, reg, "r", URGENCES, reserve=True)
    missions = [demande(client, medecin, "MOYENNE") for _ in range(3)]
    assert all(m["brancardier_id"] is None for m in missions)

    # Saturation : l'agent réservé libre ne compte pas pour ces missions
    etat = client.get("/missions/saturation", headers=reg).json()
    assert etat["sature"] is True
    assert (etat["agents_disponibles"], etat["agents_reserves_urgent"]) == (1, 1)

    # Le régulateur lève la réservation : l'agent reçoit aussitôt la première mission de la file
    r = client.patch(f"/utilisateurs/{reserve}/affectation", headers=reg,
                     json={"poste_id": None, "reserve_urgent": False})
    assert r.status_code == 200 and r.json()["reserve_urgent"] is False
    assert client.get(f"/missions/{missions[0]['id']}", headers=reg).json()["brancardier_id"] == reserve


def test_le_poste_est_visible_du_regulateur_et_de_l_agent(client, reg):
    agent_id, entetes = agent(client, reg, "r", URGENCES, poste=HALL_RDC, reserve=True)
    moi = client.get("/auth/me", headers=entetes).json()
    assert (moi["poste_id"], moi["poste_nom"], moi["reserve_urgent"]) == (HALL_RDC, "Hall central - RDC", True)
    fiche = next(u for u in client.get("/utilisateurs?role=BRANCARDIER", headers=reg).json() if u["id"] == agent_id)
    assert fiche["poste_nom"] == "Hall central - RDC" and fiche["reserve_urgent"] is True


def test_affectation_refusee(client, reg, medecin):
    agent_id, _ = agent(client, reg, "r", URGENCES)
    # Lieu inconnu
    r = client.patch(f"/utilisateurs/{agent_id}/affectation", headers=reg, json={"poste_id": 999})
    assert r.status_code == 404
    # Un médecin n'a pas de poste d'attente
    medecin_id = next(u["id"] for u in client.get("/utilisateurs?role=MEDECIN", headers=reg).json())
    r = client.patch(f"/utilisateurs/{medecin_id}/affectation", headers=reg, json={"reserve_urgent": True})
    assert r.status_code == 422
    # Compte inconnu
    assert client.patch("/utilisateurs/9999/affectation", headers=reg, json={}).status_code == 404
