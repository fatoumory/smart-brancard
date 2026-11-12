# models/detection.py
# Détections des balises BLE (simulées) : la position d'un agent est sa dernière détection

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from database import Base
from models.enums import OrigineDetection


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)

    brancardier_id = Column(Integer, ForeignKey("brancardiers.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    noeud_id = Column(Integer, ForeignKey("noeuds_hopital.id", ondelete="CASCADE"), nullable=False)

    date_heure = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc), index=True)

    # D'où vient la détection : seuls un badge ou un scan prouvent que l'agent est dans la salle
    origine = Column(Enum(OrigineDetection, name="origine_detection"), nullable=False,
                     default=OrigineDetection.DECLARATION, server_default=OrigineDetection.DECLARATION.value)
