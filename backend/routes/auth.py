# routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.enums import Role
from models.utilisateur import Brancardier, Utilisateur
from schemas.utilisateur import Token, UtilisateurCreate, UtilisateurOut
from services.auth_service import (
    hash_password,
    verify_password,
    create_jwt_token,
    get_current_user,
    require_role
)

# Préfixe commun à toutes les routes de ce fichier: /auth/...
router = APIRouter(prefix="/auth", tags=["Authentification"])


#  Inscription
# Réservée au régulateur: il crée les comptes des brancardiers et médecins.
# Le tout premier régulateur est créé avec le script seed.py
@router.post("/register", response_model=UtilisateurOut, status_code=status.HTTP_201_CREATED)
def inscription(
    donnees: UtilisateurCreate,
    db: Session = Depends(get_db),  # session PostgreSQL injectée automatiquement
    _: Utilisateur = Depends(require_role([Role.REGULATEUR]))
):
    # Vérifie si l'identifiant est déjà utilisé
    if db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == donnees.nom_utilisateur).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ce nom d'utilisateur est déjà utilisé"
        )

    # Un brancardier a ses propres attributs (statut, compteur de missions)
    classe = Brancardier if donnees.role == Role.BRANCARDIER else Utilisateur
    nouvel_utilisateur = classe(
        nom_utilisateur=donnees.nom_utilisateur,
        prenom=donnees.prenom,
        nom=donnees.nom,
        mot_de_passe_hash=hash_password(donnees.mot_de_passe),
        role=donnees.role
    )
    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)
    return nouvel_utilisateur


#  Connexion
# Format OAuth2 standard (formulaire application/x-www-form-urlencoded):
# le champ "username" contient le nom d'utilisateur, "password" le mot de passe
@router.post("/login", response_model=Token)
def connexion(
    formulaire: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Cherche l'utilisateur en base par son nom d'utilisateur
    utilisateur = db.query(Utilisateur).filter(
        Utilisateur.nom_utilisateur == formulaire.username.strip().lower()
    ).first()

    # Vérifie l'existence du compte et la validité du mot de passe
    if not utilisateur or not verify_password(formulaire.password, utilisateur.mot_de_passe_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not utilisateur.est_actif:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ce compte est désactivé"
        )

    # Génère le JWT contenant l'id et le rôle de l'utilisateur
    token = create_jwt_token({
        "sub": str(utilisateur.id),   # sub = subject (identifiant)
        "role": utilisateur.role.value,
        "nom": utilisateur.nom,
        "prenom": utilisateur.prenom
    })

    return {"access_token": token, "token_type": "bearer", "role": utilisateur.role}


#  Profil de l'utilisateur connecté
@router.get("/me", response_model=UtilisateurOut)
def mon_profil(current_user: Utilisateur = Depends(get_current_user)):
    """Retourne les infos de l'utilisateur connecté
    Accessible uniquement avec un token JWT valide"""
    return current_user
