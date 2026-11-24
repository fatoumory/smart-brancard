# services/saturation_service.py
# Alerte « Saturation flotte » pour le régulateur (CDC §5.4).
#
# La flotte est saturée quand les missions s'accumulent sans agent : au moins SEUIL_SATURATION
# missions en attente, et plus de missions en attente que d'agents disponibles pour les prendre.
# Le régulateur peut alors rappeler des agents en pause, en appeler d'autres, ou reporter les
# transports les moins urgents. Les missions qui ont déjà dépassé leur délai garanti sont comptées
# à part : ce sont elles qu'il faut regarder en premier.

import os
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from models.enums import NiveauUrgence, StatutAgent
from models.utilisateur import Brancardier
from services.assignation_service import echeance, missions_en_attente

# Nombre de missions en attente à partir duquel on parle de saturation (réglable dans le .env)
SEUIL_SATURATION = int(os.getenv("SEUIL_SATURATION", "3"))


def etat_de_la_flotte(db: Session, instant: datetime | None = None) -> dict:
    """État de la file et de la flotte, et décision « saturée » ou non"""
    instant = instant or datetime.now(timezone.utc)
    file = missions_en_attente(db)
    libres = (db.query(Brancardier.reserve_urgent)
              .filter(Brancardier.est_actif.is_(True), Brancardier.statut == StatutAgent.DISPONIBLE)
              .all())
    disponibles = len(libres)
    reserves = sum(1 for (reserve,) in libres if reserve)
    urgentes = sum(1 for m in file if m.niveau_urgence == NiveauUrgence.URGENT)
    # Un agent réservé aux URGENT ne peut prendre que les URGENT en attente : il ne compte pas
    # pour les autres missions (sinon 3 missions BASSE et 3 agents réservés libres ne seraient
    # pas signalées, alors qu'aucune ne peut partir)
    utilisables = (disponibles - reserves) + min(reserves, urgentes)
    en_retard = sum(1 for m in file if echeance(m) <= instant)
    return {
        "sature": len(file) >= SEUIL_SATURATION and len(file) > utilisables,
        "missions_en_attente": len(file),
        "missions_en_retard": en_retard,
        "agents_disponibles": disponibles,
        # Parmi les agents disponibles, ceux qui ne prennent que les URGENT
        "agents_reserves_urgent": reserves,
        "seuil": SEUIL_SATURATION,
        # Ordre dans lequel les missions seront servies (vieillissement compris)
        "file": [m.id for m in file],
    }
