# models/noeud_hopital.py
# Graphe de l'hôpital : les salles sont des nœuds, les couloirs et ascenseurs sont des arêtes

from sqlalchemy import (Boolean, CheckConstraint, Column, Enum, Float, ForeignKey, Integer,
                        String, UniqueConstraint)
from database import Base
from models.enums import TypeNoeud


class NoeudHopital(Base):
    __tablename__ = "noeuds_hopital"

    id = Column(Integer, primary_key=True, index=True)

    # Nom affiché dans les formulaires et les itinéraires (ex : "Urgences", "Ascenseur A - RDC")
    nom_salle = Column(String, nullable=False)

    # 0 = rez-de-chaussée, 1 = étage 1
    etage = Column(Integer, nullable=False)

    type_noeud = Column(Enum(TypeNoeud, name="type_noeud"), nullable=False)

    # Identifiant du tag NFC mural (vide pour une intersection sans tag)
    uid_tag_nfc = Column(String, unique=True, nullable=True)


class Arete(Base):
    __tablename__ = "aretes"
    __table_args__ = (
        UniqueConstraint("noeud_a_id", "noeud_b_id", name="uq_arete_noeuds"),
        CheckConstraint("noeud_a_id <> noeud_b_id", name="ck_arete_noeuds_distincts"),
        CheckConstraint("poids > 0", name="ck_arete_poids_positif"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Les deux nœuds reliés (arête non orientée : on la parcourt dans les deux sens)
    noeud_a_id = Column(Integer, ForeignKey("noeuds_hopital.id", ondelete="CASCADE"), nullable=False)
    noeud_b_id = Column(Integer, ForeignKey("noeuds_hopital.id", ondelete="CASCADE"), nullable=False)

    # Durée de parcours en minutes (pour un ascenseur : attente moyenne + trajet)
    poids = Column(Float, nullable=False)

    # Ascenseur en panne ou couloir fermé : l'arête est exclue du calcul de Dijkstra
    est_bloque = Column(Boolean, nullable=False, default=False)
