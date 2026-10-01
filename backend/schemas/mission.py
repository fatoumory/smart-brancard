# schemas/mission.py
# Schémas Pydantic des missions (ordres de brancardage)

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from models.enums import Materiel, MethodeVerification, MotifRefus, NiveauUrgence, StatutMission


class MissionCreate(BaseModel):
    """Données attendues pour créer une mission (POST /missions/create)"""
    # Patient déjà admis, choisi grâce à la recherche (GET /patients)
    patient_id: int
    noeud_source_id: int
    noeud_destination_id: int
    niveau_urgence: NiveauUrgence
    materiel_requis: Materiel = Materiel.RIEN
    materiel_deja_dispo: bool = False
    # Consigne de sécurité pour le brancardier (facultative)
    consigne: str | None = Field(default=None, max_length=500)


    @model_validator(mode="after")
    def trajet_different(self):
        # Une mission sans déplacement n'a pas de sens
        if self.noeud_source_id == self.noeud_destination_id:
            raise ValueError("Le départ et l'arrivée doivent être différents")
        return self

class HistoriqueOut(BaseModel):
    """Une ligne du journal d'audit d'une mission"""
    id: int
    statut_modifie_en: StatutMission
    horodatage: datetime
    # Vide (None) quand c'est l'algorithme qui a agi
    auteur_id: int | None
    auteur_nom: str | None
    methode_verification: MethodeVerification
    motif_refus: MotifRefus | None

class MissionOut(BaseModel):
    """Mission renvoyée au frontend, avec les noms utiles à l'affichage"""
    id: int
    statut: StatutMission
    niveau_urgence: NiveauUrgence
    materiel_requis: Materiel
    materiel_deja_dispo: bool
    consigne: str | None
    date_creation: datetime

    patient_id: int
    patient_ipp: str
    patient_nom: str
    patient_prenom: str

    prescripteur_id: int
    brancardier_id: int | None

    noeud_source_id: int
    noeud_source_nom: str
    noeud_destination_id: int
    noeud_destination_nom: str

    # Itinéraire calculé par Dijkstra : id des nœuds traversés, et leurs noms dans le même ordre
    itineraire: list[int]
    itineraire_noms: list[str]
    # Durée estimée du trajet en minutes, calculée à la création (vide pour les missions plus anciennes)
    duree_estimee: float | None

