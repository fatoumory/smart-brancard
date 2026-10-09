# schemas/utilisateur.py
# Schémas Pydantic: valident les données entrantes (JSON) et
# contrôlent ce qui est renvoyé au frontend (jamais le hash du mot de passe)

from datetime import datetime

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
    # Position actuelle d'un brancardier : sa dernière détection de balise (vide si jamais détecté)
    position_noeud_id: int | None = None
    position_noeud_nom: str | None = None
    position_date: datetime | None = None
    # Fin prévue de la pause en cours (le téléphone affiche le compte à rebours à partir de cette heure)
    fin_pause: datetime | None = None


class StatutUpdate(BaseModel):
    """Changement de statut opérationnel d'un brancardier"""
    statut: StatutAgent
    # Durée de la pause en minutes (seulement pour EN_PAUSE ; 15 min si non précisée)
    duree_pause_minutes: int | None = Field(default=None, ge=1, le=60)


class Token(BaseModel):
    """Réponse de POST /auth/login"""
    access_token: str
    token_type: str = "bearer"
    role: Role
