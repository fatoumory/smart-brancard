# tests/test_graphe.py
# Vérifie le chargement du graphe et les itinéraires de référence (calculés à la main)

import pytest

from database import Base, SessionLocal, engine
from models.noeud_hopital import Arete, NoeudHopital
from services.graphe_service import (ItineraireIntrouvable, calculer_itineraire,
                                    charger_graphe_json, noms_des_noeuds)

URGENCES, BLOC, REANIMATION = 1, 11, 13


@pytest.fixture()
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    charger_graphe_json(session)
    yield session
    session.close()


def bloquer(db, noeud_a_id, noeud_b_id):
    """Simule une panne : l'arête entre ces deux nœuds devient inutilisable"""
    arete = db.query(Arete).filter_by(noeud_a_id=noeud_a_id, noeud_b_id=noeud_b_id).one()
    arete.est_bloque = True
    db.commit()


def test_chargement_du_json(db):
    assert db.query(NoeudHopital).count() == 20
    assert db.query(Arete).count() == 20
    # Un deuxième chargement ne crée pas de doublons
    assert charger_graphe_json(db) == 0
    assert db.query(NoeudHopital).count() == 20


def test_urgences_reanimation_par_ascenseur_b(db):
    chemin, duree = calculer_itineraire(db, URGENCES, REANIMATION)
    assert duree == pytest.approx(5.0)
    assert chemin == [1, 5, 6, 7, 9, 19, 17, 13]


def test_urgences_bloc_par_ascenseur_a(db):
    chemin, duree = calculer_itineraire(db, URGENCES, BLOC)
    assert duree == pytest.approx(4.0)
    assert chemin == [1, 5, 8, 18, 15, 11]


def test_ascenseur_a_bloque_detour_par_b(db):
    bloquer(db, 8, 18)
    chemin, duree = calculer_itineraire(db, URGENCES, BLOC)
    assert duree == pytest.approx(7.0)
    assert chemin == [1, 5, 6, 7, 9, 19, 17, 16, 15, 11]


def test_les_deux_ascenseurs_bloques(db):
    bloquer(db, 8, 18)
    bloquer(db, 9, 19)
    # Plus aucun passage entre les étages
    with pytest.raises(ItineraireIntrouvable):
        calculer_itineraire(db, URGENCES, REANIMATION)


def test_noeud_inconnu(db):
    with pytest.raises(ItineraireIntrouvable):
        calculer_itineraire(db, URGENCES, 999)


def test_depart_egal_arrivee(db):
    assert calculer_itineraire(db, URGENCES, URGENCES) == ([URGENCES], 0.0)


def test_noms_des_noeuds(db):
    chemin, _ = calculer_itineraire(db, URGENCES, BLOC)
    assert noms_des_noeuds(db, chemin) == [
        "Urgences", "Couloir Ouest - RDC", "Ascenseur A - RDC",
        "Ascenseur A - Étage 1", "Couloir Ouest - Étage 1", "Bloc opératoire",
    ]
