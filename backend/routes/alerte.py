# routes/alerte.py
# Alertes du dashboard du régulateur

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.enums import Role
from models.utilisateur import Utilisateur
from schemas.alerte import AlerteOut
from services.alerte_service import AlerteIntrouvable, lister_alertes, traiter_alerte, vers_alertes_out
from services.auth_service import require_role

# Préfixe commun à toutes les routes de ce fichier: /alertes/...
router = APIRouter(prefix="/alertes", tags=["Alertes"])


# Liste des alertes (régulateur)
# Exemple : GET /alertes?traitee=false pour les alertes encore à traiter, les plus récentes d'abord
@router.get("", response_model=list[AlerteOut])
def lister(
    traitee: bool | None = None,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    return vers_alertes_out(db, lister_alertes(db, traitee))


# Le régulateur a réglé la situation : l'alerte est marquée traitée (avec son nom et l'heure)
@router.put("/{alerte_id}/traiter", response_model=AlerteOut)
def traiter(
    alerte_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    try:
        alerte = traiter_alerte(db, alerte_id, current_user)
    except AlerteIntrouvable:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alerte introuvable") from None
    return vers_alertes_out(db, [alerte])[0]
