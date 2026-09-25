# models/patient.py

from sqlalchemy import Column, Integer, String
from database import Base


class Patient(Base):
    # Nom de la table dans PostgreSQL
    __tablename__ = "patients"

    # Identifiant unique : généré automatiquement par PostgreSQL
    id = Column(Integer, primary_key=True, index=True)

    # IPP : identifiant permanent du patient dans l'hôpital
    id_hospitalisation = Column(String, unique=True, nullable=False, index=True)

    # Identité affichée au brancardier (CDC §7.2) : aucune donnée clinique n'est stockée
    prenom = Column(String, nullable=False)
    nom = Column(String, nullable=False)

    # Code du bracelet QR, scanné pour valider l'identité (identitovigilance, CDC §5.5)
    code_bracelet = Column(String, unique=True, nullable=False, index=True)
