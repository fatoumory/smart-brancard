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

class RefusMission(BaseModel):
    """Corps de PUT /missions/{id}/refuse : le motif est obligatoire (CDC §7.3)"""
    motif: MotifRefus


class ScanDepart(BaseModel):
    """Corps de POST /missions/{id}/scan-depart : tag NFC de la salle puis QR du bracelet.
    forcer_urgence=true : prise en charge sans scan, réservée aux missions URGENT (tracée)."""
    tag_nfc: str | None = Field(default=None, max_length=100)
    code_bracelet: str | None = Field(default=None, max_length=100)
    forcer_urgence: bool = False


class ScanArrivee(BaseModel):
    """Corps de POST /missions/{id}/scan-arrivee : tag NFC de la salle de destination"""
    tag_nfc: str = Field(min_length=1, max_length=100)


class Reaffectation(BaseModel):
    """Corps de PUT /missions/{id}/reaffecter : le brancardier choisi par le régulateur"""
    brancardier_id: int


class HistoriqueOut(BaseModel):
    """Une ligne du journal d'audit d'une mission"""
    id: int
    statut_modifie_en: StatutMission
    horodatage: datetime
    # Vide (None) quand c'est l'algorithme qui a agi
    auteur_id: int | None
    auteur_nom: str | None
    # Brancardier concerné (proposé, qui accepte, refuse, ne répond pas, scanne...)
    brancardier_id: int | None = None
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
    # Agent de la mission : identité et dernière position connue (balise)
    brancardier_nom: str | None = None
    brancardier_prenom: str | None = None
    brancardier_position_id: int | None = None
    brancardier_position_nom: str | None = None
    # True : agent choisi par l'algorithme (badge « Auto ») ; False : choisi par le régulateur
    assignation_auto: bool | None = None
    # Agent en approche (PROPOSE ou ACCEPTE) : temps de trajet jusqu'au point de départ, en minutes,
    # et heure d'arrivée estimée (maquette du suivi médecin : « Arrivée estimée au point de départ »)
    temps_agent_min: float | None = None
    arrivee_estimee: datetime | None = None

    noeud_source_id: int
    noeud_source_nom: str
    noeud_destination_id: int
    noeud_destination_nom: str

    # Itinéraire calculé par Dijkstra : id des nœuds traversés, et leurs noms dans le même ordre
    itineraire: list[int]
    itineraire_noms: list[str]
    # Durée estimée du trajet en minutes, calculée à la création (vide pour les missions plus anciennes)
    duree_estimee: float | None
    # Mission PROPOSE : heure limite de réponse de l'agent (compte à rebours du téléphone)
    fin_reponse: datetime | None = None

    # Délai garanti de prise en charge (3, 8, 15 ou 30 min selon l'urgence) et heure limite
    delai_garanti_min: int
    limite_prise_en_charge: datetime
    # Horodatages lus dans le journal : prise en charge (scan de départ) et clôture (fin ou annulation)
    date_prise_en_charge: datetime | None = None
    date_fin: datetime | None = None
    # Délai respecté ? Connu à la prise en charge (ou False dès qu'il est dépassé) ; vide sinon
    dans_les_delais: bool | None = None
    # Refusée pour matériel défectueux : n'est plus proposée automatiquement, le régulateur décide
    alerte_materiel: bool = False

