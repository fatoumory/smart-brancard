# schemas/detection.py
# Schémas Pydantic des détections de balises BLE (position des agents)

from datetime import datetime

from pydantic import BaseModel


class DetectionCreate(BaseModel):
    """Corps de POST /detections : le lieu de la balise qui vient de détecter l'agent"""
    noeud_id: int


class DetectionBadge(BaseModel):
    """Corps de POST /detections/badge : un récepteur de salle a capté le badge d'un agent.
    Dans le prototype, c'est le simulateur de badges qui l'envoie (à la place d'un ESP32)."""
    brancardier_id: int
    noeud_id: int


class DetectionOut(BaseModel):
    """Une détection, avec le nom du lieu pour l'affichage"""
    id: int
    brancardier_id: int
    noeud_id: int
    noeud_nom: str
    date_heure: datetime
