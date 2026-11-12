# services/badge_service.py
# Badges BLE des brancardiers (CDC §1.4, §4.5).
#
# Dans un vrai hôpital, chaque agent porte un badge qui émet en Bluetooth basse consommation (BLE),
# et un récepteur fixé dans chaque salle (par exemple un ESP32) prévient le serveur quand il capte
# un badge. Dans le prototype, le simulateur de badges joue ce rôle : il envoie la même information,
# « le badge de tel agent est dans telle salle », toutes les 5 à 10 secondes.
#
# Le serveur n'a donc pas besoin de savoir si la détection vient d'un vrai récepteur ou du
# simulateur : les deux arrivent par POST /detections/badge.

from sqlalchemy.orm import Session

from models.detection import Detection
from models.enums import OrigineDetection
from models.noeud_hopital import NoeudHopital
from models.utilisateur import Brancardier
from services.position_service import enregistrer_detection


class BadgeInconnu(Exception):
    """Aucun brancardier ne porte ce badge (identifiant inconnu)"""


class LieuInconnu(Exception):
    """Aucun récepteur n'est installé dans ce lieu (identifiant de nœud inconnu)"""


def detecter_badge(db: Session, brancardier_id: int, noeud_id: int) -> Detection:
    """Enregistre la détection du badge d'un agent dans un lieu.
    Fait le commit : la position de l'agent est à jour dès le retour."""
    agent = db.get(Brancardier, brancardier_id)
    if agent is None:
        raise BadgeInconnu()
    if db.get(NoeudHopital, noeud_id) is None:
        raise LieuInconnu()

    detection = enregistrer_detection(db, agent.id, noeud_id, OrigineDetection.BADGE)
    db.commit()
    db.refresh(detection)
    return detection
