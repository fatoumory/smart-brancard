# routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from models.utilisateur import Utilisateur
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
    _: Utilisateur = Depends(require_role(["regulateur"]))
):
    email = donnees.email.lower()

    # Vérifie si l'email est déjà utilisé
    if db.query(Utilisateur).filter(Utilisateur.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cet email est déjà utilisé"
        )

    # Crée le compte avec le mot de passe hashé
    nouvel_utilisateur = Utilisateur(
        nom=donnees.nom,
        prenom=donnees.prenom,
        email=email,
        mot_de_passe_hash=hash_password(donnees.mot_de_passe),
        role=donnees.role.value
    )
    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)
    return nouvel_utilisateur


#  Connexion 
# Format OAuth2 standard (formulaire application/x-www-form-urlencoded):
# le champ "username" contient l'email, "password" le mot de passe
@router.post("/login", response_model=Token)
def connexion(
    formulaire: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    # Cherche l'utilisateur en base par email
    utilisateur = db.query(Utilisateur).filter(
        Utilisateur.email == formulaire.username.lower()
    ).first()

    # Vérifie l'existence du compte et la validité du mot de passe
    if not utilisateur or not verify_password(formulaire.password, utilisateur.mot_de_passe_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Génère le JWT contenant l'id et le rôle de l'utilisateur
    token = create_jwt_token({
        "sub": str(utilisateur.id),   # sub = subject (identifiant)
        "role": utilisateur.role,
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
