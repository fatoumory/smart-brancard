# routes/utilisateurs.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.enums import Role
from models.utilisateur import Brancardier, Utilisateur
from schemas.utilisateur import StatutUpdate, UtilisateurOut
from services.auth_service import require_role

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
    return requete.order_by(Utilisateur.nom, Utilisateur.prenom).all()


#  Changement de statut (brancardier uniquement)
# Le brancardier passe DISPONIBLE / EN_PAUSE / ... depuis la PWA
@router.patch("/me/statut", response_model=UtilisateurOut)
def changer_mon_statut(
    donnees: StatutUpdate,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    current_user.statut = donnees.statut
    db.commit()
    db.refresh(current_user)
    return current_user
