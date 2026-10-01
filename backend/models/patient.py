# models/patient.py

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Enum, Integer, String, func
from models.enums import Sexe, StatutIdentite
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
    
    # Traits d'identité complémentaires : ils servent à distinguer les homonymes
    # Date de naissance vide si inconnue (patient inconscient)
    date_naissance = Column(Date, nullable=True)
    sexe = Column(Enum(Sexe, name="sexe"), nullable=False,
                default=Sexe.INDETERMINE, server_default=Sexe.INDETERMINE.value)

    # PROVISOIRE tant que l'identité réelle n'est pas confirmée
    statut_identite = Column(Enum(StatutIdentite, name="statut_identite"), nullable=False,
                            default=StatutIdentite.VALIDEE,
                            server_default=StatutIdentite.VALIDEE.value)

    # Code du bracelet QR, scanné pour valider l'identité (identitovigilance, CDC §5.5)
    code_bracelet = Column(String, unique=True, nullable=False, index=True)

        # Date et heure de l'admission (remplie automatiquement)
    date_admission = Column(DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc),
                            server_default=func.now())