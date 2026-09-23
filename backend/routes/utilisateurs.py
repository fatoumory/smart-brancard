# routes/utilisateurs.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.utilisateur import Utilisateur
from schemas.utilisateur import Role, StatutUpdate, UtilisateurOut
from services.auth_service import require_role

# Préfixe commun à toutes les routes de ce fichier: /utilisateurs/...
router = APIRouter(prefix="/utilisateurs", tags=["Utilisateurs"])


#  Liste des utilisateurs (régulateur uniquement) 
# Exemple : GET /utilisateurs?role=brancardier pour superviser la flotte
@router.get("", response_model=list[UtilisateurOut])
def lister_utilisateurs(
    role: Role | None = None,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role(["regulateur"]))
):
    requete = db.query(Utilisateur)
    if role is not None:
        requete = requete.filter(Utilisateur.role == role.value)
    return requete.order_by(Utilisateur.nom, Utilisateur.prenom).all()


#  Changement de statut (brancardier uniquement) 
# Le brancardier passe "disponible" / "pause" / ... depuis la PWA
@router.patch("/me/statut", response_model=UtilisateurOut)
def changer_mon_statut(
    donnees: StatutUpdate,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role(["brancardier"]))
):
    current_user.statut = donnees.statut.value
    db.commit()
    db.refresh(current_user)
    return current_user
