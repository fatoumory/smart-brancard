# schemas/utilisateur.py
# Schémas Pydantic: valident les données entrantes (JSON) et
# contrôlent ce qui est renvoyé au frontend (jamais le hash du mot de passe)

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.enums import Role, StatutAgent


class UtilisateurCreate(BaseModel):
    """Données attendues pour créer un compte (POST /auth/register)"""
    nom_utilisateur: str = Field(min_length=3, max_length=254)
    prenom: str = Field(min_length=1, max_length=100)
    nom: str = Field(min_length=1, max_length=100)
    mot_de_passe: str = Field(min_length=8)
    role: Role

    @field_validator("nom_utilisateur")
    @classmethod
    def normaliser(cls, v: str) -> str:
        # Identifiant insensible à la casse et sans espaces parasites
        return v.strip().lower()

    @field_validator("mot_de_passe")
    @classmethod
    def limite_bcrypt(cls, v: str) -> str:
        # bcrypt ne prend en compte que les 72 premiers octets
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Le mot de passe ne doit pas dépasser 72 octets")
        return v


class UtilisateurOut(BaseModel):
    """Données renvoyées au frontend"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom_utilisateur: str
    prenom: str
    nom: str
    role: Role
    est_actif: bool
    # Renseignés uniquement pour un brancardier
    statut: StatutAgent | None = None
    compteur_mission: int | None = None


class StatutUpdate(BaseModel):
    """Changement de statut opérationnel d'un brancardier"""
    statut: StatutAgent


class Token(BaseModel):
    """Réponse de POST /auth/login"""
    access_token: str
    token_type: str = "bearer"
    role: Role
