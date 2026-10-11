# services/assignation_service.py
# Assignation automatique des missions aux brancardiers (CDC §5.3).
#
# Règle de choix : parmi les brancardiers actifs et DISPONIBLES,
#   1. le plus proche du point de départ (temps de trajet calculé par Dijkstra),
#   2. à égalité, celui qui a effectué le moins de missions aujourd'hui (équité de charge).
# Un agent jamais détecté par une balise reste éligible, mais passe après les agents localisés.
# Un agent qui a déjà refusé la mission n'est plus sollicité pour elle.
#
# Verrouillage : la mission et les agents candidats sont verrouillés en base (SELECT ... FOR UPDATE)
# pendant le choix, et un index unique interdit à un agent d'avoir deux missions actives.

import math
from datetime import date, datetime, timedelta, timezone

import networkx as nx
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.enums import MotifRefus, NiveauUrgence, StatutAgent, StatutMission
from models.historique import Historique
from models.mission import Mission
from models.utilisateur import Brancardier
from services.graphe_service import construire_graphe
from services.historique_service import changer_statut
from services.position_service import positions_actuelles

# Ordre de traitement de la file : les plus urgentes d'abord, puis les plus anciennes
ORDRE_URGENCE = case(
    {NiveauUrgence.URGENT: 0, NiveauUrgence.HAUTE: 1,
     NiveauUrgence.MOYENNE: 2, NiveauUrgence.BASSE: 3},
    value=Mission.niveau_urgence,
)


#  Compteur de missions du jour (diagramme : reinitialiser_compteur_journalier)

def compteur_du_jour(agent: Brancardier) -> int:
    """Nombre de missions effectuées aujourd'hui par l'agent.
    Le compteur repart de zéro dès qu'on le lit un autre jour : pas besoin de tâche planifiée."""
    if agent.date_compteur != date.today():
        agent.compteur_mission = 0
        agent.date_compteur = date.today()
    return agent.compteur_mission


def incrementer_compteur(agent: Brancardier) -> None:
    """Une mission de plus effectuée aujourd'hui (appelé à la clôture d'une mission)"""
    agent.compteur_mission = compteur_du_jour(agent) + 1


#  Choix de l'agent

def agents_ayant_refuse(db: Session, mission_id: int) -> set[int]:
    """Agents qui ont déjà refusé cette mission (une ligne d'historique avec un motif de refus)"""
    lignes = (db.query(Historique.auteur_id)
              .filter(Historique.mission_id == mission_id,
                      Historique.motif_refus.is_not(None),
                      Historique.auteur_id.is_not(None))
              .all())
    return {auteur_id for (auteur_id,) in lignes}


def classer_candidats(db: Session, mission: Mission, candidats: list[Brancardier]) -> list[tuple]:
    """Classe les candidats du meilleur au moins bon.
    Renvoie [(agent, temps de trajet en minutes ou inf, missions du jour), ...]."""
    positions = positions_actuelles(db, [a.id for a in candidats])

    # Temps de trajet depuis le point de départ vers tous les lieux, en un seul calcul de Dijkstra
    # (le graphe n'est pas orienté : départ -> agent = agent -> départ)
    graphe = construire_graphe(db)
    if mission.noeud_source_id in graphe:
        distances = nx.single_source_dijkstra_path_length(graphe, mission.noeud_source_id, weight="weight")
    else:
        distances = {}

    classement = []
    for agent in candidats:
        detection = positions.get(agent.id)
        # Position inconnue, ou lieu inaccessible (couloir bloqué) : l'agent passe en dernier
        distance = distances.get(detection.noeud_id, math.inf) if detection else math.inf
        classement.append((agent, distance, compteur_du_jour(agent)))

    # Distance d'abord, puis équité de charge ; l'id départage pour un résultat stable
    classement.sort(key=lambda c: (c[1], c[2], c[0].id))
    return classement


