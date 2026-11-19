# tests/test_securite.py
# Vérification systématique du contrôle d'accès (Sprint 5, CDC §7.1).
#
# La matrice ACCES donne, pour chaque route de l'API, qui a le droit de l'appeler.
# Les tests vérifient :
#   1. que la matrice couvre toutes les routes : une route ajoutée sans être déclarée ici fait échouer
#      les tests (impossible d'oublier sa protection) ;
#   2. qu'un rôle non autorisé reçoit 403, pour chaque route et chaque rôle ;
#   3. que sans jeton, avec un jeton invalide ou avec un compte désactivé, on reçoit 401 ;
#   4. qu'un médecin ne voit pas les missions d'un autre médecin (404 : on ne révèle pas qu'elles existent).

import pytest

from database import SessionLocal
from main import app
from models.enums import Role
from models.utilisateur import Utilisateur
from services.auth_service import hash_password
from tests.conftest import login

REG, MED, BRA, ADM = Role.REGULATEUR, Role.MEDECIN, Role.BRANCARDIER, Role.ADMIN
TOUS_LES_ROLES = [REG, MED, BRA, ADM]
PUBLIC = "public"          # sans connexion (pages de connexion)
CONNECTE = "connecte"      # tout utilisateur connecté, quel que soit son rôle

# (méthode, chemin) -> rôles autorisés
ACCES = {
    # « L'API est en ligne » : aucune donnée
    ("GET", "/"): PUBLIC,
    # Authentification
    ("POST", "/auth/login"): PUBLIC,
    ("POST", "/auth/carte"): PUBLIC,
    ("GET", "/auth/me"): CONNECTE,
    ("POST", "/auth/register"): {REG},
    # Comptes et statut de l'agent
    ("GET", "/utilisateurs"): {REG},
    ("PATCH", "/utilisateurs/{utilisateur_id}"): {REG},
    ("POST", "/utilisateurs/{utilisateur_id}/carte"): {REG},
    ("PATCH", "/utilisateurs/{utilisateur_id}/affectation"): {REG},
    ("PATCH", "/utilisateurs/me/statut"): {BRA},
    # Plan de l'hôpital
    ("GET", "/noeuds"): CONNECTE,
    ("GET", "/aretes"): {REG},
    ("PATCH", "/aretes/{arete_id}"): {REG},
    # Patients
    ("POST", "/patients"): {MED},
    ("GET", "/patients"): {MED},
    ("PATCH", "/patients/{patient_id}"): {MED},
    # Positions et badges
    ("POST", "/detections"): {BRA},
    ("GET", "/detections/me"): {BRA},
    ("POST", "/detections/badge"): {REG, ADM},
    # Missions : médecin
    ("POST", "/missions/create"): {MED},
    # Missions : lecture
    ("GET", "/missions"): {REG, MED},
    ("GET", "/missions/{mission_id}"): {REG, MED},
    ("GET", "/missions/{mission_id}/historique"): {REG, MED},
    ("GET", "/missions/saturation"): {REG},
    # Missions : brancardier
    ("GET", "/missions/moi"): {BRA},
    ("GET", "/missions/moi/journal"): {BRA},
    ("PUT", "/missions/{mission_id}/accept"): {BRA},
    ("PUT", "/missions/{mission_id}/refuse"): {BRA},
    ("POST", "/missions/{mission_id}/scan-depart"): {BRA},
    ("POST", "/missions/{mission_id}/scan-arrivee"): {BRA},
    ("POST", "/missions/{mission_id}/arrivee"): {BRA},
    ("POST", "/missions/{mission_id}/appel-regulateur"): {BRA},
    # Missions : régulateur
    ("PUT", "/missions/{mission_id}/reaffecter"): {REG},
    ("PUT", "/missions/{mission_id}/annuler"): {REG},
    ("PUT", "/missions/{mission_id}/cloturer"): {REG},
    # Alertes
    ("GET", "/alertes"): {REG},
    ("PUT", "/alertes/{alerte_id}/traiter"): {REG},
}

PROTEGEES = [route for route, roles in ACCES.items() if roles != PUBLIC]


def chemin_reel(chemin: str) -> str:
    """/missions/{mission_id}/accept -> /missions/1/accept"""
    return "/".join("1" if p.startswith("{") else p for p in chemin.split("/"))


def appeler(client, methode, chemin, headers=None):
    # Corps vide : le contrôle d'accès doit répondre avant toute validation des données
    corps = {"json": {}} if methode in ("POST", "PUT", "PATCH") else {}
    return client.request(methode, chemin_reel(chemin), headers=headers or {}, **corps)


