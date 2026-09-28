# tests/test_patients.py
# Admission : IPP et bracelet générés, identité provisoire, patient qui revient, droits d'accès

from datetime import date, timedelta

import pytest

from tests.conftest import login

INFIRMIERE = {"nom_utilisateur": "accueil@test.fr", "prenom": "Awa", "nom": "Ndiaye",
            "mot_de_passe": "accueil123", "role": "MEDECIN"}
BRANCARDIER = {"nom_utilisateur": "moussa@test.fr", "prenom": "Moussa", "nom": "Ba",
            "mot_de_passe": "brancard123", "role": "BRANCARDIER"}

DUPONT = {"nom": "Dupont", "prenom": "Jean", "date_naissance": "1960-05-03", "sexe": "MASCULIN"}


@pytest.fixture()
def reg(client):
    return login(client, "reg@test.fr", "motdepasse")


@pytest.fixture()
def accueil(client, reg):
    """En-têtes de l'infirmière d'accueil (rôle MEDECIN)"""
    client.post("/auth/register", json=INFIRMIERE, headers=reg)
    return login(client, "accueil@test.fr", "accueil123")


def test_admission(client, accueil):
    r = client.post("/patients", json=DUPONT, headers=accueil)
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["nom"], p["prenom"], p["sexe"]) == ("Dupont", "Jean", "MASCULIN")
    assert p["statut_identite"] == "VALIDEE"
    # IPP généré sur 8 chiffres, et le QR du bracelet encode l'IPP
    assert len(p["id_hospitalisation"]) == 8 and p["id_hospitalisation"].isdigit()
    assert p["code_bracelet"] == "QR-" + p["id_hospitalisation"]


def test_identite_inconnue(client, accueil):
    r = client.post("/patients", json={"identite_inconnue": True, "sexe": "FEMININ"}, headers=accueil)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["nom"] == "INCONNU"
    assert p["prenom"] == "X-" + p["id_hospitalisation"]
    assert p["statut_identite"] == "PROVISOIRE"
    assert p["date_naissance"] is None


def test_deux_inconnus_ont_des_ipp_differents(client, accueil):
    a = client.post("/patients", json={"identite_inconnue": True}, headers=accueil).json()
    b = client.post("/patients", json={"identite_inconnue": True}, headers=accueil).json()
    assert a["id_hospitalisation"] != b["id_hospitalisation"]
    assert a["prenom"] != b["prenom"]


def test_patient_qui_revient(client, accueil):
    premier = client.post("/patients", json=DUPONT, headers=accueil).json()

    # Même nom, prénom et date de naissance (majuscules différentes) : pas de second IPP
    r = client.post("/patients", json={**DUPONT, "nom": "DUPONT"}, headers=accueil)
    assert r.status_code == 409
    similaires = r.json()["detail"]["patients_similaires"]
    assert [s["id_hospitalisation"] for s in similaires] == [premier["id_hospitalisation"]]


def test_homonyme_confirme(client, accueil):
    client.post("/patients", json=DUPONT, headers=accueil)
    # Vrai homonyme : l'infirmière confirme, un nouvel IPP est créé
    r = client.post("/patients", json={**DUPONT, "confirmer_nouveau": True}, headers=accueil)
    assert r.status_code == 201


def test_meme_nom_autre_date_de_naissance(client, accueil):
    client.post("/patients", json=DUPONT, headers=accueil)
    # Deux dates de naissance connues et différentes : deux personnes distinctes
    r = client.post("/patients", json={**DUPONT, "date_naissance": "1985-11-12"}, headers=accueil)
    assert r.status_code == 201


def test_donnees_invalides(client, accueil):
    demain = (date.today() + timedelta(days=1)).isoformat()
    for donnees in [{"prenom": "Jean"},                          # nom manquant
                    {"nom": "  ", "prenom": "Jean"},             # nom vide
                    {**DUPONT, "date_naissance": demain},       # naissance dans le futur
                    {**DUPONT, "sexe": "AUTRE"}]:                # valeur hors énumération
        assert client.post("/patients", json=donnees, headers=accueil).status_code == 422, donnees


