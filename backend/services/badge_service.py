# services/badge_service.py
# Badges BLE des brancardiers (CDC §1.4, §4.5).
#
# Dans un vrai hôpital, chaque agent porte un badge qui émet en Bluetooth basse consommation (BLE),
# et un récepteur fixé dans chaque salle (par exemple un ESP32) prévient le serveur quand il capte
# un badge. Dans le prototype, le simulateur de badges joue ce rôle : il envoie la même information,
# « le badge de tel agent est dans telle salle », toutes les 5 à 10 secondes.
#
# Le serveur n'a donc pas besoin de savoir si la détection vient d'un vrai récepteur ou du
# simulateur : les deux arrivent par POST /detections/badge.
#
# Ce que le badge déclenche, sans aucun geste de l'agent :
#   1. arrivée à destination : badge présent depuis 30 s dans la salle d'arrivée d'une mission
#      en transit -> la mission est terminée (méthode BALISE). L'agent reste occupé : il remet
#      le patient à l'équipe du service ;
#   2. sortie de la salle : son badge est capté ailleurs -> il redevient disponible. S'il reste
#      dans la salle ou que son badge ne répond plus, il est libéré 10 min après la fin de la
#      mission (tâche de fond, liberer_agents_apres_mission).

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.detection import Detection
from models.enums import MethodeVerification, OrigineDetection, StatutAgent, StatutMission
from models.historique import Historique
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.utilisateur import Brancardier
from services.assignation_service import incrementer_compteur, traiter_file_attente
from services.historique_service import changer_statut
from services.position_service import en_utc, enregistrer_detection

# Présence minimale dans la salle d'arrivée : un simple passage dans le couloir ne termine rien
DUREE_PRESENCE_ARRIVEE = timedelta(seconds=30)

# Temps laissé à l'agent pour remettre le patient : au-delà, il redevient disponible quoi qu'il arrive
DUREE_MAX_REMISE_PATIENT = timedelta(minutes=10)

STATUTS_ACTIFS = [StatutMission.PROPOSE, StatutMission.ACCEPTE, StatutMission.EN_TRANSIT]


class BadgeInconnu(Exception):
    """Aucun brancardier ne porte ce badge (identifiant inconnu)"""


class LieuInconnu(Exception):
    """Aucun récepteur n'est installé dans ce lieu (identifiant de nœud inconnu)"""


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def debut_de_presence(db: Session, agent_id: int, noeud_id: int) -> datetime | None:
    """Depuis quand le badge de l'agent est capté sans interruption dans ce lieu :
    première détection par badge dans ce lieu après sa dernière détection ailleurs"""
    derniere_ailleurs = (db.query(func.max(Detection.date_heure))
                         .filter(Detection.brancardier_id == agent_id, Detection.noeud_id != noeud_id)
                         .scalar())
    requete = db.query(func.min(Detection.date_heure)).filter(
        Detection.brancardier_id == agent_id,
        Detection.noeud_id == noeud_id,
        Detection.origine == OrigineDetection.BADGE,
    )
    if derniere_ailleurs is not None:
        requete = requete.filter(Detection.date_heure > derniere_ailleurs)
    return en_utc(requete.scalar())


def derniere_fin_de_mission(db: Session, agent_id: int) -> tuple[Mission, datetime] | None:
    """La dernière mission terminée par l'agent, avec l'heure de sa clôture"""
    ligne = (db.query(Historique)
             .filter(Historique.brancardier_id == agent_id,
                     Historique.statut_modifie_en == StatutMission.TERMINE)
             .order_by(Historique.horodatage.desc(), Historique.id.desc())
             .first())
    if ligne is None:
        return None
    return db.get(Mission, ligne.mission_id), en_utc(ligne.horodatage)


def a_une_mission_active(db: Session, agent_id: int) -> bool:
    return db.query(Mission.id).filter(Mission.brancardier_id == agent_id,
                                       Mission.statut.in_(STATUTS_ACTIFS)).first() is not None


def terminer_si_arrive(db: Session, agent: Brancardier, noeud_id: int, instant: datetime) -> Mission | None:
    """Mission en transit vers ce lieu, badge présent depuis 30 s : la mission est terminée.
    L'agent reste EN_MISSION pendant la remise du patient (voir liberer_si_sorti)."""
    mission = (db.query(Mission)
               .filter(Mission.brancardier_id == agent.id, Mission.statut == StatutMission.EN_TRANSIT,
                       Mission.noeud_destination_id == noeud_id)
               .with_for_update()
               .one_or_none())
    if mission is None:
        return None
    debut = debut_de_presence(db, agent.id, noeud_id)
    if debut is None or instant - debut < DUREE_PRESENCE_ARRIVEE:
        return None

    # Clôture décidée par le système (auteur vide), prouvée par le badge
    changer_statut(db, mission, StatutMission.TERMINE, auteur_id=None,
                   methode=MethodeVerification.BALISE, agent_id=agent.id)
    incrementer_compteur(agent)
    return mission


def liberer_si_sorti(db: Session, agent: Brancardier, noeud_id: int) -> bool:
    """Agent occupé sans mission active (il remettait un patient) dont le badge est capté hors
    de la salle d'arrivée : il a quitté la salle, il redevient disponible"""
    if agent.statut != StatutAgent.EN_MISSION or a_une_mission_active(db, agent.id):
        return False
    fin = derniere_fin_de_mission(db, agent.id)
    if fin is not None and fin[0].noeud_destination_id == noeud_id:
        return False   # toujours dans la salle où il a déposé le patient
    agent.statut = StatutAgent.DISPONIBLE
    return True


def detecter_badge(db: Session, brancardier_id: int, noeud_id: int) -> Detection:
    """Enregistre la détection du badge d'un agent dans un lieu, puis en tire les conséquences
    (arrivée à destination, sortie de la salle). Fait le commit."""
    agent = db.query(Brancardier).filter(Brancardier.id == brancardier_id).with_for_update().one_or_none()
    if agent is None:
        raise BadgeInconnu()
    if db.get(NoeudHopital, noeud_id) is None:
        raise LieuInconnu()

    detection = enregistrer_detection(db, agent.id, noeud_id, OrigineDetection.BADGE)
    db.flush()   # la détection compte déjà dans le calcul de la présence
    terminer_si_arrive(db, agent, noeud_id, maintenant())
    db.flush()   # une mission tout juste terminée ne compte plus comme active
    libere = liberer_si_sorti(db, agent, noeud_id)
    db.commit()
    db.refresh(detection)

    # L'agent libéré reçoit aussitôt la première mission de la file d'attente
    if libere:
        traiter_file_attente(db)
    return detection


def liberer_agents_apres_mission(db: Session, instant: datetime | None = None) -> int:
    """Tâche de fond : un agent resté occupé 10 min après la fin de sa mission (il est resté
    dans la salle, ou son badge ne répond plus) redevient disponible.
    Renvoie le nombre d'agents libérés."""
    instant = instant or maintenant()
    occupes = (db.query(Brancardier)
               .filter(Brancardier.statut == StatutAgent.EN_MISSION)
               .with_for_update(skip_locked=True, of=Brancardier)
               .all())
    liberes = 0
    for agent in occupes:
        if a_une_mission_active(db, agent.id):
            continue
        fin = derniere_fin_de_mission(db, agent.id)
        if fin is None or instant - fin[1] >= DUREE_MAX_REMISE_PATIENT:
            agent.statut = StatutAgent.DISPONIBLE
            liberes += 1
    db.commit()

    if liberes:
        traiter_file_attente(db)
    return liberes
