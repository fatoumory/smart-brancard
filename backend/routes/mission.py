import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.enums import Role, StatutMission, TypeNoeud
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.patient import Patient
from models.utilisateur import Utilisateur
from schemas.mission import MissionCreate, MissionOut, HistoriqueOut
from services.auth_service import require_role
from services.graphe_service import ItineraireIntrouvable, calculer_itineraire, noms_des_noeuds
from services.historique_service import changer_statut, historique_de

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
    # Le statut n'est pas donné ici : c'est changer_statut qui le fixe (étape 5)
    mission = Mission(
        niveau_urgence=donnees.niveau_urgence,
        materiel_requis=donnees.materiel_requis,
        materiel_deja_dispo=donnees.materiel_deja_dispo,
        consigne=donnees.consigne,
        itineraire=json.dumps(chemin),
        patient_id=patient.id,
        prescripteur_id=current_user.id,
        noeud_source_id=donnees.noeud_source_id,
        noeud_destination_id=donnees.noeud_destination_id,
    )
    db.add(mission)
    db.flush()  # attribue un id à la mission, nécessaire pour l'historique

    # 5. Première ligne du journal d'audit : création de la demande (CDC §7.3)
    # 5. Statut EN_ATTENTE + première ligne du journal d'audit : création de la demande (CDC §7.3)
    changer_statut(db, mission, StatutMission.EN_ATTENTE, auteur_id=current_user.id)


    # Mission et historique sont enregistrés ensemble : tout ou rien
    db.commit()
    db.refresh(mission)
    return vers_mission_out(db, mission, duree)

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
        methode_verification=l.methode_verification,
        motif_refus=l.motif_refus,
    ) for l in lignes]

