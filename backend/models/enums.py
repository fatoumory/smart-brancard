# models/enums.py
# Énumérations du diagramme de classes, partagées par les modèles SQL et les schémas Pydantic.
# La valeur de chaque membre est son nom : c'est elle qui transite en JSON vers le frontend.

from enum import Enum


class Role(str, Enum):
    REGULATEUR = "REGULATEUR"
    MEDECIN = "MEDECIN"
    BRANCARDIER = "BRANCARDIER"
    ADMIN = "ADMIN"


class StatutAgent(str, Enum):
    DISPONIBLE = "DISPONIBLE"
    EN_MISSION = "EN_MISSION"
    EN_PAUSE = "EN_PAUSE"
    INDISPONIBLE = "INDISPONIBLE"


class StatutMission(str, Enum):
    EN_ATTENTE = "EN_ATTENTE"
    PROPOSE = "PROPOSE"
    # Le brancardier a accepté la mission et rejoint le patient (avant le scan de départ)
    ACCEPTE = "ACCEPTE"
    EN_TRANSIT = "EN_TRANSIT"
    TERMINE = "TERMINE"
    ANNULE = "ANNULE"


class NiveauUrgence(str, Enum):
    BASSE = "BASSE"
    MOYENNE = "MOYENNE"
    HAUTE = "HAUTE"
    URGENT = "URGENT"


# Délai garanti de prise en charge selon l'urgence, en minutes (feuille de route, Sprint 5 ;
# maquette : « Délai SLA garanti »). Même valeurs que frontend/src/services/referentiel.js
DELAI_GARANTI_MIN = {
    NiveauUrgence.URGENT: 3,
    NiveauUrgence.HAUTE: 8,
    NiveauUrgence.MOYENNE: 15,
    NiveauUrgence.BASSE: 30,
}


class Materiel(str, Enum):
    RIEN = "RIEN"
    CHAISE_ROULANTE = "CHAISE_ROULANTE"
    LIT_MEDICAL = "LIT_MEDICAL"
    OXYGENE = "OXYGENE"


class MethodeVerification(str, Enum):
    MANUEL = "MANUEL"
    SCAN_CODE_QR = "SCAN_CODE_QR"
    BADGE_NFC = "BADGE_NFC"
    COMMANDE_VOCALE = "COMMANDE_VOCALE"
    FORCE_URGENCE = "FORCE_URGENCE"


class MotifRefus(str, Enum):
    MATERIEL_DEFECTUEUX = "MATERIEL_DEFECTUEUX"
    INDISPONIBILITE_PHYSIQUE = "INDISPONIBILITE_PHYSIQUE"
    URGENCE_PRIORITAIRE = "URGENCE_PRIORITAIRE"
    FIN_SERVICE = "FIN_SERVICE"

class Sexe(str, Enum):
    MASCULIN = "MASCULIN"
    FEMININ = "FEMININ"
    INDETERMINE = "INDETERMINE"


class StatutIdentite(str, Enum):
    # PROVISOIRE : patient admis sans identité connue (ex : inconscient), à compléter plus tard
    PROVISOIRE = "PROVISOIRE"
    VALIDEE = "VALIDEE"


class TypeNoeud(str, Enum):
    SERVICE = "SERVICE"
    COULOIR = "COULOIR"
    ASCENSEUR = "ASCENSEUR"
    DEPOT_MATERIEL = "DEPOT_MATERIEL"
