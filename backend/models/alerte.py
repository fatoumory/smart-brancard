# models/alerte.py
# Alertes adressées au régulateur. Aujourd'hui : l'appel d'un agent bloqué pendant une mission
# (bracelet illisible, scans refusés). Une alerte n'est pas un changement de statut de la mission :
# elle n'a pas sa place dans le journal d'audit, mais elle garde qui a appelé, quand, et qui l'a traitée.

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer
from database import Base
from models.enums import RaisonAppel


class Alerte(Base):
    __tablename__ = "alertes"

    id = Column(Integer, primary_key=True, index=True)

    # La mission en cours au moment de l'appel, et l'agent qui appelle
    mission_id = Column(Integer, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True)
    brancardier_id = Column(Integer, ForeignKey("brancardiers.id"), nullable=False)

    raison = Column(Enum(RaisonAppel, name="raison_appel"), nullable=False)

    date_creation = Column(DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    # Traitée par le régulateur : qui, et quand
    traitee = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    date_traitement = Column(DateTime(timezone=True), nullable=True)
    traitee_par_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)
