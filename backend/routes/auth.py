
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.utilisateur import Utilisateur
from services.auth_service import (
    hash_password, 
    verify_password, 
    create_jwt_token,
    get_current_user
)

# Préfixe commun à toutes les routes de ce fichier: /auth/...
router = APIRouter(prefix="/auth", tags=["Authentification"])


#  Inscription 
@router.post("/register")
def inscription(
    nom: str,
    prenom: str,
    email: str,
    mot_de_passe: str,
    role: str,
    db: Session = Depends(get_db)  # session PostgreSQL injectée automatiquement
):
    # Vérifie si l'email est déjà utilisé
    utilisateur_existant = db.query(Utilisateur).filter(
        Utilisateur.email == email
    ).first()
    
    if utilisateur_existant:
        raise HTTPException(
            status_code=400, 
            detail="Cet email est déjà utilisé"
        )

    # Vérifie que le rôle est valide
    roles_valides = ["brancardier", "medecin", "regulateur"]
    if role not in roles_valides:
        raise HTTPException(
            status_code=400,
            detail=f"Rôle invalide - valeurs acceptées : {roles_valides}"
        )

    # Crée le compte avec le mot de passe hashé
    nouvel_utilisateur = Utilisateur(
        nom=nom,
        prenom=prenom,
        email=email,
        mot_de_passe_hash=hash_password(mot_de_passe),
        role=role
    )
    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)

    return {"message": "Compte créé avec succès", "id": nouvel_utilisateur.id}


#  Connexion 
@router.post("/login")
def connexion(
    email: str,
    mot_de_passe: str,
    db: Session = Depends(get_db)
):
    # Cherche l'utilisateur en base par email
    utilisateur = db.query(Utilisateur).filter(
        Utilisateur.email == email
    ).first()

    # Vérifie l'existence du compte et la validité du mot de passe
    if not utilisateur or not verify_password(mot_de_passe, utilisateur.mot_de_passe_hash):
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    # Génère le JWT contenant l'id et le rôle de l'utilisateur
    token = create_jwt_token({
        "sub": str(utilisateur.id),   # sub = subject (identifiant)
        "role": utilisateur.role,
        "nom": utilisateur.nom,
        "prenom": utilisateur.prenom
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "role": utilisateur.role
    }


# Route protégée: exemple RBAC 
@router.get("/me")
def mon_profil(current_user: dict = Depends(get_current_user)):
    """Retourne les infos de l'utilisateur connecté
    Accessible uniquement avec un token JWT valide"""
    return {
        "id": current_user.get("sub"),
        "role": current_user.get("role"),
        "nom": current_user.get("nom"),
        "prenom": current_user.get("prenom")
    }