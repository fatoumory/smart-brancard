# tests/test_aretes.py
# Blocage des arêtes par le régulateur et effet sur le calcul d'itinéraire

import pytest

from database import SessionLocal
from services.graphe_service import calculer_itineraire, charger_graphe_json
from tests.conftest import login

URGENCES, BLOC = 1, 11
BRANCARDIER = {"nom_utilisateur": "moussa@test.fr", "prenom": "Moussa", "nom": "Ba",
               "mot_de_passe": "brancard123", "role": "BRANCARDIER"}


@pytest.fixture()
def reg(client):
    """Charge le graphe et renvoie les en-têtes d'authentification du régulateur"""
    db = SessionLocal()
    charger_graphe_json(db)
    db.close()
    return login(client, "reg@test.fr", "motdepasse")


def id_arete(client, headers, noeud_a_id, noeud_b_id):
    """Retrouve l'id de l'arête qui relie deux nœuds"""
    aretes = client.get("/aretes", headers=headers).json()
    return next(a["id"] for a in aretes
                if (a["noeud_a_id"], a["noeud_b_id"]) == (noeud_a_id, noeud_b_id))


def duree(noeud_a_id, noeud_b_id):
    db = SessionLocal()
    try:
        return calculer_itineraire(db, noeud_a_id, noeud_b_id)[1]
    finally:
        db.close()


def test_lister_aretes(client, reg):
    r = client.get("/aretes", headers=reg)
    assert r.status_code == 200
    assert len(r.json()) == 20
    ascenseur_a = next(a for a in r.json() if (a["noeud_a_id"], a["noeud_b_id"]) == (8, 18))
    assert ascenseur_a["noeud_a_nom"] == "Ascenseur A - RDC"
    assert ascenseur_a["noeud_b_nom"] == "Ascenseur A - Étage 1"
    assert ascenseur_a["est_bloque"] is False


def test_bloquer_puis_debloquer_ascenseur(client, reg):
    arete_id = id_arete(client, reg, 8, 18)
    assert duree(URGENCES, BLOC) == pytest.approx(4.0)

    # Panne de l'ascenseur A : détour par l'ascenseur B
    r = client.patch(f"/aretes/{arete_id}", json={"est_bloque": True}, headers=reg)
    assert r.status_code == 200 and r.json()["est_bloque"] is True
    assert duree(URGENCES, BLOC) == pytest.approx(7.0)

    # Seule l'arête bloquée apparaît dans le filtre
    bloquees = client.get("/aretes?est_bloque=true", headers=reg).json()
    assert [a["id"] for a in bloquees] == [arete_id]

    # Réparation : on retrouve le trajet direct
    r = client.patch(f"/aretes/{arete_id}", json={"est_bloque": False}, headers=reg)
    assert r.status_code == 200 and r.json()["est_bloque"] is False
    assert duree(URGENCES, BLOC) == pytest.approx(4.0)


def test_arete_inconnue(client, reg):
    r = client.patch("/aretes/999", json={"est_bloque": True}, headers=reg)
    assert r.status_code == 404


def test_corps_invalide(client, reg):
    arete_id = id_arete(client, reg, 8, 18)
    assert client.patch(f"/aretes/{arete_id}", json={}, headers=reg).status_code == 422
    assert client.patch(f"/aretes/{arete_id}", json={"est_bloque": "peut-être"},
                        headers=reg).status_code == 422


def test_reserve_au_regulateur(client, reg):
    client.post("/auth/register", json=BRANCARDIER, headers=reg)
    br = login(client, "moussa@test.fr", "brancard123")
    arete_id = id_arete(client, reg, 8, 18)

    # Un brancardier ne peut ni voir ni modifier les arêtes
    assert client.get("/aretes", headers=br).status_code == 403
    assert client.patch(f"/aretes/{arete_id}", json={"est_bloque": True}, headers=br).status_code == 403
    # Sans connexion
    assert client.get("/aretes").status_code == 401
    assert client.patch(f"/aretes/{arete_id}", json={"est_bloque": True}).status_code == 401
