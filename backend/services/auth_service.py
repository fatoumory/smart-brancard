# services/auth_service.py

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from database import get_db
from models.utilisateur import Utilisateur

load_dotenv()

#  Configuration JWT 
# Clé secrète utilisée pour signer les tokens: lue depuis le .env, jamais écrite dans le code
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY manquante dans le .env (voir .env.example)")

# Algorithme de signature du JWT
ALGORITHM = "HS256"

# Durée de validité du token: 8h = durée d'une garde
EXPIRATION_HEURES = 8

# Schéma OAuth2: indique à FastAPI où trouver le token dans les requêtes
# tokenUrl = la route qui délivre le token (utilisée par le bouton "Authorize" de Swagger)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


#  Fonctions de hashage (bcrypt) 

def hash_password(mot_de_passe: str) -> str:
    """Hash le mot de passe avant de le stocker en base"""
    return bcrypt.hashpw(mot_de_passe.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(mot_de_passe: str, hash: str) -> bool:
    """Compare le mot de passe saisi avec le hash stocké en base"""
    try:
        return bcrypt.checkpw(mot_de_passe.encode("utf-8"), hash.encode("utf-8"))
    except ValueError:
        # mot de passe > 72 octets ou hash mal formé
        return False


#  Fonctions JWT 

def create_jwt_token(data: dict) -> str:
    """Génère un token JWT contenant les infos de l'utilisateur + expiration"""
    to_encode = data.copy()
    expiration = datetime.now(timezone.utc) + timedelta(hours=EXPIRATION_HEURES)
    to_encode.update({"exp": expiration})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_jwt_token(token: str) -> dict | None:
    """Décode et vérifie un token JWT: retourne None si invalide ou expiré"""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


#  Dépendances FastAPI (RBAC) 

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Utilisateur:
    """Récupère l'utilisateur connecté depuis le token JWT
    Injecté dans les routes protégées via Depends(get_current_user)"""
    erreur = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré, veuillez vous reconnecter",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_jwt_token(token)
    if not payload or not str(payload.get("sub", "")).isdigit():
        raise erreur

    # On relit l'utilisateur en base: un compte supprimé n'a plus accès,
    # même si son token n'a pas encore expiré
    utilisateur = db.get(Utilisateur, int(payload["sub"]))
    if utilisateur is None:
        raise erreur
    return utilisateur

def require_role(roles_autorises: list[str]):
    """Vérifie que l'utilisateur connecté a le bon rôle
    Exemple d'utilisation : Depends(require_role(['regulateur', 'medecin']))"""
    def verifier(current_user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
        if current_user.role not in roles_autorises:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès interdit, rôle requis : {roles_autorises}"
            )
        return current_user
    return verifier
