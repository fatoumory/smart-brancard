# services/compte_service.py
# Désactivation et réactivation des comptes par le régulateur (départ d'un agent, compte compromis).
# On ne supprime jamais un compte : les missions et le journal d'audit pointent vers lui, et le
# supprimer effacerait la trace de qui a demandé, transporté ou annulé un transport.
# Un compte désactivé ne peut plus se connecter (mot de passe ou carte) ni recevoir de mission.

from sqlalchemy.orm import Session

from models.enums import StatutAgent, StatutMission
from models.mission import Mission
from models.utilisateur import Brancardier, Utilisateur
from services.assignation_service import traiter_file_attente
from services.historique_service import changer_statut


class CompteIntrouvable(Exception):
    """Aucun utilisateur de ce numéro"""


class DesactivationImpossible(Exception):
    """La désactivation n'est pas possible maintenant (message destiné au régulateur)"""


def changer_activation(db: Session, utilisateur_id: int, est_actif: bool, regulateur: Utilisateur) -> Utilisateur:
    """Active ou désactive un compte. Pour un brancardier désactivé :
    - une mission proposée ou acceptée repart en attente, pour un autre agent ;
    - une mission en transit bloque la désactivation (le patient est en cours de transport) ;
    - il passe INDISPONIBLE, et le reste s'il est réactivé : il se signale lui-même disponible."""
    utilisateur = db.get(Utilisateur, utilisateur_id)
    if utilisateur is None:
        raise CompteIntrouvable()
    if utilisateur.id == regulateur.id and not est_actif:
        raise DesactivationImpossible("Vous ne pouvez pas désactiver votre propre compte")
    if utilisateur.est_actif == est_actif:
        return utilisateur   # déjà dans l'état demandé : rien à faire

    remise_en_attente = False
    if not est_actif and isinstance(utilisateur, Brancardier):
        missions = (db.query(Mission)
                    .filter(Mission.brancardier_id == utilisateur.id,
                            Mission.statut.in_([StatutMission.PROPOSE, StatutMission.ACCEPTE,
                                                StatutMission.EN_TRANSIT]))
                    .with_for_update()
                    .all())
        if any(m.statut == StatutMission.EN_TRANSIT for m in missions):
            raise DesactivationImpossible("Ce brancardier transporte un patient : "
                                          "attendez la fin de la mission ou clôturez-la d'abord")
        for mission in missions:
            # Retour en attente décidé par le régulateur ; l'agent concerné reste noté au journal
            mission.brancardier_id = None
            changer_statut(db, mission, StatutMission.EN_ATTENTE, auteur_id=regulateur.id,
                           agent_id=utilisateur.id)
            remise_en_attente = True
        utilisateur.statut = StatutAgent.INDISPONIBLE
        utilisateur.fin_pause = None

    utilisateur.est_actif = est_actif
    db.commit()

    # La mission reprise à l'agent désactivé est proposée à quelqu'un d'autre
    if remise_en_attente:
        traiter_file_attente(db)
    db.refresh(utilisateur)
    return utilisateur
