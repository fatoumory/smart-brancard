# Badges BLE simulés : le récepteur d'une salle (ici le simulateur) signale le badge d'un agent

import pytest

from database import SessionLocal
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE = 1, 2

AGENT = {"nom_utilisateur": "cisse@test.fr", "prenom": "Amadou", "nom": "Cissé",
         "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


@pytest.fixture()
def reg(client):
    db = SessionLocal()
    charger_graphe_json(db)
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


def badge(client, entetes, brancardier_id, noeud_id):
    return client.post("/detections/badge", json={"brancardier_id": brancardier_id, "noeud_id": noeud_id},
                       headers=entetes)


def test_le_badge_donne_la_position_de_l_agent(client, reg):
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    r = badge(client, reg, agent_id, URGENCES)
    assert r.status_code == 201, r.text
    assert r.json()["brancardier_id"] == agent_id and r.json()["noeud_nom"] == "Urgences"

    # L'agent n'a rien fait : sa position est connue grâce au badge
    badge(client, reg, agent_id, RADIOLOGIE)
    agent = login(client, "cisse@test.fr", "brancard123")
    assert client.get("/detections/me", headers=agent).json()["noeud_id"] == RADIOLOGIE


def test_badge_ou_lieu_inconnu(client, reg):
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    assert badge(client, reg, 999, URGENCES).status_code == 404
    assert badge(client, reg, agent_id, 999).status_code == 404
    # Le régulateur n'est pas un brancardier : il n'a pas de badge
    assert badge(client, reg, 1, URGENCES).status_code == 404


def test_un_agent_ne_peut_pas_signaler_un_badge(client, reg):
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    agent = login(client, "cisse@test.fr", "brancard123")
    client.post("/auth/register", json=MEDECIN, headers=reg)
    medecin = login(client, "diallo@test.fr", "medecin123")
    assert badge(client, agent, agent_id, URGENCES).status_code == 403
    assert badge(client, medecin, agent_id, URGENCES).status_code == 403
    assert badge(client, {}, agent_id, URGENCES).status_code == 401
