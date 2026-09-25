# models/mission.py

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, Text
from database import Base
from models.enums import Materiel, NiveauUrgence, StatutMission


class Mission(Base):
    # Nom de la table dans PostgreSQL
    __tablename__ = "missions"

    # Identifiant unique, généré automatiquement par PostgreSQL
    id = Column(Integer, primary_key=True, index=True)

    # Niveau d'urgence: détermine la priorité dans la file d'attente
    niveau_urgence = Column(Enum(NiveauUrgence, name="niveau_urgence"), nullable=False)

    # Matériel requis, et s'il est déjà sur place (évite un détour par le dépôt)
    materiel_requis = Column(Enum(Materiel, name="materiel"), nullable=False, default=Materiel.RIEN)
    materiel_deja_dispo = Column(Boolean, nullable=False, default=False)

    # Statut de la mission: chaque changement est tracé dans la table historiques
    statut = Column(Enum(StatutMission, name="statut_mission"), nullable=False,
                    default=StatutMission.EN_ATTENTE, index=True)

    # Itinéraire calculé par Dijkstra (liste des nœuds traversés)
    itineraire = Column(Text, nullable=True)

    date_creation = Column(DateTime(timezone=True), nullable=False,
                           default=lambda: datetime.now(timezone.utc))

    # Patient transporté
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)

    # Médecin (ou régulateur) qui a prescrit le transport
    prescripteur_id = Column(Integer, ForeignKey("utilisateurs.id"), nullable=False)

    # Brancardier assigné: vide tant que la mission n'est pas attribuée
    brancardier_id = Column(Integer, ForeignKey("brancardiers.id", ondelete="SET NULL"),
                            nullable=True, index=True)

    # Trajet : nœuds de départ et d'arrivée dans le graphe de l'hôpital
    noeud_source_id = Column(Integer, ForeignKey("noeuds_hopital.id"), nullable=False)
    noeud_destination_id = Column(Integer, ForeignKey("noeuds_hopital.id"), nullable=False)
