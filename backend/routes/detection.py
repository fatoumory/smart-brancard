# routes/detection.py
# Position des agents : réception des détections de balises BLE (simulées)

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models.enums import OrigineDetection, Role
from models.noeud_hopital import NoeudHopital
from models.utilisateur import Brancardier, Utilisateur
from schemas.detection import DetectionBadge, DetectionCreate, DetectionOut
from services.auth_service import require_role
from services.badge_service import BadgeInconnu, LieuInconnu, detecter_badge
from services.position_service import enregistrer_detection, position_actuelle

# Préfixe commun à toutes les routes de ce fichier: /detections/...
router = APIRouter(prefix="/detections", tags=["Position des agents"])


#  Détection d'une balise (brancardier uniquement)
# Le téléphone de l'agent capte la balise du lieu où il passe et l'envoie ici.
# Dans le prototype, les balises sont simulées : l'application (ou Locust) envoie le lieu.
@router.post("", response_model=DetectionOut, status_code=status.HTTP_201_CREATED)
def detecter(
    donnees: DetectionCreate,
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    noeud = db.get(NoeudHopital, donnees.noeud_id)
    if noeud is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lieu inconnu : aucune balise à cet endroit"
        )

    # Position déclarée par l'agent : elle sert à le classer, mais ne prouve pas sa présence
    detection = enregistrer_detection(db, current_user.id, noeud.id, OrigineDetection.DECLARATION)
    db.commit()
    db.refresh(detection)
    return DetectionOut(id=detection.id, brancardier_id=current_user.id, noeud_id=noeud.id,
                        noeud_nom=noeud.nom_salle, date_heure=detection.date_heure)


#  Badge capté par le récepteur d'une salle (simulateur de badges, ou ESP32 dans un vrai hôpital)
# Exemple : {"brancardier_id": 7, "noeud_id": 12} = le badge de l'agent 7 est en Salle de réveil.
# Réservé au régulateur (le simulateur tourne sur son poste) et à l'administrateur (compte technique
# d'une passerelle de récepteurs) : un agent ne peut pas déclarer lui-même la position d'un autre.
@router.post("/badge", response_model=DetectionOut, status_code=status.HTTP_201_CREATED)
def badge_detecte(
    donnees: DetectionBadge,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.REGULATEUR, Role.ADMIN]))
):
    try:
        detection = detecter_badge(db, donnees.brancardier_id, donnees.noeud_id)
    except BadgeInconnu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Badge inconnu : aucun brancardier avec cet identifiant") from None
    except LieuInconnu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Lieu inconnu : aucun récepteur à cet endroit") from None
    noeud = db.get(NoeudHopital, detection.noeud_id)
    return DetectionOut(id=detection.id, brancardier_id=detection.brancardier_id, noeud_id=noeud.id,
                        noeud_nom=noeud.nom_salle, date_heure=detection.date_heure)


#  Ma position actuelle (brancardier)
@router.get("/me", response_model=DetectionOut | None)
def ma_position(
    db: Session = Depends(get_db),
    current_user: Brancardier = Depends(require_role([Role.BRANCARDIER]))
):
    detection = position_actuelle(db, current_user.id)
    if detection is None:
        return None
    noeud = db.get(NoeudHopital, detection.noeud_id)
    return DetectionOut(id=detection.id, brancardier_id=current_user.id, noeud_id=noeud.id,
                        noeud_nom=noeud.nom_salle, date_heure=detection.date_heure)
