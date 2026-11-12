# services/alerte_service.py
# Appel du régulateur par un agent bloqué pendant une mission : après plusieurs scans du bracelet
# refusés, ou un bracelet illisible. L'appel crée une alerte sur le dashboard du régulateur, qui
# la marque comme traitée une fois la situation réglée (il peut aussi clôturer, réaffecter...).

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.alerte import Alerte
from models.enums import RaisonAppel, StatutMission
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.utilisateur import Brancardier, Utilisateur
from schemas.alerte import AlerteOut
from services.position_service import position_actuelle


class MissionSansAgent(Exception):
    """La mission n'est pas confiée à cet agent (ou n'existe pas)"""


class MissionPasEnCours(Exception):
    """La mission n'est ni acceptée ni en transit : rien à signaler au régulateur"""


class AlerteIntrouvable(Exception):
    """Aucune alerte de ce numéro"""


# On peut appeler le régulateur entre l'acceptation et l'arrivée
STATUTS_APPEL_POSSIBLE = {StatutMission.ACCEPTE, StatutMission.EN_TRANSIT}


def appeler_regulateur(db: Session, mission_id: int, agent: Brancardier, raison: RaisonAppel) -> Alerte:
    """Crée l'alerte. Un agent qui appelle plusieurs fois pour la même mission (il appuie de
    nouveau, ou son téléphone renvoie la demande) ne crée pas de doublon : l'alerte en cours
    est renvoyée telle quelle."""
    mission = db.get(Mission, mission_id)
    if mission is None or mission.brancardier_id != agent.id:
        raise MissionSansAgent()
    if mission.statut not in STATUTS_APPEL_POSSIBLE:
        raise MissionPasEnCours()

    en_cours = (db.query(Alerte)
                .filter(Alerte.mission_id == mission.id, Alerte.brancardier_id == agent.id,
                        Alerte.traitee.is_(False))
                .first())
    if en_cours is not None:
        return en_cours

    alerte = Alerte(mission_id=mission.id, brancardier_id=agent.id, raison=raison)
    db.add(alerte)
    db.commit()
    db.refresh(alerte)
    return alerte


def vers_alertes_out(db: Session, alertes: list[Alerte]) -> list[AlerteOut]:
    """Complète les alertes pour le dashboard : nom de l'agent et lieu où le trouver"""
    noms_noeuds = dict(db.query(NoeudHopital.id, NoeudHopital.nom_salle).all())
    resultat = []
    for a in alertes:
        agent = db.get(Brancardier, a.brancardier_id)
        mission = db.get(Mission, a.mission_id)
        position = position_actuelle(db, a.brancardier_id)
        lieu = position.noeud_id if position is not None else mission.noeud_source_id
        resultat.append(AlerteOut(
            id=a.id, raison=a.raison, date_creation=a.date_creation,
            mission_id=a.mission_id, brancardier_id=a.brancardier_id,
            brancardier_prenom=agent.prenom, brancardier_nom=agent.nom,
            lieu_nom=noms_noeuds[lieu],
            traitee=a.traitee, date_traitement=a.date_traitement, traitee_par_id=a.traitee_par_id,
        ))
    return resultat


def lister_alertes(db: Session, traitee: bool | None = None) -> list[Alerte]:
    """Alertes de la plus récente à la plus ancienne ; traitee=False : seulement celles en cours"""
    requete = db.query(Alerte)
    if traitee is not None:
        requete = requete.filter(Alerte.traitee.is_(traitee))
    return requete.order_by(Alerte.date_creation.desc(), Alerte.id.desc()).all()


def traiter_alerte(db: Session, alerte_id: int, regulateur: Utilisateur) -> Alerte:
    """Le régulateur a réglé la situation : l'alerte quitte la liste des alertes en cours.
    Une alerte déjà traitée garde la date et l'auteur de son premier traitement."""
    alerte = db.get(Alerte, alerte_id)
    if alerte is None:
        raise AlerteIntrouvable()
    if not alerte.traitee:
        alerte.traitee = True
        alerte.date_traitement = datetime.now(timezone.utc)
        alerte.traitee_par_id = regulateur.id
        db.commit()
        db.refresh(alerte)
    return alerte
