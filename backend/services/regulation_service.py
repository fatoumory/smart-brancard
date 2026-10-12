# services/regulation_service.py
# Actions d'exception du régulateur (maquette : menu « ⋯ » de la file des missions) :
#   - réaffecter manuellement une mission à un brancardier choisi ;
#   - annuler une mission.
# L'agent précédemment sollicité est libéré dans les deux cas.

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.enums import StatutAgent, StatutMission
from models.mission import Mission
from models.utilisateur import Brancardier, Utilisateur
from services.assignation_service import traiter_file_attente
from services.historique_service import changer_statut


class MissionIntrouvable(Exception):
    """Aucune mission de ce numéro"""


class ActionImpossible(Exception):
    """L'action n'est pas permise dans l'état actuel (message destiné au régulateur)"""


# Le régulateur peut intervenir tant que le patient n'est pas en cours de transport
STATUTS_MODIFIABLES = {StatutMission.EN_ATTENTE, StatutMission.PROPOSE, StatutMission.ACCEPTE}


def mission_modifiable(db: Session, mission_id: int) -> Mission:
    mission = db.query(Mission).filter(Mission.id == mission_id).with_for_update().one_or_none()
    if mission is None:
        raise MissionIntrouvable()
    if mission.statut not in STATUTS_MODIFIABLES:
        raise ActionImpossible("Le patient est en cours de transport ou la mission est close : "
                               "elle ne peut plus être modifiée")
    return mission


def liberer_agent(db: Session, mission: Mission) -> None:
    """L'agent qui avait la mission redevient disponible"""
    if mission.brancardier_id is not None:
        ancien = db.get(Brancardier, mission.brancardier_id)
        if ancien is not None:
            ancien.statut = StatutAgent.DISPONIBLE
        mission.brancardier_id = None


def reaffecter_manuellement(db: Session, mission_id: int, brancardier_id: int,
                            regulateur: Utilisateur) -> Mission:
    """Le régulateur choisit lui-même l'agent : la mission lui est proposée (PROPOSE).
    L'agent doit encore accepter, avec le même délai de 30 s qu'une proposition automatique.
    Le journal garde le nom du régulateur : ce n'est pas une assignation « Auto »."""
    mission = mission_modifiable(db, mission_id)
    agent = (db.query(Brancardier).filter(Brancardier.id == brancardier_id)
             .with_for_update(of=Brancardier).one_or_none())
    if agent is None or not agent.est_actif:
        raise ActionImpossible("Ce brancardier n'existe pas ou son compte est désactivé")
    if agent.id == mission.brancardier_id:
        raise ActionImpossible("La mission est déjà confiée à ce brancardier")
    if agent.statut != StatutAgent.DISPONIBLE:
        raise ActionImpossible("Ce brancardier n'est pas disponible")

    liberer_agent(db, mission)
    mission.brancardier_id = agent.id
    agent.statut = StatutAgent.EN_MISSION
    changer_statut(db, mission, StatutMission.PROPOSE, auteur_id=regulateur.id, agent_id=agent.id)
    try:
        db.commit()
    except IntegrityError:
        # Verrou de la base : l'agent vient de recevoir une autre mission
        db.rollback()
        raise ActionImpossible("Ce brancardier vient de recevoir une autre mission") from None

    # L'ancien agent, libéré, peut recevoir une mission en attente
    traiter_file_attente(db)
    db.refresh(mission)
    return mission


def annuler_mission(db: Session, mission_id: int, regulateur: Utilisateur) -> Mission:
    """La mission est annulée (ANNULE) ; l'agent éventuellement sollicité est libéré.
    Une mission n'est jamais supprimée : elle reste dans le journal d'audit (CDC §7.3)."""
    mission = mission_modifiable(db, mission_id)
    agent_id = mission.brancardier_id
    liberer_agent(db, mission)
    changer_statut(db, mission, StatutMission.ANNULE, auteur_id=regulateur.id, agent_id=agent_id)
    db.commit()

    traiter_file_attente(db)
    db.refresh(mission)
    return mission
