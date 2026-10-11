# models/utilisateur.py

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, String, case
from database import Base
from models.enums import Role, StatutAgent


class Utilisateur(Base):
    # Nom de la table dans PostgreSQL
    __tablename__ = "utilisateurs"

    # Identifiant unique, généré automatiquement par PostgreSQL
    id = Column(Integer, primary_key=True, index=True)

    # Identifiant de connexion (unique) : les comptes utilisent leur email professionnel
    nom_utilisateur = Column(String, unique=True, nullable=False, index=True)

    # Mot de passe hashé: on ne stocke JAMAIS le mot de passe en clair
    mot_de_passe_hash = Column(String, nullable=False)

    # Informations personnelles
    prenom = Column(String, nullable=False)
    nom = Column(String, nullable=False)

    # Rôle: détermine les permissions dans le système (RBAC)
    role = Column(Enum(Role, name="role"), nullable=False)

    # Un compte désactivé ne peut plus se connecter (on ne supprime pas, pour l'auditabilité)
    est_actif = Column(Boolean, nullable=False, default=True)

    # Héritage : un utilisateur de rôle BRANCARDIER est chargé comme un Brancardier,
    # dont les attributs propres sont dans la table "brancardiers"
    __mapper_args__ = {
        "polymorphic_on": case((role == Role.BRANCARDIER, "brancardier"), else_="utilisateur"),
        "polymorphic_identity": "utilisateur",
    }


class Brancardier(Utilisateur):
    __tablename__ = "brancardiers"

    # Même identifiant que la ligne de la table utilisateurs
    id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="CASCADE"), primary_key=True)

    # Statut opérationnel, utilisé par l'algorithme d'assignation
    statut = Column(Enum(StatutAgent, name="statut_agent"), nullable=False,
                    default=StatutAgent.DISPONIBLE)

    # Nombre de missions effectuées dans la journée (équité de charge), remis à zéro chaque matin
    compteur_mission = Column(Integer, nullable=False, default=0)
    # Jour auquel le compteur se rapporte : un autre jour, il repart de zéro
    # (voir services/assignation_service.py, compteur_du_jour)
    date_compteur = Column(Date, nullable=True)

    # Fin prévue de la pause en cours (vide hors pause). À cette heure, le serveur remet l'agent
    # DISPONIBLE de lui-même, même si son téléphone est éteint (gerer_reprise_service_auto)
    fin_pause = Column(DateTime(timezone=True), nullable=True)

    __mapper_args__ = {"polymorphic_identity": "brancardier"}
