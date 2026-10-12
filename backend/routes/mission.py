import json
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from database import get_db
from models.enums import NiveauUrgence, Role, StatutMission, TypeNoeud
from models.historique import Historique
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.patient import Patient
from models.utilisateur import Brancardier, Utilisateur
from schemas.mission import (HistoriqueOut, MissionCreate, MissionOut, Reaffectation, RefusMission,
                             ScanArrivee, ScanDepart)
from services.auth_service import require_role
from services.graphe_service import ItineraireIntrouvable, calculer_itineraire
from services.assignation_service import (MissionNonProposee, ReponseImpossible, accepter_mission,
                                         refuser_mission, traiter_file_attente)
from services.historique_service import changer_statut, historique_de
from services.regulation_service import (ActionImpossible, MissionIntrouvable, annuler_mission,
                                        reaffecter_manuellement)
from services.scan_service import ScanInvalide, scanner_arrivee, scanner_depart
from services.vue_mission_service import construire_missions_out

# Préfixe commun à toutes les routes de ce fichier: /missions/...
router = APIRouter(prefix="/missions", tags=["Missions"])


def service_existant(db: Session, noeud_id: int, role_du_noeud: str) -> NoeudHopital:
    """Vérifie que le nœud existe et que c'est un service (on ne part pas d'un couloir)"""
    noeud = db.get(NoeudHopital, noeud_id)
    if noeud is None or noeud.type_noeud != TypeNoeud.SERVICE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Le nœud {noeud_id} ({role_du_noeud}) doit être un service de l'hôpital"
        )
    return noeud


def vers_mission_out(db: Session, mission: Mission) -> MissionOut:
    """Une mission complétée pour le frontend (voir services/vue_mission_service.py)"""
    return construire_missions_out(db, [mission])[0]


# Création d'une mission (prescripteur uniquement : médecin ou infirmier)
# Enregistre la mission avec l'itinéraire calculé par Dijkstra, statut EN_ATTENTE
@router.post("/create", response_model=MissionOut, status_code=status.HTTP_201_CREATED)
def creer_mission(
    donnees: MissionCreate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role([Role.MEDECIN]))
):
    # 1. Le patient doit avoir été admis (POST /patients) : on ne crée jamais de patient ici
    patient = db.get(Patient, donnees.patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient introuvable : il doit d'abord être admis"
        )


    # 2. Départ et arrivée doivent être des services
    service_existant(db, donnees.noeud_source_id, "départ")
    service_existant(db, donnees.noeud_destination_id, "arrivée")

    # 3. Calcul de l'itinéraire avec Dijkstra (les arêtes bloquées sont ignorées)
    try:
        chemin, duree = calculer_itineraire(db, donnees.noeud_source_id, donnees.noeud_destination_id)
    except ItineraireIntrouvable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Aucun itinéraire possible pour l'instant (ascenseur ou couloir bloqué)"
        ) from None

    # 4. Enregistrement de la mission : l'itinéraire est stocké en texte JSON, ex. "[1, 5, 8]"
    # Le statut n'est pas donné ici : c'est changer_statut qui le fixe (étape 5)
    mission = Mission(
        niveau_urgence=donnees.niveau_urgence,
        materiel_requis=donnees.materiel_requis,
        materiel_deja_dispo=donnees.materiel_deja_dispo,
        consigne=donnees.consigne,
        itineraire=json.dumps(chemin),
        duree_estimee=duree,
        patient_id=patient.id,
        prescripteur_id=current_user.id,
        noeud_source_id=donnees.noeud_source_id,
        noeud_destination_id=donnees.noeud_destination_id,
    )
    db.add(mission)
    db.flush()  # attribue un id à la mission, nécessaire pour l'historique

    # 5. Statut EN_ATTENTE + première ligne du journal d'audit : création de la demande 
    changer_statut(db, mission, StatutMission.EN_ATTENTE, auteur_id=current_user.id)


    # Mission et historique sont enregistrés ensemble : tout ou rien
    db.commit()

    # 6. Assignation automatique (CDC §5.3) : la mission est proposée au meilleur agent libre.
    #    Si personne n'est disponible, elle reste EN_ATTENTE dans la file.
    traiter_file_attente(db)
    db.refresh(mission)
    return vers_mission_out(db, mission)

