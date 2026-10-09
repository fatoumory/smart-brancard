# services/position_service.py
# Position des brancardiers à partir des balises BLE (simulées, CDC §1.4).
# Une balise est fixée dans un lieu de l'hôpital ; chaque fois qu'elle détecte un agent,
# une ligne Detection est enregistrée. La position d'un agent est sa dernière détection.

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.detection import Detection


def enregistrer_detection(db: Session, brancardier_id: int, noeud_id: int) -> Detection:
    """Enregistre le passage d'un agent près d'une balise (diagramme : enregistrer_ping_ble).
    Ne fait pas de commit : l'appelant enregistre."""
    detection = Detection(brancardier_id=brancardier_id, noeud_id=noeud_id)
    db.add(detection)
    return detection


def positions_actuelles(db: Session, brancardier_ids: list[int] | None = None) -> dict[int, Detection]:
    """Dernière détection de chaque agent : {id du brancardier: Detection}.
    Un agent jamais détecté n'apparaît pas dans le résultat (position inconnue)."""
    # Date de la dernière détection de chaque agent, puis la ligne correspondante (une seule requête)
    derniere = (db.query(Detection.brancardier_id, func.max(Detection.date_heure).label("date_max"))
                .group_by(Detection.brancardier_id))
    if brancardier_ids is not None:
        derniere = derniere.filter(Detection.brancardier_id.in_(brancardier_ids))
    derniere = derniere.subquery()

    lignes = (db.query(Detection)
              .join(derniere, (Detection.brancardier_id == derniere.c.brancardier_id)
                    & (Detection.date_heure == derniere.c.date_max))
              .order_by(Detection.id)
              .all())
    # Deux détections à la même date exacte : la plus récemment enregistrée l'emporte
    return {d.brancardier_id: d for d in lignes}


def position_actuelle(db: Session, brancardier_id: int) -> Detection | None:
    """Dernière détection d'un agent, ou None s'il n'a jamais été détecté"""
    return (db.query(Detection)
            .filter(Detection.brancardier_id == brancardier_id)
            .order_by(Detection.date_heure.desc(), Detection.id.desc())
            .first())