def assigner_automatiquement(db: Session, mission_id: int) -> Brancardier | None:
    """Propose la mission au meilleur brancardier disponible (statut PROPOSE).
    Renvoie l'agent choisi, ou None si la mission n'est plus en attente ou si personne n'est libre.
    Fait le commit lui-même : la proposition est enregistrée ou rien ne change."""
    # Verrou sur la mission : une seule assignation à la fois pour elle
    mission = db.query(Mission).filter(Mission.id == mission_id).with_for_update().one_or_none()
    if mission is None or mission.statut != StatutMission.EN_ATTENTE:
        db.rollback()
        return None

    exclus = agents_ayant_refuse(db, mission.id)
    # Verrou sur les agents libres ; un agent déjà verrouillé par une autre assignation est sauté
    requete = (db.query(Brancardier)
               .filter(Brancardier.est_actif.is_(True),
                       Brancardier.statut == StatutAgent.DISPONIBLE)
               .with_for_update(skip_locked=True, of=Brancardier))
    if exclus:
        requete = requete.filter(Brancardier.id.not_in(exclus))
    candidats = requete.all()

    if not candidats:
        db.rollback()
        return None

    agent = classer_candidats(db, mission, candidats)[0][0]

    # Proposition : l'agent est réservé (EN_MISSION) le temps qu'il réponde
    mission.brancardier_id = agent.id
    agent.statut = StatutAgent.EN_MISSION
    # auteur_id=None : c'est l'algorithme qui a choisi l'agent (badge « Auto » côté dashboard)
    changer_statut(db, mission, StatutMission.PROPOSE, auteur_id=None)
    try:
        db.commit()
    except IntegrityError:
        # L'index unique a refusé : l'agent vient de recevoir une autre mission en parallèle
        db.rollback()
        return None
    return agent


def traiter_file_attente(db: Session) -> int:
    """Propose les missions en attente aux agents libres, les plus urgentes et anciennes d'abord.
    À appeler après une création de mission, un refus, ou quand un agent redevient disponible.
    Renvoie le nombre de missions proposées."""
    en_attente = [m_id for (m_id,) in
                  db.query(Mission.id)
                  .filter(Mission.statut == StatutMission.EN_ATTENTE)
                  .order_by(ORDRE_URGENCE, Mission.date_creation, Mission.id)
                  .all()]
    proposees = 0
    for mission_id in en_attente:
        if assigner_automatiquement(db, mission_id) is not None:
            proposees += 1
        elif not (db.query(Brancardier.id)
                  .filter(Brancardier.est_actif.is_(True), Brancardier.statut == StatutAgent.DISPONIBLE)
                  .first()):
            break  # plus aucun agent libre : inutile de parcourir le reste de la file
    return proposees


#  Réponse du brancardier à une proposition

class MissionNonProposee(Exception):
    """La mission n'est pas proposée à cet agent (autre agent, ou mission inexistante)"""


class ReponseImpossible(Exception):
    """La mission n'attend plus de réponse (déjà acceptée, annulée, réaffectée...)"""




def mission_proposee_a(db: Session, mission_id: int, agent: Brancardier) -> Mission:
    """Verrouille la mission et vérifie qu'elle est proposée à cet agent et attend sa réponse"""
    mission = db.query(Mission).filter(Mission.id == mission_id).with_for_update().one_or_none()
    if mission is None or mission.brancardier_id != agent.id:
        raise MissionNonProposee()
    if mission.statut != StatutMission.PROPOSE:
        raise ReponseImpossible()
    return mission


def accepter_mission(db: Session, mission_id: int, agent: Brancardier) -> Mission:
    """L'agent accepte : la mission passe ACCEPTE (il rejoint le patient), l'agent reste EN_MISSION.
    L'acceptation est une décision explicite de l'agent, tracée dans le journal (CDC §7.3)."""
    mission = mission_proposee_a(db, mission_id, agent)
    changer_statut(db, mission, StatutMission.ACCEPTE, auteur_id=agent.id)
    db.commit()
    return mission


