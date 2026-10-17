# Ajustements demandés après la revue du Sprint 3 :
#   1. journal du brancardier ; 2. position périmée après 10 min ; 3. score d'équité de charge ;
#   4. refus pour matériel défectueux ; 5. délai de réponse selon l'urgence et 2 non-réponses

from datetime import date, datetime, timedelta, timezone

import pytest

from database import SessionLocal
from models.detection import Detection
from models.enums import StatutAgent
from models.patient import Patient
from models.utilisateur import Brancardier
from services.assignation_service import gerer_propositions_expirees
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, REANIMATION, CARDIOLOGIE = 1, 2, 13, 14
COULOIR_EST_RDC, ASCENSEUR_B_RDC = 7, 9   # à 2,5 et 2,75 min des Urgences

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


def agent(client, reg, identifiant, position=None, missions_du_jour=0):
    donnees = {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
               "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
    agent_id = client.post("/auth/register", json=donnees, headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    if position is not None:
        client.post("/detections", json={"noeud_id": position}, headers=entetes)
    if missions_du_jour:
        db = SessionLocal()
        a = db.get(Brancardier, agent_id)
        a.compteur_mission, a.date_compteur = missions_du_jour, date.today()
        db.commit()
        db.close()
    return agent_id, entetes


def demande(client, medecin, urgence="HAUTE", source=URGENCES):
    r = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": source, "noeud_destination_id": REANIMATION,
        "niveau_urgence": urgence})
    assert r.status_code == 201, r.text
    return r.json()


def lire_agent(agent_id):
    db = SessionLocal()
    try:
        a = db.get(Brancardier, agent_id)
        return a.statut, a.non_reponses
    finally:
        db.close()


def expirer(secondes):
    db = SessionLocal()
    try:
        return gerer_propositions_expirees(db, datetime.now(timezone.utc) + timedelta(seconds=secondes))
    finally:
        db.close()


#  1. Journal du brancardier

def test_journal_des_missions_terminees_du_jour(client, reg, medecin):
    _, entetes = agent(client, reg, "a", URGENCES)
    assert client.get("/missions/moi/journal", headers=entetes).json() == []

    ids = []
    for _ in range(2):
        m = client.get("/missions/moi", headers=entetes).json() or demande(client, medecin)
        client.put(f"/missions/{m['id']}/accept", headers=entetes)
        client.post(f"/missions/{m['id']}/scan-depart", headers=entetes,
                    json={"tag_nfc": "NFC-RDC-URG", "code_bracelet": "QR-00000001"})
        client.post(f"/missions/{m['id']}/scan-arrivee", headers=entetes, json={"tag_nfc": "NFC-E1-REA"})
        ids.append(m["id"])

    journal = client.get("/missions/moi/journal", headers=entetes).json()
    assert [m["id"] for m in journal] == list(reversed(ids))   # la plus récente d'abord
    assert all(m["statut"] == "TERMINE" and m["date_fin"] for m in journal)
    # Un autre jour : rien
    hier = (date.today() - timedelta(days=1)).isoformat()
    assert client.get(f"/missions/moi/journal?jour={hier}", headers=entetes).json() == []
    # Réservé aux brancardiers
    assert client.get("/missions/moi/journal", headers=medecin).status_code == 403


#  2. Position périmée

def test_position_de_plus_de_10_minutes_ignoree(client, reg, medecin):
    perime, _ = agent(client, reg, "perime", URGENCES)       # sur place... il y a 2 h
    frais, _ = agent(client, reg, "frais", REANIMATION)      # loin, mais détecté à l'instant
    db = SessionLocal()
    db.query(Detection).filter(Detection.brancardier_id == perime).update(
        {"date_heure": datetime.now(timezone.utc) - timedelta(hours=2)})
    db.commit()
    db.close()

    m = demande(client, medecin)
    assert m["brancardier_id"] == frais
    # Le dashboard garde la dernière position connue, signalée comme ancienne
    agents = {a["id"]: a for a in client.get("/utilisateurs?role=BRANCARDIER", headers=reg).json()}
    assert agents[perime]["position_noeud_id"] == URGENCES and agents[perime]["position_recente"] is False
    assert agents[frais]["position_recente"] is True


#  3. Score d'équité de charge (exemples de la proposition)

