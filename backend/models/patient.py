# models/patient.py

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from database import Base

class Patient(Base):
    # Nom de la table dans PostgreSQL
    __tablename__ = "patients"

    # Identifiant unique : généré automatiquement par PostgreSQL
    id = Column(Integer, primary_key=True, index=True)

    # Nom anonymisé, on ne stocke jamais le vrai nom en clair
    # pour respecter le secret médical (section 7.2 du cahier des charges)
    nom_anonymise = Column(String, nullable=False)

    # Code unique du bracelet QR, sert à identifier le patient
    # lors des scans de validation 