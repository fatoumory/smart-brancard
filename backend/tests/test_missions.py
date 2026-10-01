# Création d'une mission : itinéraire Dijkstra, historique, droits d'accès et cas d'erreur

import pytest

from database import SessionLocal
from models.historique import Historique
from models.mission import Mission
from models.noeud_hopital import Arete
from models.patient import Patient
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, REANIMATION, COULOIR_OUEST = 1, 13, 5

DUPONT_ID = 1  # le patient admis par la fixture reg

MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
        "mot_de_passe": "medecin123", "role": "MEDECIN"}
BRANCARDIER = {"nom_utilisateur": "moussa@test.fr", "prenom": "Moussa", "nom": "Ba",
            "mot_de_passe": "brancard123", "role": "BRANCARDIER"}

# Demande valide : M. Dupont, des Urgences vers la Réanimation, sous oxygène
DEMANDE = {"patient_id": DUPONT_ID, "noeud_source_id": URGENCES,
        "noeud_destination_id": REANIMATION, "niveau_urgence": "URGENT",
        "materiel_requis": "OXYGENE",
        "consigne": "Patient sous O2, manipuler avec précaution."}


@pytest.fixture()
def reg(client):
    """Graphe + un patient admis ; renvoie les en-têtes du régulateur"""
    db = SessionLocal()
    charger_graphe_json(db)
    db.add(Patient(id=DUPONT_ID, id_hospitalisation="00000001", prenom="Jean", nom="Dupont",
                   code_bracelet="QR-00000001"))
    # Un blessé inconscient, admis avec une identité provisoire
    db.add(Patient(id=2, id_hospitalisation="00000002", prenom="X-00000002", nom="INCONNU",
                code_bracelet="QR-00000002"))

    db.commit()
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


@pytest.fixture()
def medecin(client, reg):
    client.post("/auth/register", json=MEDECIN, headers=reg)
    return login(client, "diallo@test.fr", "medecin123")


def compter(modele):
    db = SessionLocal()
    try:
        return db.query(modele).count()
    finally:
        db.close()


def test_medecin_cree_une_mission(client, medecin):
    r = client.post("/missions/create", json=DEMANDE, headers=medecin)
    assert r.status_code == 201, r.text
    m = r.json()

    assert m["statut"] == "EN_ATTENTE"
    assert m["brancardier_id"] is None
    assert (m["patient_nom"], m["patient_prenom"]) == ("Dupont", "Jean")
    assert m["materiel_requis"] == "OXYGENE"
    assert m["consigne"] == "Patient sous O2, manipuler avec précaution."

    # Itinéraire de référence : par l'ascenseur B, 5 minutes
    assert m["itineraire"] == [1, 5, 6, 7, 9, 19, 17, 13]
    assert m["itineraire_noms"][0] == "Urgences"
    assert m["itineraire_noms"][-1] == "Réanimation"
    assert m["duree_estimee"] == pytest.approx(5.0)


def test_historique_de_creation(client, medecin):
    medecin_id = client.get("/auth/me", headers=medecin).json()["id"]
    mission_id = client.post("/missions/create", json=DEMANDE, headers=medecin).json()["id"]

    db = SessionLocal()
    lignes = db.query(Historique).filter_by(mission_id=mission_id).all()
    mission = db.get(Mission, mission_id)
    db.close()

    assert mission.prescripteur_id == medecin_id
    assert len(lignes) == 1
    assert lignes[0].statut_modifie_en.value == "EN_ATTENTE"
    assert lignes[0].auteur_id == medecin_id


def test_reserve_au_prescripteur(client, reg):
    client.post("/auth/register", json=BRANCARDIER, headers=reg)
    br = login(client, "moussa@test.fr", "brancard123")
    # Ni le régulateur, ni le brancardier, ni un visiteur non connecté
    assert client.post("/missions/create", json=DEMANDE, headers=reg).status_code == 403
    assert client.post("/missions/create", json=DEMANDE, headers=br).status_code == 403
    assert client.post("/missions/create", json=DEMANDE).status_code == 401
    assert compter(Mission) == 0

def test_patient_non_admis(client, medecin):
    # Aucun patient n'est créé à la création d'une mission : il doit d'abord être admis
    r = client.post("/missions/create", json={**DEMANDE, "patient_id": 999}, headers=medecin)
    assert r.status_code == 404
    assert compter(Mission) == 0
    assert compter(Patient) == 2


def test_mission_pour_un_patient_inconnu(client, medecin):
    # Un blessé inconscient (identité provisoire) doit pouvoir être transporté
    r = client.post("/missions/create", json={**DEMANDE, "patient_id": 2}, headers=medecin)
    assert r.status_code == 201, r.text
    assert (r.json()["patient_nom"], r.json()["patient_prenom"]) == ("INCONNU", "X-00000002")


def test_donnees_invalides(client, medecin):
    for champ, valeur in [("patient_id", "Dupont"),            # un id, pas un nom
                        ( "noeud_destination_id", URGENCES),   # départ = arrivée
                        ("niveau_urgence", "TRES_URGENT"),     # valeur hors énumération
                        ("materiel_requis", "BRANCARD")]:
        r = client.post("/missions/create", json={**DEMANDE, champ: valeur}, headers=medecin)
        assert r.status_code == 422, champ


def test_depart_et_arrivee_doivent_etre_des_services(client, medecin):
    # Un couloir n'est pas un service
    r = client.post("/missions/create", json={**DEMANDE, "noeud_source_id": COULOIR_OUEST},
                    headers=medecin)
    assert r.status_code == 422
    # Un nœud qui n'existe pas
    r = client.post("/missions/create", json={**DEMANDE, "noeud_destination_id": 999},
                    headers=medecin)
    assert r.status_code == 422


def test_aucun_itineraire_possible(client, medecin):
    # Les deux ascenseurs en panne : plus aucun passage entre les étages
    db = SessionLocal()
    for a, b in [(8, 18), (9, 19)]:
        db.query(Arete).filter_by(noeud_a_id=a, noeud_b_id=b).one().est_bloque = True
    db.commit()
    db.close()

    r = client.post("/missions/create", json=DEMANDE, headers=medecin)
    assert r.status_code == 409
    # Rien n'a été enregistré
    assert compter(Mission) == 0
    assert compter(Historique) == 0