def test_equite_entre_agents_presque_a_egalite(client, reg, medecin):
    # Cissé à 2,5 min avec 10 missions (score 7,5), Diop à 2,75 min sans mission (score 2,75)
    agent(client, reg, "cisse", COULOIR_EST_RDC, missions_du_jour=10)
    diop, _ = agent(client, reg, "diop", ASCENSEUR_B_RDC)
    assert demande(client, medecin, urgence="HAUTE")["brancardier_id"] == diop


def test_la_distance_reste_prioritaire_quand_l_ecart_est_grand(client, reg, medecin):
    # Cissé à 1,25 min avec 6 missions (score 4,25), Diop à 5,25 min sans mission (score 5,25)
    cisse, _ = agent(client, reg, "cisse", RADIOLOGIE, missions_du_jour=6)
    agent(client, reg, "diop", CARDIOLOGIE)
    assert demande(client, medecin, urgence="HAUTE")["brancardier_id"] == cisse


def test_en_urgence_seule_la_distance_compte(client, reg, medecin):
    # Même situation que le premier exemple, mais URGENT : k = 0, le plus proche part
    cisse, _ = agent(client, reg, "cisse", COULOIR_EST_RDC, missions_du_jour=10)
    agent(client, reg, "diop", ASCENSEUR_B_RDC)
    assert demande(client, medecin, urgence="URGENT")["brancardier_id"] == cisse


#  4. Refus pour matériel défectueux

def test_materiel_defectueux_alerte_le_regulateur(client, reg, medecin):
    a, entetes = agent(client, reg, "a", URGENCES)
    b, _ = agent(client, reg, "b", REANIMATION)
    m = demande(client, medecin)
    assert m["brancardier_id"] == a

    r = client.put(f"/missions/{m['id']}/refuse", json={"motif": "MATERIEL_DEFECTUEUX"}, headers=entetes)
    # Pas de proposition en boucle : la mission attend la décision du régulateur
    assert r.json()["statut"] == "EN_ATTENTE" and r.json()["alerte_materiel"] is True
    # L'agent n'est pas en cause : il reste disponible ; l'autre agent n'est pas sollicité
    assert lire_agent(a)[0] == StatutAgent.DISPONIBLE
    assert lire_agent(b)[0] == StatutAgent.DISPONIBLE

    # Le régulateur choisit un agent qui a le bon matériel : l'alerte disparaît
    r = client.put(f"/missions/{m['id']}/reaffecter", json={"brancardier_id": b}, headers=reg)
    assert r.json()["statut"] == "PROPOSE" and r.json()["alerte_materiel"] is False


def test_autres_missions_toujours_proposees(client, reg, medecin):
    a, entetes = agent(client, reg, "a", URGENCES)
    bloquee = demande(client, medecin)
    client.put(f"/missions/{bloquee['id']}/refuse", json={"motif": "MATERIEL_DEFECTUEUX"}, headers=entetes)
    # La mission bloquée n'empêche pas la suivante de partir
    suivante = demande(client, medecin, urgence="BASSE")
    assert suivante["brancardier_id"] == a


#  5. Délai de réponse selon l'urgence, et 2 non-réponses

@pytest.mark.parametrize("urgence, delai_s", [("URGENT", 30), ("HAUTE", 45), ("MOYENNE", 60), ("BASSE", 60)])
def test_delai_selon_l_urgence(client, reg, medecin, urgence, delai_s):
    _, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin, urgence=urgence)
    fin = datetime.fromisoformat(m["fin_reponse"]).replace(tzinfo=timezone.utc)
    assert timedelta(seconds=delai_s - 5) < fin - datetime.now(timezone.utc) <= timedelta(seconds=delai_s)
    assert expirer(delai_s - 3) == 0
    assert expirer(delai_s + 1) == 1


def test_indisponible_apres_deux_non_reponses_de_suite(client, reg, medecin):
    a, _ = agent(client, reg, "a", URGENCES)
    demande(client, medecin, urgence="URGENT")
    expirer(31)
    assert lire_agent(a) == (StatutAgent.DISPONIBLE, 1)   # 1re non-réponse : il reste disponible

    demande(client, medecin, urgence="URGENT")             # nouvelle mission, proposée au même agent
    expirer(31)
    assert lire_agent(a) == (StatutAgent.INDISPONIBLE, 2)  # 2e d'affilée : injoignable