def mission_visible(db: Session, mission_id: int, utilisateur: Utilisateur) -> Mission:
    """Renvoie la mission si l'utilisateur a le droit de la voir, sinon 404.
    Le régulateur voit tout ; un prescripteur ne voit que les missions qu'il a demandées.
    On répond 404 (et non 403) pour ne pas révéler qu'une mission existe."""
    mission = db.get(Mission, mission_id)
    if mission is None or (utilisateur.role == Role.MEDECIN
                            and mission.prescripteur_id != utilisateur.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Mission introuvable"
        )
    return mission


#  Historique d'une mission (journal d'audit)
# Sert au suivi de la demande (médecin) et au contrôle (régulateur)
@router.get("/{mission_id}/historique", response_model=list[HistoriqueOut])
def lire_historique(
    mission_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role([Role.REGULATEUR, Role.MEDECIN]))
):
    mission_visible(db, mission_id, current_user)
    lignes = historique_de(db, mission_id)

    # Nom des auteurs, en une seule requête ("Algorithme" côté frontend si auteur vide)
    ids = {l.auteur_id for l in lignes if l.auteur_id is not None}
    auteurs = {u.id: f"{u.prenom} {u.nom}"
                for u in db.query(Utilisateur).filter(Utilisateur.id.in_(ids))}

    return [HistoriqueOut(
        id=l.id,
        statut_modifie_en=l.statut_modifie_en,
        horodatage=l.horodatage,
        auteur_id=l.auteur_id,
        auteur_nom=auteurs.get(l.auteur_id),
        brancardier_id=l.brancardier_id,
        methode_verification=l.methode_verification,
        motif_refus=l.motif_refus,
    ) for l in lignes]


#  Mission en cours du brancardier connecté (application mobile)
# Celle qui lui est proposée, qu'il a acceptée, ou qu'il transporte ; null s'il n'en a pas.
# Déclarée avant /{mission_id}, sinon "moi" serait pris pour un identifiant.
@router.get("/moi", response_model=MissionOut | None)
def ma_mission(
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    mission = db.query(Mission).filter(
        Mission.brancardier_id == current_user.id,
        Mission.statut.in_([StatutMission.PROPOSE, StatutMission.ACCEPTE, StatutMission.EN_TRANSIT]),
    ).first()
    return vers_mission_out(db, mission) if mission else None


#  Journal du brancardier (onglet « Journal » de l'application mobile)
# Missions qu'il a terminées dans la journée, de la plus récente à la plus ancienne.
# Exemple : GET /missions/moi/journal  ou  GET /missions/moi/journal?jour=2026-10-12
# La journée va de minuit à minuit en UTC (heure de Dakar).
@router.get("/moi/journal", response_model=list[MissionOut])
def mon_journal(
    jour: date | None = None,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    debut = datetime.combine(jour or datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    ids = {m_id for (m_id,) in
           db.query(Historique.mission_id)
           .join(Mission, Mission.id == Historique.mission_id)
           .filter(Mission.brancardier_id == current_user.id,
                   Mission.statut == StatutMission.TERMINE,
                   Historique.statut_modifie_en == StatutMission.TERMINE,
                   Historique.horodatage >= debut,
                   Historique.horodatage < debut + timedelta(days=1))}
    missions = construire_missions_out(db, db.query(Mission).filter(Mission.id.in_(ids)).all())
    return sorted(missions, key=lambda m: m.date_fin, reverse=True)


# Ordre de priorité : URGENT d'abord (un tri alphabétique donnerait BASSE, HAUTE, MOYENNE, URGENT)
ORDRE_URGENCE = case(
    {NiveauUrgence.URGENT: 0, NiveauUrgence.HAUTE: 1,
    NiveauUrgence.MOYENNE: 2, NiveauUrgence.BASSE: 3},
    value=Mission.niveau_urgence,
)


# Liste des missions (dashboard du régulateur, « mes demandes » du médecin)
# Exemples : GET /missions?statut=EN_ATTENTE&statut=PROPOSE    GET /missions?niveau_urgence=URGENT
@router.get("", response_model=list[MissionOut])
def lister_missions(
    statut: list[StatutMission] | None = Query(default=None),
    niveau_urgence: NiveauUrgence | None = None,
    limite: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role([Role.REGULATEUR, Role.MEDECIN]))
):
    requete = db.query(Mission)
    # Un prescripteur ne voit que ses propres demandes
    if current_user.role == Role.MEDECIN:
        requete = requete.filter(Mission.prescripteur_id == current_user.id)
    if statut:
        requete = requete.filter(Mission.statut.in_(statut))
    if niveau_urgence is not None:
        requete = requete.filter(Mission.niveau_urgence == niveau_urgence)

    # Les plus urgentes d'abord ; à urgence égale, la plus ancienne d'abord (file d'attente)
    missions = requete.order_by(ORDRE_URGENCE, Mission.date_creation, Mission.id).limit(limite).all()
    return construire_missions_out(db, missions)


#  Détail d'une mission (suivi de la demande)
@router.get("/{mission_id}", response_model=MissionOut)
def lire_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role([Role.REGULATEUR, Role.MEDECIN]))
):
    return vers_mission_out(db, mission_visible(db, mission_id, current_user))


