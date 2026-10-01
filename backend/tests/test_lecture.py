# tests/test_lecture.py
# Routes de lecture pour les interfaces : GET /noeuds, GET /missions, GET /missions/{id}

import pytest

from database import SessionLocal
from models.patient import Patient
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, BLOC, REANIMATION = 1, 2, 11, 13

MEDECIN_A = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
            "mot_de_passe": "medecin123", "role": "MEDECIN"}
MEDECIN_B = {"nom_utilisateur": "sow@test.fr", "prenom": "Ibrahima", "nom": "Sow",
            "mot_de_passe": "medecin123", "role": "MEDECIN"}
BRANCARDIER = {"nom_utilisateur": "moussa@test.fr", "prenom": "Moussa", "nom": "Ba",
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


def compte(client, reg, donnees):
    client.post("/auth/register", json=donnees, headers=reg)
    return login(client, donnees["nom_utilisateur"], donnees["mot_de_passe"])


def creer(client, headers, urgence, source=URGENCES, destination=REANIMATION):
    r = client.post("/missions/create", headers=headers, json={
        "patient_id": 1, "noeud_source_id": source, "noeud_destination_id": destination,
        "niveau_urgence": urgence})
    assert r.status_code == 201, r.text
    return r.json()["id"]


#  GET /noeuds

def test_noeuds(client, reg):
    br = compte(client, reg, BRANCARDIER)   # tout utilisateur connecté peut lire le plan

    tous = client.get("/noeuds", headers=br).json()
    assert len(tous) == 20
    assert "uid_tag_nfc" not in tous[0]      # le tag NFC reste secret

    services = client.get("/noeuds", params={"type_noeud": "SERVICE"}, headers=reg).json()
    assert [s["nom_salle"] for s in services] == [
        "Consultations externes", "Laboratoire", "Radiologie", "Urgences",        # RDC
        "Bloc opératoire", "Cardiologie", "Réanimation", "Salle de réveil"]      # étage 1

    ascenseurs_etage_1 = client.get("/noeuds", params={"type_noeud": "ASCENSEUR", "etage": 1},
                                    headers=reg).json()
    assert len(ascenseurs_etage_1) == 2

    assert client.get("/noeuds").status_code == 401
    assert client.get("/noeuds", params={"type_noeud": "PISCINE"}, headers=reg).status_code == 422


#  GET /missions

def test_liste_triee_par_urgence(client, reg):
    a = compte(client, reg, MEDECIN_A)
    b = compte(client, reg, MEDECIN_B)
    basse = creer(client, a, "BASSE", destination=RADIOLOGIE)
    urgent_1 = creer(client, a, "URGENT")
    haute = creer(client, a, "HAUTE", destination=BLOC)
    urgent_2 = creer(client, a, "URGENT", source=RADIOLOGIE)
    moyenne = creer(client, b, "MOYENNE")

    missions = client.get("/missions", headers=reg).json()
    # URGENT d'abord ; à urgence égale, la plus ancienne d'abord
    assert [m["id"] for m in missions] == [urgent_1, urgent_2, haute, moyenne, basse]
    # Chaque mission porte son itinéraire en étapes pour le dashboard
    assert missions[0]["itineraire_noms"][0] == "Urgences"


def test_medecin_ne_voit_que_ses_demandes(client, reg):
    a = compte(client, reg, MEDECIN_A)
    b = compte(client, reg, MEDECIN_B)
    creer(client, a, "URGENT")
    creer(client, a, "BASSE", destination=RADIOLOGIE)
    creer(client, b, "HAUTE")

    assert len(client.get("/missions", headers=a).json()) == 2
    assert len(client.get("/missions", headers=b).json()) == 1
    assert len(client.get("/missions", headers=reg).json()) == 3


def test_filtres(client, reg):
    a = compte(client, reg, MEDECIN_A)
    creer(client, a, "URGENT")
    creer(client, a, "URGENT", source=RADIOLOGIE)
    creer(client, a, "BASSE", destination=RADIOLOGIE)

    def nombre(params):
        r = client.get("/missions", params=params, headers=reg)
        assert r.status_code == 200, r.text
        return len(r.json())

    assert nombre({"niveau_urgence": "URGENT"}) == 2
    assert nombre({"statut": "EN_ATTENTE"}) == 3
    assert nombre({"statut": "TERMINE"}) == 0
    assert nombre({"statut": ["EN_ATTENTE", "PROPOSE"]}) == 3   # plusieurs statuts à la fois
    assert nombre({"limite": 1}) == 1


def test_liste_acces(client, reg):
    br = compte(client, reg, BRANCARDIER)
    assert client.get("/missions", headers=br).status_code == 403
    assert client.get("/missions").status_code == 401
    assert client.get("/missions", params={"statut": "FINI"}, headers=reg).status_code == 422


#  GET /missions/{id}

def test_detail_mission(client, reg):
    a = compte(client, reg, MEDECIN_A)
    b = compte(client, reg, MEDECIN_B)
    mission_id = creer(client, a, "URGENT")

    for headers in (a, reg):   # le prescripteur et le régulateur
        r = client.get(f"/missions/{mission_id}", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["itineraire"] == [1, 5, 6, 7, 9, 19, 17, 13]
        assert r.json()["duree_estimee"] == pytest.approx(5.0)

    assert client.get(f"/missions/{mission_id}", headers=b).status_code == 404   # un collègue
    assert client.get("/missions/999", headers=reg).status_code == 404


def test_duree_estimee_conservee(client, reg):
    a = compte(client, reg, MEDECIN_A)
    mission_id = creer(client, a, "URGENT")          # 5,0 min par l'ascenseur B

    # Panne de l'ascenseur B après la création de la mission
    aretes = client.get("/aretes", headers=reg).json()
    ascenseur_b = next(x["id"] for x in aretes if (x["noeud_a_id"], x["noeud_b_id"]) == (9, 19))
    client.patch(f"/aretes/{ascenseur_b}", json={"est_bloque": True}, headers=reg)

    # La mission garde l'estimation faite au moment de la demande
    ancienne = client.get(f"/missions/{mission_id}", headers=a).json()
    assert ancienne["duree_estimee"] == pytest.approx(5.0)
    assert 9 in ancienne["itineraire"]

    # Une nouvelle demande passe par l'ascenseur A : 6,0 min
    nouvelle = client.get(f"/missions/{creer(client, a, 'URGENT')}", headers=a).json()
    assert nouvelle["duree_estimee"] == pytest.approx(6.0)
    assert 8 in nouvelle["itineraire"]
