import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.enums import MethodeVerification, Role, StatutMission, TypeNoeud
from models.historique import Historique
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.patient import Patient
from models.utilisateur import Utilisateur
from schemas.mission import MissionCreate, MissionOut
from services.auth_service import require_role
from services.graphe_service import ItineraireIntrouvable, calculer_itineraire, noms_des_noeuds

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


def vers_mission_out(db: Session, mission: Mission, duree: float) -> MissionOut:
    """Complète la mission avec le patient et les noms des nœuds pour le frontend"""
    patient = db.get(Patient, mission.patient_id)
    itineraire = json.loads(mission.itineraire)
    noms = noms_des_noeuds(db, itineraire)
    return MissionOut(
        id=mission.id,
        statut=mission.statut,
        niveau_urgence=mission.niveau_urgence,
        materiel_requis=mission.materiel_requis,
        materiel_deja_dispo=mission.materiel_deja_dispo,
        consigne=mission.consigne,
        date_creation=mission.date_creation,
        patient_id=patient.id,
        patient_ipp=patient.id_hospitalisation,
        patient_nom=patient.nom,
        patient_prenom=patient.prenom,
        prescripteur_id=mission.prescripteur_id,
        brancardier_id=mission.brancardier_id,
        noeud_source_id=mission.noeud_source_id,
        noeud_source_nom=noms[0],
        noeud_destination_id=mission.noeud_destination_id,
        noeud_destination_nom=noms[-1],
        itineraire=itineraire,
        itineraire_noms=noms,
        duree_estimee=duree,
    )


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
    mission = Mission(
        niveau_urgence=donnees.niveau_urgence,
        materiel_requis=donnees.materiel_requis,
        materiel_deja_dispo=donnees.materiel_deja_dispo,
        consigne=donnees.consigne,
        statut=StatutMission.EN_ATTENTE,
        itineraire=json.dumps(chemin),
        patient_id=patient.id,
        prescripteur_id=current_user.id,
        noeud_source_id=donnees.noeud_source_id,
        noeud_destination_id=donnees.noeud_destination_id,
    )
    db.add(mission)
    db.flush()  # attribue un id à la mission, nécessaire pour l'historique

    # 5. Première ligne du journal d'audit : création de la demande (CDC §7.3)
    db.add(Historique(
        mission_id=mission.id,
        auteur_id=current_user.id,
        statut_modifie_en=StatutMission.EN_ATTENTE,
        methode_verification=MethodeVerification.MANUEL,
    ))

    # Mission et historique sont enregistrés ensemble : tout ou rien
    db.commit()
    db.refresh(mission)
    return vers_mission_out(db, mission, duree)
