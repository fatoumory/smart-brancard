# models/historique.py
# Journal des changements de statut des missions (auditabilité, CDC §7.3)

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from database import Base
from models.enums import MethodeVerification, MotifRefus, StatutMission


class Historique(Base):
    __tablename__ = "historiques"

    id = Column(Integer, primary_key=True, index=True)

    mission_id = Column(Integer, ForeignKey("missions.id", ondelete="CASCADE"),
                        nullable=False, index=True)

    # Auteur de l'action : vide si c'est l'algorithme d'assignation
    auteur_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=True)

    # Agent concerné : celui à qui la mission est proposée, qui accepte, refuse, ne répond pas,
    # scanne... Vide à la création. Permet d'exclure d'une mission les agents qui l'ont refusée
    # ou laissée sans réponse, et de retrouver toutes les propositions (CDC §7.3)
    brancardier_id = Column(Integer, ForeignKey("brancardiers.id"), nullable=True, index=True)

    statut_modifie_en = Column(Enum(StatutMission, name="statut_mission"), nullable=False)

    horodatage = Column(DateTime(timezone=True), nullable=False,
                        default=lambda: datetime.now(timezone.utc))

    # Comment le changement a été validé (saisie, scan QR, badge NFC, voix, forçage en urgence)
    methode_verification = Column(Enum(MethodeVerification, name="methode_verification"),
                                  nullable=False, default=MethodeVerification.MANUEL)

    # Renseigné uniquement quand un brancardier refuse la mission
    motif_refus = Column(Enum(MotifRefus, name="motif_refus"), nullable=True)