def test_une_reponse_remet_le_compteur_a_zero(client, reg, medecin):
    a, entetes = agent(client, reg, "a", URGENCES)
    demande(client, medecin, urgence="URGENT")
    expirer(31)
    m = demande(client, medecin, urgence="URGENT")
    client.put(f"/missions/{m['id']}/refuse", json={"motif": "URGENCE_PRIORITAIRE"}, headers=entetes)
    assert lire_agent(a)[1] == 0


def test_retour_volontaire_remet_le_compteur_a_zero(client, reg, medecin):
    a, entetes = agent(client, reg, "a", URGENCES)
    for _ in range(2):
        demande(client, medecin, urgence="URGENT")
        expirer(31)
    assert lire_agent(a) == (StatutAgent.INDISPONIBLE, 2)
    client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"}, headers=entetes)
    assert lire_agent(a)[1] == 0


def test_agent_sans_reponse_exclu_de_la_mission(client, reg, medecin):
    a, _ = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin, urgence="URGENT")
    expirer(31)
    # Il reste disponible, mais la même mission ne lui est plus proposée
    assert lire_agent(a)[0] == StatutAgent.DISPONIBLE
    assert client.get(f"/missions/{m['id']}", headers=medecin).json()["brancardier_id"] is None


def test_agent_concerne_dans_le_journal(client, reg, medecin):
    a, entetes = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin)
    client.put(f"/missions/{m['id']}/accept", headers=entetes)
    lignes = client.get(f"/missions/{m['id']}/historique", headers=medecin).json()
    assert [(l["statut_modifie_en"], l["brancardier_id"]) for l in lignes] == [
        ("EN_ATTENTE", None), ("PROPOSE", a), ("ACCEPTE", a)]


#  Mission sans candidat : alerte, puis exclusion levée au bout de 5 min

def vieillir_exclusions(minutes):
    """Simule l'écoulement du temps : les refus et non-réponses datent de `minutes` minutes"""
    from models.historique import Historique
    db = SessionLocal()
    db.query(Historique).filter(Historique.statut_modifie_en == "EN_ATTENTE",
                                Historique.brancardier_id.is_not(None)).update(
        {"horodatage": datetime.now(timezone.utc) - timedelta(minutes=minutes)})
    db.commit()
    db.close()


def test_aucun_brancardier_inscrit(client, medecin):
    assert demande(client, medecin)["sans_candidat"] is True


def test_tous_les_agents_exclus(client, reg, medecin):
    a, _ = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin, urgence="URGENT")
    assert m["sans_candidat"] is False   # proposée : rien à signaler
    expirer(31)
    # Le seul agent n'a pas répondu : il reste disponible mais exclu ; personne d'autre
    apres = client.get(f"/missions/{m['id']}", headers=reg).json()
    assert apres["statut"] == "EN_ATTENTE" and apres["sans_candidat"] is True

    # Le régulateur réaffecte sans attendre : l'alerte disparaît
    r = client.put(f"/missions/{m['id']}/reaffecter", json={"brancardier_id": a}, headers=reg)
    assert r.json()["statut"] == "PROPOSE" and r.json()["sans_candidat"] is False


def test_exclusion_levee_au_bout_de_5_minutes(client, reg, medecin):
    from services.taches_fond import executer_taches_periodiques
    a, _ = agent(client, reg, "a", URGENCES)
    m = demande(client, medecin, urgence="URGENT")
    expirer(31)
    vieillir_exclusions(4)
    executer_taches_periodiques()
    assert client.get(f"/missions/{m['id']}", headers=reg).json()["brancardier_id"] is None  # encore exclu

    vieillir_exclusions(6)
    executer_taches_periodiques()   # la tâche de fond relance la file sans autre action
    apres = client.get(f"/missions/{m['id']}", headers=reg).json()
    assert apres["statut"] == "PROPOSE" and apres["brancardier_id"] == a


def test_pas_d_alerte_si_un_agent_peut_encore_la_prendre(client, reg, medecin):
    agent(client, reg, "a", URGENCES)
    agent(client, reg, "b", REANIMATION)
    _, entetes_b = agent(client, reg, "c", REANIMATION)
    client.patch("/utilisateurs/me/statut", json={"statut": "EN_PAUSE"}, headers=entetes_b)
    m = demande(client, medecin, urgence="URGENT")
    expirer(31)   # « a » n'a pas répondu ; « b » reçoit la mission
    assert client.get(f"/missions/{m['id']}", headers=reg).json()["sans_candidat"] is False
