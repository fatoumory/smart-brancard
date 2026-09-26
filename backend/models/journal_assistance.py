# models/journal_assistance.py
# Trace de chaque commande vocale traitée par l'assistant (Whisper, CDC §5.2)

from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from database import Base


class JournalAssistance(Base):
    __tablename__ = "journaux_assistance"

    id = Column(Integer, primary_key=True, index=True)

    # Utilisateur qui a parlé (médecin ou régulateur)
    emetteur_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=False, index=True)

    chemin_audio = Column(String, nullable=False)
    texte_transcrit = Column(Text, nullable=True)

    # Confiance de l'extraction (0 à 1) : sous 0,75, le formulaire doit être vérifié à la main
    score_confiance = Column(Float, nullable=True)

    # Entités extraites (patient, départ, arrivée, urgence...), au format JSON
    entites_extraites = Column(Text, nullable=True)
