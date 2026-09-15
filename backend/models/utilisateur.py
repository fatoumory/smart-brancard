# models/utilisateur.py

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from database import Base

class Utilisateur(Base):
    # Nom de la table dans PostgreSQL
    __tablename__ = "utilisateurs"

    # Identifiant unique, généré automatiquement par PostgreSQL
    id = Column(Integer, primary_key=True, index=True)

    # Informations personnelles
    nom = Column(String, nullable=False)
    prenom = Column(String, nullable=False)

    # Email unique: sert d'identifiant de connexion
    email = Column(String, unique=True, nullable=False, index=True)

    # Mot de passe hashé:  on ne stocke JAMAIS le mot de passe en clair
    mot_de_passe_hash = Column(String, nullable=False)

    # Rôle: détermine les permissions dans le système (RBAC)
    # Valeurs possibles : "brancardier" / "medecin" / "regulateur"
    role = Column(String, nullable=False)

    # Statut opérationnel: utilisé principalement pour les brancardiers
    # Valeurs possibles : "disponible" / "en_mission" / "pause" / "indisponible"
    # Pour médecin et régulateur ce champ sera ignoré par l'algorithme
    statut = Column(String, default="disponible")

    # Date de création du compte: horodatage automatique
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))