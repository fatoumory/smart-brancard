# Assignation automatique : choix du brancardier le plus proche, équité de charge,
# file d'attente, exclusions et verrous (CDC §5.3)

from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from database import SessionLocal
from models.enums import MotifRefus, StatutAgent, StatutMission
from models.historique import Historique
from models.mission import Mission
from models.patient import Patient
from models.utilisateur import Brancardier, Utilisateur
from services.assignation_service import compteur_du_jour, incrementer_compteur
from services.graphe_service import charger_graphe_json
from tests.conftest import login

URGENCES, RADIOLOGIE, REANIMATION = 1, 2, 13

MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


def agent_donnees(identifiant):
    return {"nom_utilisateur": f"{identifiant}@test.fr", "prenom": identifiant.capitalize(),
            "nom": "Agent", "mot_de_passe": "brancard123", "role": "BRANCARDIER"}


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


def agent(client, reg, identifiant, position=None, statut=None):
    """Crée un brancardier, le place près d'une balise et lui donne un statut ; renvoie (id, en-têtes)"""
    agent_id = client.post("/auth/register", json=agent_donnees(identifiant), headers=reg).json()["id"]
    entetes = login(client, f"{identifiant}@test.fr", "brancard123")
    if position is not None:
        client.post("/detections", json={"noeud_id": position}, headers=entetes)
    if statut is not None:
        client.patch("/utilisateurs/me/statut", json={"statut": statut}, headers=entetes)
    return agent_id, entetes


def demande(client, medecin, urgence="HAUTE", source=URGENCES, destination=REANIMATION):
    r = client.post("/missions/create", headers=medecin, json={
        "patient_id": 1, "noeud_source_id": source, "noeud_destination_id": destination,
        "niveau_urgence": urgence})
    assert r.status_code == 201, r.text
    return r.json()


def statut_agent(agent_id):
    db = SessionLocal()
    try:
        return db.get(Brancardier, agent_id).statut
    finally:
        db.close()


def test_le_plus_proche_est_choisi(client, reg, medecin):
    loin, _ = agent(client, reg, "loin", position=REANIMATION)
    proche, _ = agent(client, reg, "proche", position=RADIOLOGIE)
    m = demande(client, medecin, source=URGENCES)

    assert m["statut"] == "PROPOSE"
    assert m["brancardier_id"] == proche
    assert statut_agent(proche) == StatutAgent.EN_MISSION   # réservé pendant qu'il répond
    assert statut_agent(loin) == StatutAgent.DISPONIBLE


def test_proposition_tracee_comme_automatique(client, reg, medecin):
    agent(client, reg, "a", position=URGENCES)
    m = demande(client, medecin)
    lignes = client.get(f"/missions/{m['id']}/historique", headers=medecin).json()
    assert [l["statut_modifie_en"] for l in lignes] == ["EN_ATTENTE", "PROPOSE"]
    assert lignes[1]["auteur_id"] is None   # c'est l'algorithme qui a choisi


def test_egalite_departagee_par_la_charge(client, reg, medecin):
    charge, _ = agent(client, reg, "charge", position=URGENCES)
    repose, _ = agent(client, reg, "repose", position=URGENCES)
    db = SessionLocal()
    for agent_id, nombre in ((charge, 5), (repose, 1)):
        a = db.get(Brancardier, agent_id)
        a.compteur_mission, a.date_compteur = nombre, date.today()
    db.commit()
    db.close()

    assert demande(client, medecin)["brancardier_id"] == repose


def test_agent_sans_position_passe_apres_les_agents_localises(client, reg, medecin):
    inconnu, _ = agent(client, reg, "inconnu")                       # jamais détecté
    localise, _ = agent(client, reg, "localise", position=REANIMATION)  # loin, mais localisé
    assert demande(client, medecin)["brancardier_id"] == localise
    # Il reste seul disponible : il reçoit la mission suivante
    assert demande(client, medecin)["brancardier_id"] == inconnu


