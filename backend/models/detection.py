# models/detection.py
# Détections des balises BLE (simulées) : la position d'un agent est sa dernière détection

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer
from database import Base


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)

    brancardier_id = Column(Integer, ForeignKey("brancardiers.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    noeud_id = Column(Integer, ForeignKey("noeuds_hopital.id", ondelete="CASCADE"), nullable=False)

    date_heure = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc), index=True)
