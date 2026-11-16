# schemas/alerte.py
# Schémas Pydantic des alertes adressées au régulateur

from datetime import datetime

from pydantic import BaseModel

from models.enums import RaisonAppel


class AppelRegulateur(BaseModel):
    """Corps de POST /missions/{id}/appel-regulateur : pourquoi l'agent appelle"""
    raison: RaisonAppel


class AlerteOut(BaseModel):
    """Une alerte, avec ce que le dashboard affiche : qui appelle, pour quelle mission, d'où"""
    id: int
    raison: RaisonAppel
    date_creation: datetime
    mission_id: int
    brancardier_id: int
    brancardier_prenom: str
    brancardier_nom: str
    # Où chercher l'agent : sa dernière position connue au moment de l'appel,
    # sinon le point de départ de la mission (là où l'on scanne le bracelet)
    lieu_nom: str
    traitee: bool
    date_traitement: datetime | None
    traitee_par_id: int | None