def refuser_mission(db: Session, mission_id: int, agent: Brancardier, motif: MotifRefus) -> Mission:
    """L'agent refuse avec un motif : la mission retourne en attente et sera proposée à un autre agent.
    Le refus est tracé avec son motif ; il exclut l'agent des prochaines propositions de cette mission."""
    mission = mission_proposee_a(db, mission_id, agent)
    mission.brancardier_id = None
    changer_statut(db, mission, StatutMission.EN_ATTENTE, auteur_id=agent.id, motif_refus=motif)
    if motif == MotifRefus.URGENCE_PRIORITAIRE:
        # Retenu par une autre urgence : il se met en pause, et revient quand il a fini
        mettre_en_pause(agent)
    else:
        # Matériel défectueux, état physique, fin de service : il ne peut plus transporter
        agent.statut = StatutAgent.INDISPONIBLE
        agent.fin_pause = None
    db.commit()

    # Réaffectation immédiate à l'agent suivant (et, s'il redevient disponible, à cet agent une autre mission)
    traiter_file_attente(db)
    db.refresh(mission)
    return mission


#  Pauses (diagramme : changer_statut, gerer_reprise_service_auto)

DUREE_PAUSE_DEFAUT_MIN = 15


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def mettre_en_pause(agent: Brancardier, minutes: int | None = None) -> None:
    """Met l'agent en pause pour une durée donnée ; le serveur le remettra disponible à la fin"""
    agent.statut = StatutAgent.EN_PAUSE
    agent.fin_pause = maintenant() + timedelta(minutes=minutes or DUREE_PAUSE_DEFAUT_MIN)


def gerer_reprise_service_auto(db: Session) -> int:
    """Remet DISPONIBLES les agents dont la pause est terminée, puis leur propose la file d'attente.
    Appelé régulièrement par la tâche de fond (services/taches_fond.py).
    Renvoie le nombre d'agents remis en service."""
    agents = (db.query(Brancardier)
              .filter(Brancardier.statut == StatutAgent.EN_PAUSE,
                      Brancardier.fin_pause.is_not(None),
                      Brancardier.fin_pause <= maintenant())
              .with_for_update(skip_locked=True, of=Brancardier)
              .all())
    for agent in agents:
        agent.statut = StatutAgent.DISPONIBLE
        agent.fin_pause = None
    db.commit()

    if agents:
        traiter_file_attente(db)
    return len(agents)


#  Délai de réponse à une proposition (CDC §5.3, maquette : « Répondez dans 30 s »)

DELAI_REPONSE = timedelta(seconds=30)


def date_proposition(db: Session, mission_id: int) -> datetime | None:
    """Heure de la dernière proposition de la mission (lue dans le journal d'audit)"""
    return (db.query(func.max(Historique.horodatage))
            .filter(Historique.mission_id == mission_id,
                    Historique.statut_modifie_en == StatutMission.PROPOSE)
            .scalar())


def gerer_propositions_expirees(db: Session, instant: datetime | None = None) -> int:
    """Sans réponse 30 s après la proposition : l'agent passe INDISPONIBLE (il n'est peut-être
    plus joignable) et la mission repart vers un autre agent.
    Appelé régulièrement par la tâche de fond. `instant` permet aux tests de simuler l'heure.
    Renvoie le nombre de propositions expirées."""
    limite = (instant or maintenant()) - DELAI_REPONSE

    # Dernière proposition de chaque mission
    derniere = (db.query(Historique.mission_id, func.max(Historique.horodatage).label("proposee_a"))
                .filter(Historique.statut_modifie_en == StatutMission.PROPOSE)
                .group_by(Historique.mission_id)
                .subquery())
    # Verrou : une mission que l'agent est en train d'accepter (déjà verrouillée) est laissée de côté
    expirees = (db.query(Mission)
                .join(derniere, derniere.c.mission_id == Mission.id)
                .filter(Mission.statut == StatutMission.PROPOSE, derniere.c.proposee_a <= limite)
                .with_for_update(skip_locked=True, of=Mission)
                .all())

    for mission in expirees:
        agent = db.get(Brancardier, mission.brancardier_id)
        if agent is not None:
            agent.statut = StatutAgent.INDISPONIBLE
            agent.fin_pause = None
        mission.brancardier_id = None
        # Retour en attente décidé par le système (auteur vide), sans motif : ce n'est pas un refus
        changer_statut(db, mission, StatutMission.EN_ATTENTE, auteur_id=None)
    db.commit()

    if expirees:
        traiter_file_attente(db)
    return len(expirees)
