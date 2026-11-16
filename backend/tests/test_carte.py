# Connexion des brancardiers par carte QR

from database import SessionLocal
from models.utilisateur import Utilisateur
from tests.conftest import login

AGENT = {"nom_utilisateur": "cisse@test.fr", "prenom": "Amadou", "nom": "Cissé",
         "mot_de_passe": "brancard123", "role": "BRANCARDIER"}
MEDECIN = {"nom_utilisateur": "diallo@test.fr", "prenom": "Awa", "nom": "Diallo",
           "mot_de_passe": "medecin123", "role": "MEDECIN"}


def carte(client, reg, utilisateur_id):
    return client.post(f"/utilisateurs/{utilisateur_id}/carte", headers=reg)


def test_l_agent_se_connecte_avec_sa_carte(client):
    reg = login(client, "reg@test.fr", "motdepasse")
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]

    r = carte(client, reg, agent_id)
    assert r.status_code == 201, r.text
    code = r.json()["code"]
    assert code.startswith("SBC-") and r.json()["prenom"] == "Amadou"

    r = client.post("/auth/carte", json={"code": code})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "BRANCARDIER"
    moi = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"}).json()
    assert moi["id"] == agent_id and moi["a_une_carte"] is True


def test_le_code_n_est_jamais_garde_en_clair(client):
    reg = login(client, "reg@test.fr", "motdepasse")
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    code = carte(client, reg, agent_id).json()["code"]
    db = SessionLocal()
    stocke = db.get(Utilisateur, agent_id).carte_hash
    db.close()
    assert stocke != code and len(stocke) == 64   # seulement l'empreinte SHA-256
    # Le code n'apparaît pas non plus dans la liste des agents
    assert "code" not in client.get("/utilisateurs", headers=reg).json()[0]


def test_une_carte_perdue_est_remplacee(client):
    reg = login(client, "reg@test.fr", "motdepasse")
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    ancienne = carte(client, reg, agent_id).json()["code"]
    nouvelle = carte(client, reg, agent_id).json()["code"]

    assert nouvelle != ancienne
    r = client.post("/auth/carte", json={"code": ancienne})
    assert r.status_code == 401 and "nouvelle carte" in r.json()["detail"]
    assert client.post("/auth/carte", json={"code": nouvelle}).status_code == 200
    # Le mot de passe reste valable en secours
    login(client, "cisse@test.fr", "brancard123")


def test_carte_inconnue_ou_compte_desactive(client):
    reg = login(client, "reg@test.fr", "motdepasse")
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    code = carte(client, reg, agent_id).json()["code"]
    assert client.post("/auth/carte", json={"code": "SBC-faux"}).status_code == 401
    assert client.post("/auth/carte", json={"code": "QR-00000001"}).status_code == 401   # un bracelet
    assert client.post("/auth/carte", json={"code": ""}).status_code == 422

    db = SessionLocal()
    db.get(Utilisateur, agent_id).est_actif = False
    db.commit()
    db.close()
    assert client.post("/auth/carte", json={"code": code}).status_code == 403


def test_cartes_reservees_aux_brancardiers_et_au_regulateur(client):
    reg = login(client, "reg@test.fr", "motdepasse")
    agent_id = client.post("/auth/register", json=AGENT, headers=reg).json()["id"]
    medecin_id = client.post("/auth/register", json=MEDECIN, headers=reg).json()["id"]
    medecin = login(client, "diallo@test.fr", "medecin123")

    assert carte(client, reg, medecin_id).status_code == 422   # le médecin garde son mot de passe
    assert carte(client, reg, 999).status_code == 404
    assert carte(client, medecin, agent_id).status_code == 403
    assert carte(client, login(client, "cisse@test.fr", "brancard123"), agent_id).status_code == 403
