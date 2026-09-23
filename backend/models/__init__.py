# models/__init__.py
# Importer tous les modèles ici garantit que Base.metadata les connaît
# avant l'appel à create_all (sinon leurs tables ne sont pas créées)

from models.utilisateur import Utilisateur
from models.patient import Patient
from models.mission import Mission

__all__ = ["Utilisateur", "Patient", "Mission"]
