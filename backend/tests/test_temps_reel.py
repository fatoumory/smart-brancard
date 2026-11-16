# Temps réel : WebSocket /ws et sujets publiés après chaque commit (CDC §4.7)

import pytest
from starlette.websockets import WebSocketDisconnect

from database import SessionLocal
from models.patient import Patient
from services.graphe_service import charger_graphe_json
from services.temps_reel import diffuseur
from tests.conftest import login

URGENCES, REANIMATION = 1, 13

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


@pytest.fixture()
def publies(monkeypatch):
    """Sujets publiés pendant le test, dans l'ordre"""
    liste = []
    monkeypatch.setattr(diffuseur, "publier", lambda sujets: liste.append(sujets))
    return liste


def jeton(entetes):
    return entetes["Authorization"].removeprefix("Bearer ")


def attendre_le_sujet(ws, sujet, essais=10):
    """Lit les messages jusqu'à celui qui annonce ce sujet"""
    for _ in range(essais):
        message = ws.receive_json()
        if message["type"] == "maj" and sujet in message["sujets"]:
            return message
    raise AssertionError(f"Sujet {sujet} jamais reçu")


def test_un_ecran_connecte_est_prevenu_d_une_nouvelle_mission(client, reg, medecin):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"jeton": jeton(reg)})
        assert ws.receive_json() == {"type": "connecte"}
        client.post("/missions/create", headers=medecin, json={
            "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
            "niveau_urgence": "URGENT"})
        # Seul le sujet est envoyé : aucune donnée de la mission ni du patient
        assert attendre_le_sujet(ws, "missions") == {"type": "maj", "sujets": ["missions"]}
    assert diffuseur.nombre_de_connexions() == 0


@pytest.mark.parametrize("premier_message", ['{"jeton": "faux"}', '{}', 'pas du json'])
def test_connexion_refusee_sans_jeton_valide(client, reg, premier_message):
    with client.websocket_connect("/ws") as ws:
        ws.send_text(premier_message)
        with pytest.raises(WebSocketDisconnect) as erreur:
            ws.receive_json()
    assert erreur.value.code == 4401


def test_compte_desactive_refuse(client, reg, medecin):
    medecin_id = client.get("/auth/me", headers=medecin).json()["id"]
    client.patch(f"/utilisateurs/{medecin_id}", json={"est_actif": False}, headers=reg)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"jeton": jeton(medecin)})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_sujets_selon_les_tables_modifiees(client, reg, medecin, publies):
    donnees = {"nom_utilisateur": "a@test.fr", "prenom": "A", "nom": "Agent",
               "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    client.post("/auth/register", json=donnees, headers=reg)
    agent = login(client, "a@test.fr", "brancard123")
    publies.clear()

    # Une position : le sujet « agents » (dashboard du régulateur)
    client.post("/detections", json={"noeud_id": URGENCES}, headers=agent)
    assert publies == [["agents"]]

    # Une mission proposée à l'agent : missions et agents (son statut passe EN_MISSION)
    publies.clear()
    client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": "HAUTE"})
    assert ["missions"] in publies and ["agents", "missions"] in publies


def test_une_action_annulee_ne_previent_personne(client, publies):
    db = SessionLocal()
    db.add(Patient(id_hospitalisation="00000009", prenom="X", nom="Y", code_bracelet="QR-00000009"))
    db.flush()
    db.rollback()
    db.close()
    # Une simple lecture non plus
    client.get("/")
    assert publies == []
