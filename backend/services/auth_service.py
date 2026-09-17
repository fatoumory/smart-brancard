
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

#  Configuration JWT 
# Clé secrète utilisée pour signer les tokens (à mettre dans un .env en production)
SECRET_KEY = "smart_brancard_secret_key_a_changer_en_production"

# Algorithme de signature du JWT
ALGORITHM = "HS256"

# Durée de validité du token: 8h = durée d'une garde
EXPIRATION_HEURES = 8

#  Configuration du hashage des mots de passe 
# bcrypt est l'algorithme recommandé pour hasher les mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Schéma OAuth2: indique à FastAPI où trouver le token dans les requêtes
# tokenUrl = la route qui délivre le token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


#  Fonctions de hashage 

def hash_password(mot_de_passe: str) -> str:
    """Hash le mot de passe avant de le stocker en base"""
    return pwd_context.hash(mot_de_passe)

def verify_password(mot_de_passe: str, hash: str) -> bool:
    """Compare le mot de passe saisi avec le hash stocké en base"""
    return pwd_context.verify(mot_de_passe, hash)


#  Fonctions JWT 

def create_jwt_token(data: dict) -> str:
    """Génère un token JWT contenant les infos de l'utilisateur + expiration"""
    to_encode = data.copy()
    # Calcul de la date d'expiration
    expiration = datetime.now(timezone.utc) + timedelta(hours=EXPIRATION_HEURES)
    to_encode.update({"exp": expiration})
    # Signature et encodage du token
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_jwt_token(token: str) -> dict | None:
    """Décode et vérifie un token JWT: retourne None si invalide ou expiré"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


#  Dépendances FastAPI (RBAC) 

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Récupère l'utilisateur connecté depuis le token JWT
    Injecté dans les routes protégées via Depends(get_current_user)"""
    payload = decode_jwt_token(token)
    if not payload:
        raise HTTPException(
            status_code=401, 
            detail="Token invalide ou expiré, veuillez vous reconnecter"
        )
    return payload

def require_role(roles_autorises: list):
    """Vérifie que l'utilisateur connecté a le bon rôle
    Exemple d'utilisation : Depends(require_role(['regulateur', 'medecin']))"""
    def verifier(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") not in roles_autorises:
            raise HTTPException(
                status_code=403,
                detail=f"Accès interdit, rôle requis : {roles_autorises}"
            )
        return current_user
    return verifier