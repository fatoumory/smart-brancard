from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.enums import Role
from models.patient import Patient
from models.utilisateur import Utilisateur
from schemas.patient import PatientAdmission, PatientIdentite, PatientOut
from services.auth_service import require_role
from services.patient_service import (PatientsSimilaires, admettre_patient,
                                    rechercher_patients, valider_identite)

# Préfixe commun à toutes les routes de ce fichier: /patients/...
router = APIRouter(prefix="/patients", tags=["Patients"])


def conflit_similaires(e: PatientsSimilaires) -> HTTPException:
    """Erreur 409 avec la liste des patients semblables, pour que l'infirmière choisisse"""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": "Un patient semblable est déjà connu : vérifiez s'il s'agit de la même personne",
            "patients_similaires": [PatientOut.model_validate(p).model_dump(mode="json")
                                    for p in e.patients],
        },
    )


#  Admission d'un patient (infirmière d'accueil : rôle MEDECIN)
# Génère l'IPP et le code du bracelet ; identité provisoire possible (patient inconscient)
@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def admettre(
    donnees: PatientAdmission,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.MEDECIN]))
):
    try:
        return admettre_patient(db, donnees)
    except PatientsSimilaires as e:
        # L'infirmière choisit l'un des patients semblables,
        # ou renvoie la demande avec "confirmer_nouveau": true s'il s'agit d'un homonyme
        raise conflit_similaires(e) from None


#  Recherche de patients (prescripteur)
# Exemple : GET /patients?recherche=dupont jean   ou   GET /patients?recherche=00000148
@router.get("", response_model=list[PatientOut])
def rechercher(
    recherche: str = Query(min_length=2, max_length=100),
    limite: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.MEDECIN]))
):
    return rechercher_patients(db, recherche, limite)


#  Validation ou correction de l'identité (infirmière d'accueil)
# Ex : le patient "INCONNU X-00000148" est identifié comme Moussa Traoré
@router.patch("/{patient_id}", response_model=PatientOut)
def modifier_identite(
    patient_id: int,
    donnees: PatientIdentite,
    db: Session = Depends(get_db),
    _: Utilisateur = Depends(require_role([Role.MEDECIN]))
):
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient introuvable"
        )
    try:
        return valider_identite(db, patient, donnees)
    except PatientsSimilaires as e:
        raise conflit_similaires(e) from None
