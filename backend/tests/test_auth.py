# tests/test_auth.py

from tests.conftest import login

BRANCARDIER = {"nom_utilisateur": "moussa@test.fr", "prenom": "Moussa", "nom": "Ba",
               "mot_de_passe": "brancard123", "role": "BRANCARDIER"}


def test_tables_du_diagramme():
    from database import Base
    assert {"utilisateurs", "brancardiers", "patients", "noeuds_hopital", "aretes", "missions",
            "historiques", "detections", "journaux_assistance"} == set(Base.metadata.tables)


def test_login_ok_et_me(client):
    headers = login(client, "reg@test.fr", "motdepasse")
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "REGULATEUR"
    assert r.json()["est_actif"] is True
    assert r.json()["statut"] is None  # pas un brancardier
    assert "mot_de_passe_hash" not in r.json()


def test_login_insensible_a_la_casse(client):
    login(client, "  REG@test.fr ", "motdepasse")


def test_login_mauvais_mot_de_passe(client):
    r = client.post("/auth/login", data={"username": "reg@test.fr", "password": "faux"})
    assert r.status_code == 401


def test_me_sans_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer abc"}).status_code == 401


def test_register_brancardier(client):
    headers = login(client, "reg@test.fr", "motdepasse")
    r = client.post("/auth/register", json=BRANCARDIER, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["statut"] == "DISPONIBLE"
    assert r.json()["compteur_mission"] == 0
    # doublon
    assert client.post("/auth/register", json=BRANCARDIER, headers=headers).status_code == 400
    # le nouveau compte peut se connecter et est chargé comme un Brancardier
    br = login(client, "moussa@test.fr", "brancard123")
    assert client.get("/auth/me", headers=br).json()["statut"] == "DISPONIBLE"


def test_register_medecin_sans_statut(client):
    headers = login(client, "reg@test.fr", "motdepasse")
    medecin = {**BRANCARDIER, "nom_utilisateur": "dr@test.fr", "role": "MEDECIN"}
    r = client.post("/auth/register", json=medecin, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["statut"] is None


def test_register_validation(client):
    headers = login(client, "reg@test.fr", "motdepasse")
    for champ, valeur in [("role", "brancardier"), ("role", "admin2"), ("nom_utilisateur", "ab"),
                          ("mot_de_passe", "court")]:
        r = client.post("/auth/register", json={**BRANCARDIER, champ: valeur}, headers=headers)
        assert r.status_code == 422, (champ, valeur)


def test_compte_desactive(client):
    from database import SessionLocal
    from models.utilisateur import Utilisateur
    headers = login(client, "reg@test.fr", "motdepasse")
    db = SessionLocal()
    db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == "reg@test.fr").update({"est_actif": False})
    db.commit()
    db.close()
    # le token déjà délivré ne marche plus, et la connexion est refusée
    assert client.get("/auth/me", headers=headers).status_code == 401
    r = client.post("/auth/login", data={"username": "reg@test.fr", "password": "motdepasse"})
    assert r.status_code == 403


def test_rbac(client):
    reg = login(client, "reg@test.fr", "motdepasse")
    client.post("/auth/register", json=BRANCARDIER, headers=reg)
    br = login(client, "moussa@test.fr", "brancard123")

    # un brancardier ne peut ni créer de compte ni lister les utilisateurs
    assert client.post("/auth/register", json={**BRANCARDIER, "nom_utilisateur": "x@test.fr"},
                       headers=br).status_code == 403
    assert client.get("/utilisateurs", headers=br).status_code == 403
    # sans token
    assert client.post("/auth/register", json=BRANCARDIER).status_code == 401

    # le régulateur voit la flotte
    r = client.get("/utilisateurs?role=BRANCARDIER", headers=reg)
    assert r.status_code == 200 and [u["nom_utilisateur"] for u in r.json()] == ["moussa@test.fr"]

    # seul un brancardier change son statut
    r = client.patch("/utilisateurs/me/statut", json={"statut": "EN_PAUSE"}, headers=br)
    assert r.status_code == 200 and r.json()["statut"] == "EN_PAUSE"
    assert client.patch("/utilisateurs/me/statut", json={"statut": "EN_PAUSE"},
                        headers=reg).status_code == 403


def test_cors(client):
    r = client.options("/auth/login", headers={"Origin": "http://localhost:5173",
                                                "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
