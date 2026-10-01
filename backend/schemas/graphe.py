# schemas/graphe.py
# Schémas Pydantic du graphe de l'hôpital (arêtes : couloirs et ascenseurs)

from pydantic import BaseModel, ConfigDict
from models.enums import TypeNoeud


class AreteOut(BaseModel):
    """Arête renvoyée au frontend, avec le nom des deux nœuds pour l'affichage"""
    id: int
    noeud_a_id: int
    noeud_a_nom: str
    noeud_b_id: int
    noeud_b_nom: str
    poids: float
    est_bloque: bool


class AreteBlocage(BaseModel):
    """Corps de PATCH /aretes/{id} : true = bloquer (panne, fermeture), false = rouvrir"""
    est_bloque: bool
    

class NoeudOut(BaseModel):
    """Lieu de l'hôpital renvoyé au frontend (listes déroulantes, carte).
    Le tag NFC n'est pas envoyé : il ne doit être connu que du backend, qui vérifie les scans."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom_salle: str
    etage: int
    type_noeud: TypeNoeud 