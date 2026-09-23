# tests/test_auth.py

from tests.conftest import login

BRANCARDIER = {"nom": "Ba", "prenom": "Moussa", "email": "moussa@test.fr",
               "mot_de_passe": "brancard123", "role": "brancardier"}


def test_tables_creees():
    from database import Base
    assert {"utilisateurs", "patients", "missions"} <= set(Base.metadata.tables)


def test_login_ok_et_me(client):
    headers = login(client, "reg@test.fr", "motdepasse")
    r = client.get("/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "regulateur"
    assert "mot_de_passe_hash" not in r.json()


def test_login_mauvais_mot_de_passe(client):
    r = client.post("/auth/login", data={"username": "reg@test.fr", "password": "faux"})
    assert r.status_code == 401


def test_me_sans_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer abc"}).status_code == 401


def test_register_par_regulateur(client):
    headers = login(client, "reg@test.fr", "motdepasse")
    r = client.post("/auth/register", json=BRANCARDIER, headers=headers)
    assert r.status_code == 201, r.text
    assert r.json()["statut"] == "disponible"
    # doublon
    assert client.post("/auth/register", json=BRANCARDIER, headers=headers).status_code == 400
    # le nouveau compte peut se connecter
    login(client, "moussa@test.fr", "brancard123")


def test_register_validation(client):
    headers = login(client, "reg@test.fr", "motdepasse")
    for champ, valeur in [("role", "admin"), ("email", "pas-un-email"), ("mot_de_passe", "court")]:
        r = client.post("/auth/register", json={**BRANCARDIER, champ: valeur}, headers=headers)
        assert r.status_code == 422


def test_rbac(client):
    reg = login(client, "reg@test.fr", "motdepasse")
    client.post("/auth/register", json=BRANCARDIER, headers=reg)
    br = login(client, "moussa@test.fr", "brancard123")

    # un brancardier ne peut ni créer de compte ni lister les utilisateurs
    assert client.post("/auth/register", json={**BRANCARDIER, "email": "x@test.fr"}, headers=br).status_code == 403
    assert client.get("/utilisateurs", headers=br).status_code == 403
    # sans token
    assert client.post("/auth/register", json=BRANCARDIER).status_code == 401

    # le régulateur voit la flotte
    r = client.get("/utilisateurs?role=brancardier", headers=reg)
    assert r.status_code == 200 and [u["email"] for u in r.json()] == ["moussa@test.fr"]

    # seul un brancardier change son statut
    r = client.patch("/utilisateurs/me/statut", json={"statut": "pause"}, headers=br)
    assert r.status_code == 200 and r.json()["statut"] == "pause"
    assert client.patch("/utilisateurs/me/statut", json={"statut": "pause"}, headers=reg).status_code == 403


def test_cors(client):
    r = client.options("/auth/login", headers={"Origin": "http://localhost:5173",
                                                "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
