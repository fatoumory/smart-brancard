# services/scan_service.py
# Traçabilité du transport par scans (CDC §5.5) :
#   - départ : tag NFC mural de la salle de départ (preuve de présence)
#              + QR du bracelet du patient (identitovigilance)      -> EN_TRANSIT
#   - arrivée : tag NFC mural de la salle de destination            -> TERMINE, agent libéré
# En urgence vitale, le départ peut être forcé sans scan ; le forçage est tracé dans le journal.

from sqlalchemy.orm import Session

from models.enums import MethodeVerification, NiveauUrgence, StatutAgent, StatutMission
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.patient import Patient
from models.utilisateur import Brancardier
from services.assignation_service import (MissionNonProposee, ReponseImpossible,
                                          incrementer_compteur, traiter_file_attente)
from services.historique_service import changer_statut
from services.position_service import enregistrer_detection


class ScanInvalide(Exception):
    """Le tag ou le bracelet scanné ne correspond pas à la mission (message destiné à l'agent)"""


def meme_code(scanne: str | None, attendu: str | None) -> bool:
    """Compare deux codes sans tenir compte des espaces autour ni des majuscules"""
    return bool(scanne and attendu) and scanne.strip().casefold() == attendu.strip().casefold()


def mission_de_l_agent(db: Session, mission_id: int, agent: Brancardier, statut: StatutMission) -> Mission:
    """Verrouille la mission et vérifie qu'elle appartient à l'agent et qu'elle est au bon statut"""
    mission = db.query(Mission).filter(Mission.id == mission_id).with_for_update().one_or_none()
    if mission is None or mission.brancardier_id != agent.id:
        raise MissionNonProposee()
    if mission.statut != statut:
        raise ReponseImpossible()
    return mission


def scanner_depart(db: Session, mission_id: int, agent: Brancardier, tag_nfc: str | None,
                   code_bracelet: str | None, forcer_urgence: bool = False) -> Mission:
    """Prise en charge du patient : la mission passe EN_TRANSIT."""
    mission = mission_de_l_agent(db, mission_id, agent, StatutMission.ACCEPTE)

    if forcer_urgence:
        # Urgence vitale : on ne retarde pas le transport (bracelet illisible, tag hors service...)
        if mission.niveau_urgence != NiveauUrgence.URGENT:
            raise ScanInvalide("Le forçage sans scan est réservé aux missions URGENT")
        methode = MethodeVerification.FORCE_URGENCE
    else:
        depart = db.get(NoeudHopital, mission.noeud_source_id)
        if not meme_code(tag_nfc, depart.uid_tag_nfc):
            raise ScanInvalide(f"Ce tag n'est pas celui du point de départ ({depart.nom_salle})")
        patient = db.get(Patient, mission.patient_id)
        if not meme_code(code_bracelet, patient.code_bracelet):
            raise ScanInvalide("Ce bracelet n'est pas celui du patient de la mission : vérifiez son identité")
        # Le bracelet est la preuve d'identité : c'est la vérification retenue dans le journal
        methode = MethodeVerification.SCAN_CODE_QR

    changer_statut(db, mission, StatutMission.EN_TRANSIT, auteur_id=agent.id, methode=methode,
                   agent_id=agent.id)
    # L'agent est au point de départ : sa position est mise à jour
    enregistrer_detection(db, agent.id, mission.noeud_source_id)
    db.commit()
    return mission


def scanner_arrivee(db: Session, mission_id: int, agent: Brancardier, tag_nfc: str | None) -> Mission:
    """Clôture : la mission passe TERMINE, l'agent redevient disponible."""
    mission = mission_de_l_agent(db, mission_id, agent, StatutMission.EN_TRANSIT)

    destination = db.get(NoeudHopital, mission.noeud_destination_id)
    if not meme_code(tag_nfc, destination.uid_tag_nfc):
        raise ScanInvalide(f"Ce tag n'est pas celui de la destination ({destination.nom_salle})")

    changer_statut(db, mission, StatutMission.TERMINE, auteur_id=agent.id,
                   methode=MethodeVerification.BADGE_NFC, agent_id=agent.id)
    enregistrer_detection(db, agent.id, mission.noeud_destination_id)
    # Diagramme : incrementer_compteur_mission (équité de charge pour les prochaines assignations)
    incrementer_compteur(agent)
    agent.statut = StatutAgent.DISPONIBLE
    db.commit()

    # L'agent libéré reçoit aussitôt la première mission de la file d'attente
    traiter_file_attente(db)
    db.refresh(mission)
    return mission