def test_reserve_a_l_accueil(client, reg):
    client.post("/auth/register", json=BRANCARDIER, headers=reg)
    br = login(client, "moussa@test.fr", "brancard123")
    assert client.post("/patients", json=DUPONT, headers=reg).status_code == 403
    assert client.post("/patients", json=DUPONT, headers=br).status_code == 403
    assert client.post("/patients", json=DUPONT).status_code == 401

#  Étape 3 : recherche et validation de l'identité

def admettre(client, headers, donnees):
    r = client.post("/patients", json=donnees, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_recherche(client, accueil):
    dupont = admettre(client, accueil, DUPONT)
    admettre(client, accueil, {"nom": "Diop", "prenom": "Fatou"})
    inconnu = admettre(client, accueil, {"identite_inconnue": True})

    def noms(recherche):
        r = client.get("/patients", params={"recherche": recherche}, headers=accueil)
        assert r.status_code == 200, r.text
        return [p["nom"] for p in r.json()]

    assert noms("dup") == ["Dupont"]                             # début du nom
    assert noms("JEAN") == ["Dupont"]                            # prénom, majuscules
    assert noms("dup jea") == ["Dupont"]                         # plusieurs mots
    assert noms("dupont fatou") == []                            # chaque mot doit correspondre
    assert noms(dupont["id_hospitalisation"]) == ["Dupont"]      # par IPP
    assert noms("inconnu") == ["INCONNU"]                        # identités provisoires
    assert noms(inconnu["prenom"]) == ["INCONNU"]


def test_recherche_trop_courte_ou_non_autorisee(client, reg, accueil):
    assert client.get("/patients", params={"recherche": "d"}, headers=accueil).status_code == 422
    assert client.get("/patients", headers=accueil).status_code == 422
    assert client.get("/patients", params={"recherche": "dup"}, headers=reg).status_code == 403
    assert client.get("/patients", params={"recherche": "dup"}).status_code == 401


def test_identite_provisoire_validee(client, accueil):
    inconnu = admettre(client, accueil, {"identite_inconnue": True})
    r = client.patch(f"/patients/{inconnu['id']}", headers=accueil,
                     json={"nom": "Traoré", "prenom": "Moussa", "date_naissance": "1990-01-15",
                           "sexe": "MASCULIN"})
    assert r.status_code == 200, r.text
    p = r.json()
    assert (p["nom"], p["prenom"], p["statut_identite"]) == ("Traoré", "Moussa", "VALIDEE")
    # L'IPP et le bracelet ne changent pas
    assert p["id_hospitalisation"] == inconnu["id_hospitalisation"]
    assert p["code_bracelet"] == inconnu["code_bracelet"]


def test_identite_deja_connue(client, accueil):
    dupont = admettre(client, accueil, DUPONT)
    inconnu = admettre(client, accueil, {"identite_inconnue": True})

    # L'inconnu est identifié comme Jean Dupont, qui a déjà un IPP : on prévient
    r = client.patch(f"/patients/{inconnu['id']}", json=DUPONT, headers=accueil)
    assert r.status_code == 409
    ipps = [p["id_hospitalisation"] for p in r.json()["detail"]["patients_similaires"]]
    assert ipps == [dupont["id_hospitalisation"]]

    # Vrai homonyme : l'infirmière confirme
    r = client.patch(f"/patients/{inconnu['id']}", json={**DUPONT, "confirmer_nouveau": True},
                    headers=accueil)
    assert r.status_code == 200


def test_correction_sans_se_trouver_soi_meme(client, accueil):
    dupont = admettre(client, accueil, DUPONT)
    # Corriger une faute sur son propre prénom ne doit pas le détecter comme doublon de lui-même
    r = client.patch(f"/patients/{dupont['id']}", json={**DUPONT, "prenom": "Jean-Pierre"},
                    headers=accueil)
    assert r.status_code == 200
    r = client.patch(f"/patients/{dupont['id']}", json=DUPONT, headers=accueil)
    assert r.status_code == 200


def test_modifier_identite_erreurs(client, reg, accueil):
    inconnu = admettre(client, accueil, {"identite_inconnue": True})
    assert client.patch("/patients/999", json=DUPONT, headers=accueil).status_code == 404
    assert client.patch(f"/patients/{inconnu['id']}", json={"nom": "Traoré"},
                        headers=accueil).status_code == 422
    assert client.patch(f"/patients/{inconnu['id']}", json=DUPONT, headers=reg).status_code == 403
