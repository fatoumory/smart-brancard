# routes/utilisateurs.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.enums import Role, StatutAgent, StatutMission
from models.mission import Mission
from models.noeud_hopital import NoeudHopital
from models.utilisateur import Brancardier, Utilisateur
from schemas.utilisateur import CarteOut, StatutUpdate, UtilisateurOut
from services.assignation_service import (PauseImpossible, mettre_en_pause, traiter_file_attente,
                                          verifier_pause_possible)
from services.auth_service import nouvelle_carte, require_role
from services.position_service import est_recente, positions_actuelles

# Préfixe commun à toutes les routes de ce fichier: /utilisateurs/...
router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])


#  Liste des utilisateurs (régulateur uniquement)
# Exemple : GET /utilisateurs?role=BRANCARDIER pour superviser la flotte
@router.get("", response_model=list[UtilisateurOut])
def lister_utilisateurs(
    role: Role | None = None,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    requete = db.query(Utilisateur)
    if role is not None:
        requete = requete.filter(Utilisateur.role == role)
    utilisateurs = requete.order_by(Utilisateur.nom, Utilisateur.prenom).all()

    # Position des brancardiers (dernière balise détectée), en deux requêtes pour toute la liste
    positions = positions_actuelles(db, [u.id for u in utilisateurs if isinstance(u, Brancardier)])
    noms = dict(db.query(NoeudHopital.id, NoeudHopital.nom_salle)
                .filter(NoeudHopital.id.in_({d.noeud_id for d in positions.values()})).all())

    resultat = []
    for u in utilisateurs:
        sortie = UtilisateurOut.model_validate(u)
        detection = positions.get(u.id)
        if detection is not None:
            sortie.position_noeud_id = detection.noeud_id
            sortie.position_noeud_nom = noms[detection.noeud_id]
            sortie.position_date = detection.date_heure
            sortie.position_recente = est_recente(detection)
        resultat.append(sortie)
    return resultat


#  Carte de connexion d'un brancardier (régulateur)
# Génère une nouvelle carte : le code est renvoyé une seule fois, pour être imprimé en QR.
# Une carte perdue se remplace ici : l'ancienne ne fonctionne plus.
@router.post("/{utilisateur_id}/carte", response_model=CarteOut, status_code=status.HTTP_201_CREATED)
def generer_carte(
    utilisateur_id: int,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    agent = db.get(Utilisateur, utilisateur_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")
    if agent.role != Role.BRANCARDIER:
        # Médecins et régulateurs gardent leur email et leur mot de passe
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="Les cartes de connexion sont réservées aux brancardiers")
    code = nouvelle_carte(agent)
    db.commit()
    return CarteOut(utilisateur_id=agent.id, prenom=agent.prenom, nom=agent.nom, code=code)


#  Changement de statut (brancardier uniquement)
# Le brancardier passe DISPONIBLE / EN_PAUSE / ... depuis la PWA
@router.patch("/me/statut", response_model=UtilisateurOut)
def changer_mon_statut(
    donnees: StatutUpdate,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    # EN_MISSION est géré par le système (proposition, acceptation, clôture), pas par l'agent
    if donnees.statut == StatutAgent.EN_MISSION:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Le statut « en mission » est attribué automatiquement"
        )
    # Pendant une mission, l'agent ne peut pas changer de statut : il doit la terminer ou la refuser
    mission_active = db.query(Mission.id).filter(
        Mission.brancardier_id == current_user.id,
        Mission.statut.in_([StatutMission.PROPOSE, StatutMission.ACCEPTE, StatutMission.EN_TRANSIT]),
    ).first()
    if mission_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vous avez une mission en cours : terminez-la ou refusez-la d'abord"
        )

    if donnees.statut == StatutAgent.EN_PAUSE:
        # Il doit rester assez d'agents disponibles pour les urgences
        try:
            verifier_pause_possible(db, current_user)
        except PauseImpossible as e:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from None
        # La fin de la pause est gérée par le serveur, pas par le téléphone
        mettre_en_pause(current_user, donnees.duree_pause_minutes)
    else:
        current_user.statut = donnees.statut
        current_user.fin_pause = None
    if donnees.statut == StatutAgent.DISPONIBLE:
        # Il se signale lui-même : ses non-réponses passées ne comptent plus
        current_user.non_reponses = 0
    db.commit()

    # Un agent qui redevient disponible reçoit la première mission de la file d'attente
    if donnees.statut == StatutAgent.DISPONIBLE:
        traiter_file_attente(db)
    db.refresh(current_user)
    return current_user
