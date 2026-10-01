# Journal d'audit des missions : chaque changement de statut laisse une trace horodatée.
# RÈGLE : le statut d'une mission ne se modifie JAMAIS directement (mission.statut = ...),
# toujours avec changer_statut, qui écrit la ligne d'historique en même temps.

from sqlalchemy.orm import Session

from models.enums import MethodeVerification, MotifRefus, StatutMission
from models.historique import Historique
from models.mission import Mission


def changer_statut(
    db: Session,
    mission: Mission,
    nouveau_statut: StatutMission,
    auteur_id: int | None,
    methode: MethodeVerification = MethodeVerification.MANUEL,
    motif_refus: MotifRefus | None = None,
) -> Historique:
    """Change le statut de la mission et ajoute la ligne d'historique correspondante.
    auteur_id=None signifie que c'est l'algorithme qui agit (ex : assignation automatique).
    Ne fait pas de commit : l'appelant enregistre la mission et l'historique ensemble."""
    # Un refus renvoie la mission en attente : c'est le seul cas où un motif a du sens
    if motif_refus is not None and nouveau_statut != StatutMission.EN_ATTENTE:
        raise ValueError("Un motif de refus n'accompagne qu'un retour en EN_ATTENTE")

    mission.statut = nouveau_statut
    ligne = Historique(
        mission_id=mission.id,
        auteur_id=auteur_id,
        statut_modifie_en=nouveau_statut,
        methode_verification=methode,
        motif_refus=motif_refus,
    )
    db.add(ligne)
    return ligne


def historique_de(db: Session, mission_id: int) -> list[Historique]:
    """Lignes d'historique d'une mission, de la plus ancienne à la plus récente"""
    return (db.query(Historique)
            .filter(Historique.mission_id == mission_id)
            .order_by(Historique.horodatage, Historique.id)
            .all())
