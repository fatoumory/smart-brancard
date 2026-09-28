# Journal d'audit : une ligne à chaque changement de statut, et sa consultation

import pytest

from database import SessionLocal
from models.enums import MethodeVerification, MotifRefus, StatutMission
from models.historique import Historique
from models.mission import Mission
from models.patient import Patient
from services.graphe_service import charger_graphe_json
from services.historique_service import changer_statut, historique_de
from tests.conftest import login

MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
        "mot_de_passe": "medecin123", "role": "MEDECIN"}
AUTRE_MEDECIN = {"nom_utilisateur": "sow@test.fr", "prenom": "Ibrahima", "nom": "Sow",
                "mot_de_passe": "medecin123", "role": "MEDECIN"}
BRANCARDIER = {"nom_utilisateur": "moussa@test.fr", "prenom": "Moussa", "nom": "Ba",
            "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
DEMANDE = {"patient_id": 1, "noeud_source_id": 1, "noeud_destination_id": 13,
        "niveau_urgence": "URGENT"}


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
def mission_id(client, medecin):
    r = client.post("/missions/create", json=DEMANDE, headers=medecin)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_changer_statut_ecrit_une_ligne_a_chaque_fois(client, mission_id):
    db = SessionLocal()
    mission = db.get(Mission, mission_id)

    # L'algorithme propose la mission (auteur vide), puis un brancardier la refuse avec un motif
    changer_statut(db, mission, StatutMission.PROPOSE, auteur_id=None)
    changer_statut(db, mission, StatutMission.EN_ATTENTE, auteur_id=None,
                motif_refus=MotifRefus.MATERIEL_DEFECTUEUX)
    changer_statut(db, mission, StatutMission.EN_TRANSIT, auteur_id=None,
                methode=MethodeVerification.BADGE_NFC)
    db.commit()

    lignes = historique_de(db, mission_id)
    statut_final = db.get(Mission, mission_id).statut
    db.close()

    assert [l.statut_modifie_en for l in lignes] == [
        StatutMission.EN_ATTENTE, StatutMission.PROPOSE,
        StatutMission.EN_ATTENTE, StatutMission.EN_TRANSIT]
    assert lignes[1].auteur_id is None                                # l'algorithme
    assert lignes[2].motif_refus == MotifRefus.MATERIEL_DEFECTUEUX    # le refus
    assert lignes[3].methode_verification == MethodeVerification.BADGE_NFC
    assert statut_final == StatutMission.EN_TRANSIT                   # la mission suit


def test_motif_seulement_pour_un_refus(client, mission_id):
    db = SessionLocal()
    mission = db.get(Mission, mission_id)
    with pytest.raises(ValueError):
        changer_statut(db, mission, StatutMission.TERMINE, auteur_id=None,
                    motif_refus=MotifRefus.FIN_SERVICE)
    db.close()


def test_lire_historique(client, reg, medecin, mission_id):
    db = SessionLocal()
    changer_statut(db, db.get(Mission, mission_id), StatutMission.PROPOSE, auteur_id=None)
    db.commit()
    db.close()

    for headers in (medecin, reg):   # le prescripteur et le régulateur
        r = client.get(f"/missions/{mission_id}/historique", headers=headers)
        assert r.status_code == 200, r.text
        lignes = r.json()
        assert [l["statut_modifie_en"] for l in lignes] == ["EN_ATTENTE", "PROPOSE"]
        assert lignes[0]["auteur_nom"] == "Awa Diallo"
        assert lignes[1]["auteur_id"] is None and lignes[1]["auteur_nom"] is None
        assert lignes[0]["horodatage"] <= lignes[1]["horodatage"]


def test_historique_acces(client, reg, mission_id):
    # Un autre médecin ne voit pas les missions de sa collègue : 404, comme si elle n'existait pas
    client.post("/auth/register", json=AUTRE_MEDECIN, headers=reg)
    autre = login(client, "sow@test.fr", "medecin123")
    assert client.get(f"/missions/{mission_id}/historique", headers=autre).status_code == 404

    client.post("/auth/register", json=BRANCARDIER, headers=reg)
    br = login(client, "moussa@test.fr", "brancard123")
    assert client.get(f"/missions/{mission_id}/historique", headers=br).status_code == 403
    assert client.get(f"/missions/{mission_id}/historique").status_code == 401
    assert client.get("/missions/999/historique", headers=reg).status_code == 404
