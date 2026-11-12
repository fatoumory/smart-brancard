# services/position_service.py
# Position des brancardiers à partir des balises BLE (simulées, CDC §1.4).
# Une balise est fixée dans un lieu de l'hôpital ; chaque fois qu'elle détecte un agent,
# une ligne Detection est enregistrée. La position d'un agent est sa dernière détection.

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.detection import Detection
from models.enums import OrigineDetection


# Au-delà de ce délai sans détection (téléphone éteint, hors de portée), la position est
# considérée comme inconnue : l'agent n'est plus classé « proche » sur une position périmée
POSITION_VALIDE = timedelta(minutes=10)

# Pour prouver qu'un agent est DANS une salle, il faut une détection beaucoup plus fraîche :
# le badge est capté toutes les 5 à 10 s, une détection de plus de 2 min ne prouve plus rien
PRESENCE_RECENTE = timedelta(minutes=2)

# Seules ces origines prouvent la présence ; une déclaration de l'agent (« Je suis à ») non
ORIGINES_PROUVANT_LA_PRESENCE = {OrigineDetection.BADGE, OrigineDetection.SCAN}


def en_utc(instant: datetime | None) -> datetime | None:
    """SQLite (tests) renvoie des dates sans fuseau : elles sont en UTC, on le précise"""
    if instant is not None and instant.tzinfo is None:
        return instant.replace(tzinfo=timezone.utc)
    return instant


def est_recente(detection: Detection, instant: datetime | None = None) -> bool:
    """La détection date de moins de 10 minutes"""
    return en_utc(detection.date_heure) >= (instant or datetime.now(timezone.utc)) - POSITION_VALIDE


def prouve_la_presence(detection: Detection | None, noeud_id: int, instant: datetime | None = None) -> bool:
    """La détection prouve que l'agent est en ce moment dans ce lieu :
    même lieu, moins de 2 min, et venue d'un badge ou d'un scan (pas d'une déclaration)"""
    return (detection is not None
            and detection.noeud_id == noeud_id
            and detection.origine in ORIGINES_PROUVANT_LA_PRESENCE
            and en_utc(detection.date_heure) >= (instant or datetime.now(timezone.utc)) - PRESENCE_RECENTE)


def etait_present(db: Session, brancardier_id: int, noeud_id: int, instant: datetime | None = None) -> bool:
    """L'agent était dans ce lieu à cet instant (maintenant par défaut) : sa dernière détection
    à cet instant le prouve. Pour une action faite hors ligne, on regarde où il était quand il
    l'a faite, pas quand le réseau est revenu (il a pu changer de salle entre-temps)."""
    instant = instant or datetime.now(timezone.utc)
    detection = (db.query(Detection)
                 .filter(Detection.brancardier_id == brancardier_id, Detection.date_heure <= instant)
                 .order_by(Detection.date_heure.desc(), Detection.id.desc())
                 .first())
    return prouve_la_presence(detection, noeud_id, instant)


def enregistrer_detection(db: Session, brancardier_id: int, noeud_id: int,
                          origine: OrigineDetection = OrigineDetection.DECLARATION) -> Detection:
    """Enregistre le passage d'un agent près d'une balise (diagramme : enregistrer_ping_ble).
    Ne fait pas de commit : l'appelant enregistre."""
    detection = Detection(brancardier_id=brancardier_id, noeud_id=noeud_id, origine=origine)
    db.add(detection)
    return detection


def positions_actuelles(db: Session, brancardier_ids: list[int] | None = None,
                        recentes_seulement: bool = False) -> dict[int, Detection]:
    """Dernière détection de chaque agent : {id du brancardier: Detection}.
    Un agent jamais détecté n'apparaît pas dans le résultat (position inconnue).
    recentes_seulement : une dernière détection de plus de 10 min compte comme inconnue."""
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
    positions = {d.brancardier_id: d for d in lignes}
    if recentes_seulement:
        instant = datetime.now(timezone.utc)
        positions = {i: d for i, d in positions.items() if est_recente(d, instant)}
    return positions


def position_actuelle(db: Session, brancardier_id: int) -> Detection | None:
    """Dernière détection d'un agent, ou None s'il n'a jamais été détecté"""
    return (db.query(Detection)
            .filter(Detection.brancardier_id == brancardier_id)
            .order_by(Detection.date_heure.desc(), Detection.id.desc())
            .first())
