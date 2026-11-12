# services/scan_service.py
# Traçabilité du transport par scans (CDC §4.6) :
#   - départ : preuve de présence dans la salle de départ (badge détecté, sinon tag NFC mural)
#              + QR du bracelet du patient (identitovigilance)      -> EN_TRANSIT
#   - arrivée : tag NFC mural de la salle de destination            -> TERMINE, agent libéré
# En urgence vitale, le départ peut être forcé sans scan ; le forçage est tracé dans le journal.
#
# Actions faites hors ligne : le téléphone envoie l'heure réelle de l'action (horodatage_client),
# vérifiée puis gardée au journal à côté de l'heure de réception. Une action déjà enregistrée et
# renvoyée (réponse perdue) renvoie la mission telle quelle, sans être comptée deux fois.

from datetime import datetime

from sqlalchemy.orm import Session

from models.enums import MethodeVerification, NiveauUrgence, OrigineDetection, StatutAgent, StatutMission
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.patient import Patient
from models.utilisateur import Brancardier
from services.assignation_service import (DejaFait, MissionNonProposee, ReponseImpossible,
                                          incrementer_compteur, traiter_file_attente)
from services.historique_service import changer_statut, verifier_horodatage_client
from services.position_service import enregistrer_detection, etait_present


class ScanInvalide(Exception):
    """Le tag ou le bracelet scanné ne correspond pas à la mission (message destiné à l'agent)"""


# Statuts où la prise en charge, ou l'arrivée, de l'agent est déjà enregistrée
APRES_PRISE_EN_CHARGE = {StatutMission.EN_TRANSIT, StatutMission.TERMINE}
APRES_ARRIVEE = {StatutMission.TERMINE}


def meme_code(scanne: str | None, attendu: str | None) -> bool:
    """Compare deux codes sans tenir compte des espaces autour ni des majuscules"""
    return bool(scanne and attendu) and scanne.strip().casefold() == attendu.strip().casefold()


def mission_de_l_agent(db: Session, mission_id: int, agent: Brancardier, statut: StatutMission,
                       deja_fait: set[StatutMission] | None = None) -> Mission:
    """Verrouille la mission et vérifie qu'elle appartient à l'agent et qu'elle est au bon statut.
    deja_fait : statuts où cette étape est déjà enregistrée pour cet agent (lève DejaFait)"""
    mission = db.query(Mission).filter(Mission.id == mission_id).with_for_update().one_or_none()
    if mission is None or mission.brancardier_id != agent.id:
        raise MissionNonProposee()
    if deja_fait and mission.statut in deja_fait:
        raise DejaFait(mission)
    if mission.statut != statut:
        raise ReponseImpossible()
    return mission


def scanner_depart(db: Session, mission_id: int, agent: Brancardier, tag_nfc: str | None,
                   code_bracelet: str | None, forcer_urgence: bool = False,
                   horodatage_client: datetime | None = None) -> Mission:
    """Prise en charge du patient : la mission passe EN_TRANSIT."""
    try:
        mission = mission_de_l_agent(db, mission_id, agent, StatutMission.ACCEPTE, APRES_PRISE_EN_CHARGE)
    except DejaFait as e:
        db.commit()   # scan renvoyé : rien ne change, on libère seulement le verrou
        return e.mission
    heure = verifier_horodatage_client(horodatage_client, mission)

    if forcer_urgence:
        # Urgence vitale : on ne retarde pas le transport (bracelet illisible, tag hors service...)
        if mission.niveau_urgence != NiveauUrgence.URGENT:
            raise ScanInvalide("Le forçage sans scan est réservé aux missions URGENT")
        methode = MethodeVerification.FORCE_URGENCE
    else:
        depart = db.get(NoeudHopital, mission.noeud_source_id)
        if tag_nfc:
            # Tag scanné (secours, ou badge non détecté) : il doit être celui de la salle de départ
            if not meme_code(tag_nfc, depart.uid_tag_nfc):
                raise ScanInvalide(f"Ce tag n'est pas celui du point de départ ({depart.nom_salle})")
        elif not etait_present(db, agent.id, depart.id, heure):
            # Pas de tag : c'est le badge qui doit prouver que l'agent était dans la salle de départ
            # au moment du scan
            raise ScanInvalide(f"Votre badge n'a pas été détecté au point de départ ({depart.nom_salle}) : "
                               "scannez le tag de la salle")
        patient = db.get(Patient, mission.patient_id)
        if not meme_code(code_bracelet, patient.code_bracelet):
            raise ScanInvalide("Ce bracelet n'est pas celui du patient de la mission : vérifiez son identité")
        # Le bracelet est la preuve d'identité : c'est la vérification retenue dans le journal
        methode = MethodeVerification.SCAN_CODE_QR

    changer_statut(db, mission, StatutMission.EN_TRANSIT, auteur_id=agent.id, methode=methode,
                   agent_id=agent.id, horodatage_client=heure)
    # L'agent est au point de départ : sa position est mise à jour
    enregistrer_detection(db, agent.id, mission.noeud_source_id, OrigineDetection.SCAN)
    db.commit()
    return mission


def terminer_par_l_agent(db: Session, mission: Mission, agent: Brancardier, methode: MethodeVerification,
                         heure: datetime | None) -> Mission:
    """Clôture faite par l'agent (scan du tag ou bouton « Arrivé ») : il redevient disponible
    et reçoit aussitôt la première mission de la file d'attente"""
    changer_statut(db, mission, StatutMission.TERMINE, auteur_id=agent.id, methode=methode,
                   agent_id=agent.id, horodatage_client=heure)
    # Diagramme : incrementer_compteur_mission (équité de charge pour les prochaines assignations)
    incrementer_compteur(agent)
    agent.statut = StatutAgent.DISPONIBLE
    db.commit()

    traiter_file_attente(db)
    db.refresh(mission)
    return mission


def scanner_arrivee(db: Session, mission_id: int, agent: Brancardier, tag_nfc: str | None,
                    horodatage_client: datetime | None = None) -> Mission:
    """Clôture : la mission passe TERMINE, l'agent redevient disponible."""
    try:
        mission = mission_de_l_agent(db, mission_id, agent, StatutMission.EN_TRANSIT, APRES_ARRIVEE)
    except DejaFait as e:
        db.commit()
        return e.mission
    heure = verifier_horodatage_client(horodatage_client, mission)

    destination = db.get(NoeudHopital, mission.noeud_destination_id)
    if not meme_code(tag_nfc, destination.uid_tag_nfc):
        raise ScanInvalide(f"Ce tag n'est pas celui de la destination ({destination.nom_salle})")

    enregistrer_detection(db, agent.id, mission.noeud_destination_id, OrigineDetection.SCAN)
    return terminer_par_l_agent(db, mission, agent, MethodeVerification.BADGE_NFC, heure)


def declarer_arrivee(db: Session, mission_id: int, agent: Brancardier,
                     horodatage_client: datetime | None = None) -> Mission:
    """Bouton « Arrivé » : secours quand le badge n'a pas été détecté dans la salle d'arrivée
    (badge oublié, récepteur en panne). Rien n'est prouvé : la clôture est tracée « MANUEL »,
    avec l'agent comme auteur. L'agent redevient disponible."""
    try:
        mission = mission_de_l_agent(db, mission_id, agent, StatutMission.EN_TRANSIT, APRES_ARRIVEE)
    except DejaFait as e:
        db.commit()
        return e.mission
    heure = verifier_horodatage_client(horodatage_client, mission)
    return terminer_par_l_agent(db, mission, agent, MethodeVerification.MANUEL, heure)
