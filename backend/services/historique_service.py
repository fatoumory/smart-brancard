# Journal d'audit des missions : chaque changement de statut laisse une trace horodatée.
# RÈGLE : le statut d'une mission ne se modifie JAMAIS directement (mission.statut = ...),
# toujours avec changer_statut, qui écrit la ligne d'historique en même temps.

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models.enums import MethodeVerification, MotifRefus, StatutMission
from models.historique import Historique
from models.mission import Mission
from services.position_service import en_utc

# Actions faites hors ligne : le téléphone peut avoir quelques minutes d'avance (horloge mal
# réglée), et une action ne peut pas être renvoyée plus de 30 min après avoir été faite
AVANCE_TOLEREE = timedelta(minutes=2)
RETARD_MAX_HORS_LIGNE = timedelta(minutes=30)


class HorodatageInvalide(Exception):
    """L'heure d'une action faite hors ligne est incohérente (message destiné à l'agent)"""


def verifier_horodatage_client(horodatage_client: datetime | None, mission: Mission,
                               instant: datetime | None = None) -> datetime | None:
    """Contrôle l'heure envoyée par le téléphone pour une action faite hors ligne.
    Refusée si elle est dans le futur, avant la création de la mission, ou trop ancienne :
    sinon un agent en retard pourrait antidater son scan pour paraître dans les délais."""
    if horodatage_client is None:
        return None
    instant = instant or datetime.now(timezone.utc)
    heure = en_utc(horodatage_client)
    if (heure > instant + AVANCE_TOLEREE
            or heure < en_utc(mission.date_creation)
            or heure < instant - RETARD_MAX_HORS_LIGNE):
        raise HorodatageInvalide("Heure de l'action incohérente : vérifiez l'heure du téléphone")
    return heure


def changer_statut(
    db: Session,
    mission: Mission,
    nouveau_statut: StatutMission,
    auteur_id: int | None,
    methode: MethodeVerification = MethodeVerification.MANUEL,
    motif_refus: MotifRefus | None = None,
    agent_id: int | None = None,
    horodatage_client: datetime | None = None,
) -> Historique:
    """Change le statut de la mission et ajoute la ligne d'historique correspondante.
    auteur_id=None signifie que c'est l'algorithme qui agit (ex : assignation automatique).
    agent_id : le brancardier concerné par ce changement (proposé, qui accepte, refuse, scanne...).
    horodatage_client : heure réelle d'une action faite hors ligne, déjà vérifiée.
    Ne fait pas de commit : l'appelant enregistre la mission et l'historique ensemble."""
    # Un refus renvoie la mission en attente : c'est le seul cas où un motif a du sens
    if motif_refus is not None and nouveau_statut != StatutMission.EN_ATTENTE:
        raise ValueError("Un motif de refus n'accompagne qu'un retour en EN_ATTENTE")

    mission.statut = nouveau_statut
    ligne = Historique(
        mission_id=mission.id,
        auteur_id=auteur_id,
        brancardier_id=agent_id,
        statut_modifie_en=nouveau_statut,
        methode_verification=methode,
        motif_refus=motif_refus,
        horodatage_client=horodatage_client,
    )
    db.add(ligne)
    return ligne


def historique_de(db: Session, mission_id: int) -> list[Historique]:
    """Lignes d'historique d'une mission, de la plus ancienne à la plus récente"""
    return (db.query(Historique)
            .filter(Historique.mission_id == mission_id)
            .order_by(Historique.horodatage, Historique.id)
            .all())