@pytest.fixture()
def jetons(client):
    """Un jeton par rôle (le compte ADMIN est créé directement : aucune route ne le crée)"""
    reg = login(client, "reg@test.fr", "motdepasse")
    for nom, role in (("med@test.fr", "MEDECIN"), ("bra@test.fr", "BRANCARDIER")):
        r = client.post("/auth/register", headers=reg, json={
            "nom_utilisateur": nom, "prenom": "Test", "nom": role.title(),
            "mot_de_passe": "motdepasse", "role": role})
        assert r.status_code == 201, r.text
    db = SessionLocal()
    db.add(Utilisateur(nom="Admin", prenom="Test", nom_utilisateur="adm@test.fr",
                       mot_de_passe_hash=hash_password("motdepasse"), role=Role.ADMIN))
    db.commit()
    db.close()
    return {
        REG: reg,
        MED: login(client, "med@test.fr", "motdepasse"),
        BRA: login(client, "bra@test.fr", "motdepasse"),
        ADM: login(client, "adm@test.fr", "motdepasse"),
    }


def test_la_matrice_couvre_toutes_les_routes():
    # Liste lue dans le schéma OpenAPI (celui de /docs) : il contient toutes les routes HTTP,
    # y compris celles des routeurs inclus (le WebSocket /ws a sa propre vérification, test_temps_reel.py)
    routes = {(methode.upper(), chemin)
              for chemin, operations in app.openapi()["paths"].items()
              for methode in operations}
    oubliees = routes - set(ACCES)
    disparues = set(ACCES) - routes
    assert not oubliees, f"Routes absentes de la matrice de sécurité : {sorted(oubliees)}"
    assert not disparues, f"Routes de la matrice qui n'existent plus : {sorted(disparues)}"


# Une vérification par rôle (et non par route) : la base n'est créée qu'une fois par rôle,
# et un échec liste toutes les routes fautives d'un coup
@pytest.mark.parametrize("role", TOUS_LES_ROLES, ids=lambda r: r.value)
def test_role_non_autorise_recoit_403(client, jetons, role):
    fautes = []
    for (methode, chemin), roles in ACCES.items():
        if roles in (PUBLIC, CONNECTE) or role in roles:
            continue
        r = appeler(client, methode, chemin, jetons[role])
        if r.status_code != 403:
            fautes.append(f"{methode} {chemin} -> {r.status_code}")
    assert not fautes, f"{role.value} n'est pas refusé sur : {fautes}"


@pytest.mark.parametrize("entetes", [
    {},                                                                      # sans jeton
    {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature-fausse"},  # jeton falsifié
    {"Authorization": "Basic cmVnQHRlc3QuZnI6bW90ZGVwYXNzZQ=="},            # pas un jeton Bearer
], ids=["sans_jeton", "jeton_falsifie", "pas_bearer"])
def test_sans_jeton_valide_401(client, entetes):
    fautes = [f"{m} {c} -> {code}" for m, c in PROTEGEES
              if (code := appeler(client, m, c, entetes).status_code) != 401]
    assert not fautes, f"Accès sans jeton valide : {fautes}"


def test_compte_desactive_401_partout(client, jetons):
    """Un compte désactivé perd l'accès tout de suite, même avec un jeton encore valide"""
    medecin = client.get("/auth/me", headers=jetons[MED]).json()
    r = client.patch(f"/utilisateurs/{medecin['id']}", headers=jetons[REG], json={"est_actif": False})
    assert r.status_code == 200, r.text
    for methode, chemin in PROTEGEES:
        assert appeler(client, methode, chemin, jetons[MED]).status_code == 401, f"{methode} {chemin}"


def test_un_medecin_ne_voit_pas_les_missions_d_un_autre(client, jetons):
    from models.patient import Patient
    from services.graphe_service import charger_graphe_json
    db = SessionLocal()
    charger_graphe_json(db)
    db.add(Patient(id=1, id_hospitalisation="00000001", prenom="Jean", nom="Dupont", code_bracelet="QR-00000001"))
    db.commit()
    db.close()
    r = client.post("/missions/create", headers=jetons[MED], json={
        "patient_id": 1, "noeud_source_id": 1, "noeud_destination_id": 13, "niveau_urgence": "BASSE"})
    assert r.status_code == 201, r.text
    mission_id = r.json()["id"]

    client.post("/auth/register", headers=jetons[REG], json={
        "nom_utilisateur": "autre@test.fr", "prenom": "Autre", "nom": "Medecin",
        "mot_de_passe": "motdepasse", "role": "MEDECIN"})
    autre = login(client, "autre@test.fr", "motdepasse")

    # 404 et non 403 : l'autre médecin ne doit même pas savoir que la mission existe
    assert client.get(f"/missions/{mission_id}", headers=autre).status_code == 404
    assert client.get(f"/missions/{mission_id}/historique", headers=autre).status_code == 404
    assert client.get("/missions", headers=autre).json() == []
    # Le régulateur, lui, la voit
    assert client.get(f"/missions/{mission_id}", headers=jetons[REG]).status_code == 200
