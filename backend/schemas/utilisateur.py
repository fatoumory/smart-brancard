# schemas/utilisateur.py
# Schémas Pydantic: valident les données entrantes (JSON) et
# contrôlent ce qui est renvoyé au frontend (jamais le hash du mot de passe)

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Role(str, Enum):
    brancardier = "brancardier"
    medecin = "medecin"
    regulateur = "regulateur"


class StatutAgent(str, Enum):
    disponible = "disponible"
    en_mission = "en_mission"
    pause = "pause"
    indisponible = "indisponible"


class UtilisateurCreate(BaseModel):
    """Données attendues pour créer un compte (POST /auth/register)"""
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    email: EmailStr
    mot_de_passe: str = Field(min_length=8)
    role: Role

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
    nom: str
    prenom: str
    email: EmailStr
    role: Role
    statut: StatutAgent
    created_at: datetime


class StatutUpdate(BaseModel):
    """Changement de statut opérationnel d'un brancardier"""
    statut: StatutAgent


class Token(BaseModel):
    """Réponse de POST /auth/login"""
    access_token: str
    token_type: str = "bearer"
    role: Role
