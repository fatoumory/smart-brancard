# Données des missions pour les écrans : agent, position, arrivée estimée, badge « Auto »,
# délais garantis et horodatages ; construction par lot (nombre de requêtes constant)

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event

from database import SessionLocal, engine
from models.mission import Mission
from models.patient import Patient
from services.graphe_service import calculer_itineraire, charger_graphe_json
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
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": "Amadou", "nom": "Cissé",
               "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    client.post("/detections", json={"noeud_id": position}, headers=entetes)
    return agent_id, entetes


def demande(client, medecin, urgence="URGENT"):
    return client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": URGENCES, "noeud_destination_id": REANIMATION,
        "niveau_urgence": urgence}).json()


def heure(texte):
    return datetime.fromisoformat(texte).replace(tzinfo=timezone.utc) if texte else None


def test_mission_en_attente(client, medecin):
    m = demande(client, medecin, urgence="HAUTE")
    assert m["statut"] == "EN_ATTENTE"
    assert m["brancardier_nom"] is None and m["assignation_auto"] is None and m["arrivee_estimee"] is None
    # Délai garanti selon l'urgence (HAUTE : 8 min) et heure limite de prise en charge
    assert m["delai_garanti_min"] == 8
    assert heure(m["limite_prise_en_charge"]) - heure(m["date_creation"]) == timedelta(minutes=8)
    assert m["dans_les_delais"] is None   # pas encore pris en charge, délai pas encore dépassé


def test_agent_en_approche(client, reg, medecin):
    agent_id, _ = agent(client, reg, "a", RADIOLOGIE)
    m = demande(client, medecin)

    # Ce que la maquette du suivi médecin affiche : nom de l'agent, sa position, son arrivée estimée
    assert (m["brancardier_prenom"], m["brancardier_nom"]) == ("Amadou", "Cissé")
    assert m["brancardier_position_nom"] == "Radiologie"
    assert m["assignation_auto"] is True   # choisi par l'algorithme : badge « Auto »

    db = SessionLocal()
    attendu = calculer_itineraire(db, RADIOLOGIE, URGENCES)[1]
    db.close()
    assert m["temps_agent_min"] == pytest.approx(attendu)
    restant = heure(m["arrivee_estimee"]) - datetime.now(timezone.utc)
    assert timedelta(minutes=attendu) - timedelta(seconds=10) < restant <= timedelta(minutes=attendu)


def test_reaffectation_manuelle_sans_badge_auto(client, reg, medecin):
    agent(client, reg, "a", URGENCES)
    choisi, _ = agent(client, reg, "b", REANIMATION)
    m = demande(client, medecin)
    r = client.put(f"/missions/{m['id']}/reaffecter", json={"brancardier_id": choisi}, headers=reg)
    assert r.json()["assignation_auto"] is False


def test_horodatages_du_cycle_complet(client, reg, medecin):
    _, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    en_route = client.get(f"/missions/{m['id']}", headers=medecin).json()
    assert en_route["arrivee_estimee"] is not None          # acceptée : agent en approche

    client.post(f"/missions/{m['id']}/scan-depart", headers=entetes,
                json={"tag_nfc": "NFC-RDC-URG", "code_bracelet": "QR-00000001"})
    pris = client.get(f"/missions/{m['id']}", headers=medecin).json()
    assert pris["date_prise_en_charge"] is not None and pris["arrivee_estimee"] is None
    assert pris["dans_les_delais"] is True                    # pris en charge tout de suite

    client.post(f"/missions/{m['id']}/scan-arrivee", headers=entetes, json={"tag_nfc": "NFC-E1-REA"})
    fini = client.get(f"/missions/{m['id']}", headers=medecin).json()
    assert heure(fini["date_fin"]) >= heure(fini["date_prise_en_charge"])


def test_delai_depasse(client, medecin):
    m = demande(client, medecin, urgence="URGENT")
    # La demande a été faite il y a 10 min et personne ne l'a prise en charge (délai URGENT : 3 min)
    db = SessionLocal()
    db.get(Mission, m["id"]).date_creation = datetime.now(timezone.utc) - timedelta(minutes=10)
    db.commit()
    db.close()
    assert client.get(f"/missions/{m['id']}", headers=medecin).json()["dans_les_delais"] is False


def test_mission_annulee(client, reg, medecin):
    m = demande(client, medecin)
    annulee = client.put(f"/missions/{m['id']}/annuler", headers=reg).json()
    assert annulee["date_fin"] is not None and annulee["dans_les_delais"] is None


def test_liste_en_nombre_de_requetes_constant(client, reg, medecin):
    agent(client, reg, "a", URGENCES)

    def requetes_pour_la_liste():
        compte = []
        ecouteur = lambda *args: compte.append(1)
        event.listen(engine, "before_cursor_execute", ecouteur)
        try:
            assert client.get("/missions", headers=reg).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", ecouteur)
        return len(compte)

    for _ in range(3):
        demande(client, medecin)
    avec_3 = requetes_pour_la_liste()
    for _ in range(12):
        demande(client, medecin)
    avec_15 = requetes_pour_la_liste()
    # 5 fois plus de missions, et pas une requête de plus
    assert avec_15 == avec_3