#  Réponse du brancardier à une proposition (CDC §5.3)

def erreur_reponse(e: Exception) -> HTTPException:
    if isinstance(e, MissionNonProposee):
        # 404 et non 403 : on ne révèle pas les missions des autres agents
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                             detail="Aucune mission de ce numéro ne vous est proposée")
    return HTTPException(status_code=status.HTTP_409_CONFLICT,
                         detail="Cette mission n'attend plus de réponse")


# Acceptation : la mission passe ACCEPTE, l'agent rejoint le patient
@router.put("/{mission_id}/accept", response_model=MissionOut)
def accepter(
    mission_id: int,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    try:
        mission = accepter_mission(db, mission_id, current_user)
    except (MissionNonProposee, ReponseImpossible) as e:
        db.rollback()
        raise erreur_reponse(e) from None
    return vers_mission_out(db, mission)


# Refus avec motif : la mission repart vers un autre agent ; selon le motif, l'agent devient indisponible
@router.put("/{mission_id}/refuse", response_model=MissionOut)
def refuser(
    mission_id: int,
    donnees: RefusMission,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    try:
        mission = refuser_mission(db, mission_id, current_user, donnees.motif)
    except (MissionNonProposee, ReponseImpossible) as e:
        db.rollback()
        raise erreur_reponse(e) from None
    return vers_mission_out(db, mission)


#  Scans de traçabilité (CDC §5.5)

def erreur_scan(e: Exception, etape: str) -> HTTPException:
    if isinstance(e, MissionNonProposee):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                             detail="Cette mission ne vous est pas attribuée")
    if isinstance(e, ReponseImpossible):
        return HTTPException(status_code=status.HTTP_409_CONFLICT,
                             detail=f"La mission n'en est pas à l'étape « {etape} »")
    # ScanInvalide : le message explique à l'agent ce qui ne correspond pas
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))


# Prise en charge : tag NFC de la salle de départ + QR du bracelet -> EN_TRANSIT
@router.post("/{mission_id}/scan-depart", response_model=MissionOut)
def scan_depart(
    mission_id: int,
    donnees: ScanDepart,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    try:
        mission = scanner_depart(db, mission_id, current_user, donnees.tag_nfc,
                                 donnees.code_bracelet, donnees.forcer_urgence)
    except (MissionNonProposee, ReponseImpossible, ScanInvalide) as e:
        db.rollback()
        raise erreur_scan(e, "prise en charge") from None
    return vers_mission_out(db, mission)


# Clôture : tag NFC de la salle de destination -> TERMINE, l'agent est libéré
@router.post("/{mission_id}/scan-arrivee", response_model=MissionOut)
def scan_arrivee(
    mission_id: int,
    donnees: ScanArrivee,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    try:
        mission = scanner_arrivee(db, mission_id, current_user, donnees.tag_nfc)
    except (MissionNonProposee, ReponseImpossible, ScanInvalide) as e:
        db.rollback()
        raise erreur_scan(e, "arrivée") from None
    return vers_mission_out(db, mission)


#  Actions d'exception du régulateur (maquette : menu « ⋯ » de la file des missions)

def erreur_regulation(e: Exception) -> HTTPException:
    if isinstance(e, MissionIntrouvable):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission introuvable")
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


# Réaffectation manuelle : la mission est proposée au brancardier choisi
@router.put("/{mission_id}/reaffecter", response_model=MissionOut)
def reaffecter(
    mission_id: int,
    donnees: Reaffectation,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    try:
        mission = reaffecter_manuellement(db, mission_id, donnees.brancardier_id, current_user)
    except (MissionIntrouvable, ActionImpossible) as e:
        db.rollback()
        raise erreur_regulation(e) from None
    return vers_mission_out(db, mission)


# Annulation : la mission passe ANNULE, l'agent sollicité est libéré
@router.put("/{mission_id}/annuler", response_model=MissionOut)
def annuler(
    mission_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    try:
        mission = annuler_mission(db, mission_id, current_user)
    except (MissionIntrouvable, ActionImpossible) as e:
        db.rollback()
        raise erreur_regulation(e) from None
    return vers_mission_out(db, mission)
