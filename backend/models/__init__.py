# models/__init__.py
# Importer tous les modèles ici garantit que Base.metadata les connaît
# (utilisé par Alembic pour générer les migrations, et par les tests)

from models.utilisateur import Utilisateur, Brancardier
from models.patient import Patient
from models.noeud_hopital import NoeudHopital, Arete
from models.mission import Mission
from models.historique import Historique
from models.detection import Detection
from models.journal_assistance import JournalAssistance

__all__ = [
    "Utilisateur", "Brancardier", "Patient", "NoeudHopital", "Arete",
    "Mission", "Historique", "Detection", "JournalAssistance",
]
