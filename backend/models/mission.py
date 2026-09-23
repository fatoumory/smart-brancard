# models/mission.py

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime, timezone
from database import Base

class Mission(Base):
    # Nom de la table dans PostgreSQL
    __tablename__ = "missions"

    # Identifiant unique, généré automatiquement par PostgreSQL
    id = Column(Integer, primary_key=True, index=True)

    # Clé étrangère vers la table patients
    # ondelete="SET NULL": si le patient est supprimé, la mission reste
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"), 
                        nullable=True)

    # Clé étrangère vers la table utilisateurs (le brancardier assigné)
    # nullable=True: au moment de la création, aucun brancardier n'est encore assigné
    brancardier_id = Column(Integer, ForeignKey("utilisateurs.id", ondelete="SET NULL"), 
                            nullable=True)

    # Trajet de la mission
    service_depart = Column(String, nullable=False)
    service_arrivee = Column(String, nullable=False)

    # Niveau d'urgence: détermine la priorité dans la file d'attente
    # Valeurs possibles : "basse" / "moyenne" / "haute" / "urgente"
    niveau_urgence = Column(String, nullable=False)

    # Matériel requis pour le transport
    # Valeurs possibles : "lit_medicalise" / "fauteuil_roulant" / "support_oxygene"
    materiel_requis = Column(String, nullable=True)

    # Statut de la mission: évolue tout au long du cycle de vie (SS2 → SS6)
    # Valeurs : "en_attente" / "proposee" / "en_cours" / 
    #           "en_transit" / "terminee" / "en_file_attente"
    statut = Column(String, default="en_attente")

    # Motif de refus: renseigné uniquement si le brancardier refuse (SS4)
    # Valeurs : "materiel_defectueux" / "urgence_vitale" / "autre"
    motif_refus = Column(String, nullable=True)

    # Horodatages: traçabilité complète pour l'auditabilité (section 7.3)
    created_at = Column(DateTime(timezone=True), 
                        default=lambda: datetime.now(timezone.utc))
    
    # Horodatage du scan NFC départ (SS6, Partie A)
    timestamp_depart = Column(DateTime(timezone=True), nullable=True)
    
    # Horodatage du scan NFC arrivée (SS6, Partie B)
    timestamp_arrivee = Column(DateTime(timezone=True), nullable=True)