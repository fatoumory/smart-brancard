# services/graphe_service.py
# Graphe de l'hôpital : chargement du fichier JSON en base,
# construction du graphe NetworkX et calcul d'itinéraire avec Dijkstra

import json
from pathlib import Path

import networkx as nx
from sqlalchemy import text
from sqlalchemy.orm import Session

from models.enums import TypeNoeud
from models.noeud_hopital import Arete, NoeudHopital

# Plan de l'hôpital : 20 nœuds sur 2 étages (voir data/graphe_hopital.json)
CHEMIN_GRAPHE = Path(__file__).resolve().parents[1] / "data" / "graphe_hopital.json"


class ItineraireIntrouvable(Exception):
    """Aucun chemin entre deux nœuds (nœud inconnu, ou toutes les arêtes utiles sont bloquées)"""


#  Chargement du fichier JSON dans la base

def charger_graphe_json(db: Session, chemin: Path = CHEMIN_GRAPHE) -> int:
    """Insère les nœuds et les arêtes du fichier JSON dans la base.
    Ne fait rien si des nœuds existent déjà. Retourne le nombre de nœuds créés."""
    if db.query(NoeudHopital).first():
        return 0

    donnees = json.loads(chemin.read_text(encoding="utf-8"))

    # Les éléments sans "id" (ou sans "noeud_a_id") sont des commentaires : on les ignore
    noeuds = [n for n in donnees["noeuds"] if "id" in n]
    aretes = [a for a in donnees["aretes"] if "noeud_a_id" in a]

    for n in noeuds:
        db.add(NoeudHopital(
            id=n["id"],
            nom_salle=n["nom_salle"],
            etage=n["etage"],
            type_noeud=TypeNoeud(n["type_noeud"]),
            uid_tag_nfc=n["uid_tag_nfc"],
        ))
    # Envoie les nœuds à la base avant les arêtes, qui pointent vers eux
    db.flush()

    for a in aretes:
        db.add(Arete(
            noeud_a_id=a["noeud_a_id"],
            noeud_b_id=a["noeud_b_id"],
            poids=a["poids"],
            est_bloque=a["est_bloque"],
        ))

    # Les id des nœuds ont été donnés à la main : sous PostgreSQL, on recale le compteur
    # automatique, sinon le prochain nœud créé par l'API reprendrait l'id 1 (déjà pris)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text(
            "SELECT setval(pg_get_serial_sequence('noeuds_hopital', 'id'), "
            "(SELECT MAX(id) FROM noeuds_hopital))"
        ))

    db.commit()
    return len(noeuds)


#  Construction du graphe et calcul de l'itinéraire

def construire_graphe(db: Session) -> nx.Graph:
    """Construit le graphe NetworkX à partir des arêtes de la base.
    Les arêtes bloquées (ascenseur en panne, couloir fermé) ne sont pas ajoutées."""
    # nx.Graph est non orienté : chaque couloir se parcourt dans les deux sens
    graphe = nx.Graph()
    for arete in db.query(Arete).filter(Arete.est_bloque.is_(False)):
        graphe.add_edge(arete.noeud_a_id, arete.noeud_b_id, weight=arete.poids)
    return graphe


def calculer_itineraire(db: Session, source_id: int, destination_id: int) -> tuple[list[int], float]:
    """Plus court chemin (Dijkstra) entre deux nœuds.
    Retourne (liste des id des nœuds traversés, durée totale en minutes)."""
    if source_id == destination_id:
        return [source_id], 0.0

    graphe = construire_graphe(db)
    try:
        duree, chemin = nx.single_source_dijkstra(graphe, source_id, destination_id, weight="weight")
    except (nx.NodeNotFound, nx.NetworkXNoPath):
        raise ItineraireIntrouvable(
            f"Aucun itinéraire entre les nœuds {source_id} et {destination_id}"
        ) from None
    return chemin, duree


def noms_des_noeuds(db: Session, chemin: list[int]) -> list[str]:
    """Traduit une liste d'id en noms de salles, dans le même ordre (pour l'affichage)"""
    noms = dict(
        db.query(NoeudHopital.id, NoeudHopital.nom_salle)
        .filter(NoeudHopital.id.in_(chemin))
        .all()
    )
    return [noms[i] for i in chemin]
