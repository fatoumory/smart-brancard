# services/vue_mission_service.py
# Construit les missions renvoyées au frontend (MissionOut), avec tout ce que les écrans affichent :
# patient, trajet, agent (nom, position, arrivée estimée), badge « Auto », délais et horodatages.
#
# Les missions sont complétées PAR LOT : un nombre fixe de requêtes, quelle que soit la taille
# de la liste (sinon le dashboard ferait plusieurs requêtes par mission).

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import networkx as nx
from sqlalchemy.orm import Session

from models.enums import DELAI_GARANTI_MIN, StatutMission
from models.historique import Historique
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.patient import Patient
from models.utilisateur import Brancardier
from schemas.mission import MissionOut
from services.assignation_service import DELAI_REPONSE
from services.graphe_service import construire_graphe
from services.position_service import positions_actuelles

# Statuts où l'agent rejoint le patient : l'arrivée estimée au point de départ a un sens
STATUTS_EN_APPROCHE = {StatutMission.PROPOSE, StatutMission.ACCEPTE}


def en_utc(instant: datetime | None) -> datetime | None:
    """SQLite (tests) renvoie des dates sans fuseau : elles sont en UTC, on le précise"""
    if instant is not None and instant.tzinfo is None:
        return instant.replace(tzinfo=timezone.utc)
    return instant


def construire_missions_out(db: Session, missions: list[Mission]) -> list[MissionOut]:
    """Complète une liste de missions pour le frontend, dans le même ordre"""
    if not missions:
        return []
    maintenant = datetime.now(timezone.utc)
    ids = [m.id for m in missions]

    # 1. Données liées, chacune en une requête
    patients = {p.id: p for p in db.query(Patient).filter(Patient.id.in_({m.patient_id for m in missions}))}
    noms_noeuds = dict(db.query(NoeudHopital.id, NoeudHopital.nom_salle).all())
    ids_agents = {m.brancardier_id for m in missions if m.brancardier_id is not None}
    agents = {a.id: a for a in db.query(Brancardier).filter(Brancardier.id.in_(ids_agents))}
    positions = positions_actuelles(db, list(ids_agents)) if ids_agents else {}

    journal = defaultdict(list)
    for ligne in (db.query(Historique).filter(Historique.mission_id.in_(ids))
                  .order_by(Historique.horodatage, Historique.id)):
        journal[ligne.mission_id].append(ligne)

    # 2. Temps de trajet agent -> point de départ (un seul Dijkstra par point de départ)
    besoin_distances = {m.noeud_source_id for m in missions
                        if m.statut in STATUTS_EN_APPROCHE and m.brancardier_id in positions}
    distances = {}
    if besoin_distances:
        graphe = construire_graphe(db)
        for source in besoin_distances:
            distances[source] = (nx.single_source_dijkstra_path_length(graphe, source, weight="weight")
                                 if source in graphe else {})

    resultat = []
    for m in missions:
        lignes = journal[m.id]
        patient = patients[m.patient_id]
        itineraire = json.loads(m.itineraire)
        delai = DELAI_GARANTI_MIN[m.niveau_urgence]
        cree_a = en_utc(m.date_creation)
        limite = cree_a + timedelta(minutes=delai)

        # Dernière proposition : heure limite de réponse, et qui l'a faite (algorithme = « Auto »)
        propositions = [l for l in lignes if l.statut_modifie_en == StatutMission.PROPOSE]
        derniere_proposition = propositions[-1] if propositions else None
        fin_reponse = None
        if m.statut == StatutMission.PROPOSE and derniere_proposition:
            fin_reponse = en_utc(derniere_proposition.horodatage) + DELAI_REPONSE
        assignation_auto = (derniere_proposition.auteur_id is None
                            if m.brancardier_id is not None and derniere_proposition else None)

        # Horodatages des étapes clés (journal d'audit)
        prise = next((en_utc(l.horodatage) for l in lignes
                      if l.statut_modifie_en == StatutMission.EN_TRANSIT), None)
        fin = next((en_utc(l.horodatage) for l in reversed(lignes)
                    if l.statut_modifie_en in (StatutMission.TERMINE, StatutMission.ANNULE)), None)

        # Délai garanti respecté ? Connu à la prise en charge, ou dès qu'il est dépassé
        if prise is not None:
            dans_les_delais = prise <= limite
        elif m.statut in (StatutMission.EN_ATTENTE, *STATUTS_EN_APPROCHE) and maintenant > limite:
            dans_les_delais = False
        else:
            dans_les_delais = None

        # Agent : identité, position, et arrivée estimée au point de départ s'il est en approche
        agent = agents.get(m.brancardier_id)
        detection = positions.get(m.brancardier_id)
        temps_agent = arrivee = None
        if m.statut in STATUTS_EN_APPROCHE and detection is not None:
            temps_agent = distances.get(m.noeud_source_id, {}).get(detection.noeud_id)
            if temps_agent is not None:
                arrivee = maintenant + timedelta(minutes=temps_agent)

        resultat.append(MissionOut(
            id=m.id,
            statut=m.statut,
            niveau_urgence=m.niveau_urgence,
            materiel_requis=m.materiel_requis,
            materiel_deja_dispo=m.materiel_deja_dispo,
            consigne=m.consigne,
            date_creation=cree_a,
            patient_id=patient.id,
            patient_ipp=patient.id_hospitalisation,
            patient_nom=patient.nom,
            patient_prenom=patient.prenom,
            prescripteur_id=m.prescripteur_id,
            brancardier_id=m.brancardier_id,
            brancardier_nom=agent.nom if agent else None,
            brancardier_prenom=agent.prenom if agent else None,
            brancardier_position_id=detection.noeud_id if detection else None,
            brancardier_position_nom=noms_noeuds[detection.noeud_id] if detection else None,
            assignation_auto=assignation_auto,
            temps_agent_min=temps_agent,
            arrivee_estimee=arrivee,
            noeud_source_id=m.noeud_source_id,
            noeud_source_nom=noms_noeuds[m.noeud_source_id],
            noeud_destination_id=m.noeud_destination_id,
            noeud_destination_nom=noms_noeuds[m.noeud_destination_id],
            itineraire=itineraire,
            itineraire_noms=[noms_noeuds[i] for i in itineraire],
            duree_estimee=m.duree_estimee,
            fin_reponse=fin_reponse,
            delai_garanti_min=delai,
            limite_prise_en_charge=limite,
            date_prise_en_charge=prise,
            date_fin=fin,
            dans_les_delais=dans_les_delais,
        ))
    return resultat
