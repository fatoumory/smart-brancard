# Schémas Pydantic des patients (admission et affichage)

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from models.enums import Sexe, StatutIdentite


class PatientAdmission(BaseModel):
    """Données saisies par l'infirmière d'accueil (POST /patients)"""
    # Patient inconscient ou non identifiable : identité provisoire, nom et prénom ignorés
    identite_inconnue: bool = False
    nom: str | None = Field(default=None, max_length=100)
    prenom: str | None = Field(default=None, max_length=100)
    date_naissance: date | None = None
    sexe: Sexe = Sexe.INDETERMINE
    # L'infirmière confirme qu'il s'agit bien d'une autre personne qu'un patient semblable déjà connu
    confirmer_nouveau: bool = False

    @field_validator("nom", "prenom")
    @classmethod
    def sans_espaces_autour(cls, v: str | None) -> str | None:
        # " Dupont " et "Dupont" désignent la même personne ; une chaîne vide équivaut à "non renseigné"
        if v is None:
            return None
        return v.strip() or None

    @field_validator("date_naissance")
    @classmethod
    def pas_dans_le_futur(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("La date de naissance ne peut pas être dans le futur")
        return v

    @model_validator(mode="after")
    def identite_complete(self):
        # Sans la case "identité inconnue", le nom et le prénom sont obligatoires
        if not self.identite_inconnue and (not self.nom or not self.prenom):
            raise ValueError("Nom et prénom obligatoires (ou cocher « identité inconnue »)")
        return self

class PatientIdentite(BaseModel):
    """Identité confirmée (PATCH /patients/{id}) : remplace une identité provisoire ou corrige une erreur.
    L'IPP et le bracelet ne changent jamais."""
    nom: str = Field(min_length=1, max_length=100)
    prenom: str = Field(min_length=1, max_length=100)
    date_naissance: date | None = None
    # None = sexe inchangé
    sexe: Sexe | None = None
    # L'infirmière confirme qu'il s'agit bien d'une personne distincte d'un patient semblable
    confirmer_nouveau: bool = False

    @field_validator("nom", "prenom")
    @classmethod
    def sans_espaces_autour(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Ce champ ne peut pas être vide")
        return v

    @field_validator("date_naissance")
    @classmethod
    def pas_dans_le_futur(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("La date de naissance ne peut pas être dans le futur")
        return v


class PatientOut(BaseModel):
    """Patient renvoyé au frontend (le code du bracelet sert à imprimer le QR)"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_hospitalisation: str
    nom: str
    prenom: str
    date_naissance: date | None
    sexe: Sexe
    statut_identite: StatutIdentite
    code_bracelet: str
    date_admission: datetime