def test_agents_non_disponibles_ignores(client, reg, medecin):
    agent(client, reg, "pause", position=URGENCES, statut="EN_PAUSE")
    agent(client, reg, "absent", position=URGENCES, statut="INDISPONIBLE")
    desactive, _ = agent(client, reg, "desactive", position=URGENCES)
    db = SessionLocal()
    db.get(Utilisateur, desactive).est_actif = False
    db.commit()
    db.close()

    m = demande(client, medecin)
    assert m["statut"] == "EN_ATTENTE" and m["brancardier_id"] is None


def test_un_agent_ne_recoit_qu_une_mission_a_la_fois(client, reg, medecin):
    seul, _ = agent(client, reg, "seul", position=URGENCES)
    premiere = demande(client, medecin)
    seconde = demande(client, medecin)
    assert premiere["brancardier_id"] == seul
    assert seconde["statut"] == "EN_ATTENTE"


def test_agent_qui_redevient_disponible_recoit_la_plus_urgente(client, reg, medecin):
    agent_id, entetes = agent(client, reg, "a", position=URGENCES, statut="EN_PAUSE")
    basse = demande(client, medecin, urgence="BASSE")
    urgente = demande(client, medecin, urgence="URGENT")
    assert basse["statut"] == urgente["statut"] == "EN_ATTENTE"   # personne de libre

    client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"}, headers=entetes)
    assert client.get(f"/missions/{urgente['id']}", headers=medecin).json()["brancardier_id"] == agent_id
    assert client.get(f"/missions/{basse['id']}", headers=medecin).json()["statut"] == "EN_ATTENTE"


def test_agent_ayant_refuse_n_est_plus_sollicite(client, reg, medecin):
    refuse, entetes = agent(client, reg, "refuse", position=URGENCES, statut="EN_PAUSE")
    autre, _ = agent(client, reg, "autre", position=REANIMATION, statut="EN_PAUSE")
    m = demande(client, medecin)

    # Refus déjà enregistré dans le journal (la route de refus arrive à la tâche 4)
    db = SessionLocal()
    db.add(Historique(mission_id=m["id"], auteur_id=refuse, statut_modifie_en=StatutMission.EN_ATTENTE,
                      motif_refus=MotifRefus.MATERIEL_DEFECTUEUX))
    db.commit()
    db.close()

    # Le plus proche redevient disponible, mais a refusé : la mission attend l'autre agent
    client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"}, headers=entetes)
    assert client.get(f"/missions/{m['id']}", headers=medecin).json()["statut"] == "EN_ATTENTE"
    autre_entetes = login(client, "autre@test.fr", "brancard123")
    client.patch("/utilisateurs/me/statut", json={"statut": "DISPONIBLE"}, headers=autre_entetes)
    assert client.get(f"/missions/{m['id']}", headers=medecin).json()["brancardier_id"] == autre


def test_compteur_remis_a_zero_un_autre_jour():
    a = Brancardier(compteur_mission=7, date_compteur=date.today() - timedelta(days=1))
    assert compteur_du_jour(a) == 0
    incrementer_compteur(a)
    assert (a.compteur_mission, a.date_compteur) == (1, date.today())


def test_verrou_une_mission_active_par_agent(client, reg, medecin):
    agent_id, _ = agent(client, reg, "a", position=URGENCES)
    demande(client, medecin)            # PROPOSE pour cet agent
    autre = demande(client, medecin)    # reste EN_ATTENTE

    # Même en contournant l'API, la base refuse une seconde mission active pour le même agent
    db = SessionLocal()
    mission = db.get(Mission, autre["id"])
    mission.brancardier_id, mission.statut = agent_id, StatutMission.PROPOSE
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_l_agent_ne_choisit_pas_son_statut_pendant_une_mission(client, reg, medecin):
    _, entetes = agent(client, reg, "a", position=URGENCES)
    r = client.patch("/utilisateurs/me/statut", json={"statut": "EN_MISSION"}, headers=entetes)
    assert r.status_code == 422
    demande(client, medecin)  # la mission lui est proposée
    r = client.patch("/utilisateurs/me/statut", json={"statut": "EN_PAUSE"}, headers=entetes)
    assert r.status_code == 409
