# seed_demo.py
# Jeu de données de démonstration (Sprint 5) : comptes, équipe de brancardiers, patients avec bracelet.
# Le plan de l'hôpital (salles et tags NFC) vient de seed_graphe.py, chargé ici s'il manque.
#
# Équipe de jour recommandée par l'analyse de la file d'attente (rapport Sprint 5, § 4.3) :
# 4 agents polyvalents, et 2 agents postés au centre de chaque étage, réservés aux URGENT.
#
# Prérequis : les tables existent (alembic upgrade head)
# Utilisation : python seed_demo.py   (lancé tout seul par Docker quand DEMO=1)
# Le script peut être relancé : un compte ou un patient qui existe déjà n'est pas recréé.
#
# ATTENTION : mots de passe connus de tous. Pour une démonstration seulement, jamais en production.

import models  # enregistre tous les modèles
from database import SessionLocal
from models.enums import Role, Sexe, StatutIdentite
from models.patient import Patient
from models.utilisateur import Brancardier, Utilisateur
from services.auth_service import hash_password
from services.graphe_service import charger_graphe_json

MOT_DE_PASSE_DEMO = "demo1234"

# Postes d'attente (nœuds de data/graphe_hopital.json) : le centre de chaque étage
HALL_RDC = 6        # Hall central - RDC
PALIER_ETAGE = 16   # Palier central - Étage 1

# (identifiant, prénom, nom, rôle)
COMPTES = [
    ("regulateur@demo.sn", "Mariama", "Sarr", Role.REGULATEUR),
    ("dr.diallo@demo.sn", "Awa", "Diallo", Role.MEDECIN),        # Urgences
    ("dr.ndiaye@demo.sn", "Moussa", "Ndiaye", Role.MEDECIN),     # Cardiologie
]

# (identifiant, prénom, nom, poste d'attente, réservé aux URGENT)
BRANCARDIERS = [
    ("ibrahima.fall@demo.sn", "Ibrahima", "Fall", None, False),
    ("fatou.sow@demo.sn", "Fatou", "Sow", None, False),
    ("cheikh.ba@demo.sn", "Cheikh", "Ba", None, False),
    ("aminata.diop@demo.sn", "Aminata", "Diop", None, False),
    ("ousmane.gueye@demo.sn", "Ousmane", "Gueye", HALL_RDC, True),
    ("khady.faye@demo.sn", "Khady", "Faye", PALIER_ETAGE, True),
]

# (IPP, prénom, nom, sexe, identité). IPP fixes : les bracelets imprimés restent valables
# d'une installation à l'autre (docs/demo/bracelets.html). Le dernier est un patient admis
# inconscient, à l'identité provisoire.
PATIENTS = [
    ("90000001", "Abdoulaye", "Diouf", Sexe.MASCULIN, StatutIdentite.VALIDEE),
    ("90000002", "Ndeye", "Mbaye", Sexe.FEMININ, StatutIdentite.VALIDEE),
    ("90000003", "Mamadou", "Kane", Sexe.MASCULIN, StatutIdentite.VALIDEE),
    ("90000004", "Seynabou", "Cisse", Sexe.FEMININ, StatutIdentite.VALIDEE),
    ("90000005", "Pape", "Seck", Sexe.MASCULIN, StatutIdentite.VALIDEE),
    ("90000006", "Astou", "Thiam", Sexe.FEMININ, StatutIdentite.VALIDEE),
    ("90000007", "Moustapha", "Diallo", Sexe.MASCULIN, StatutIdentite.VALIDEE),
    ("90000008", "X-90000008", "INCONNU", Sexe.INDETERMINE, StatutIdentite.PROVISOIRE),
]


def charger_demo(db) -> dict:
    """Crée ce qui manque ; renvoie le nombre de lignes créées par catégorie"""
    crees = {"lieux": charger_graphe_json(db), "comptes": 0, "brancardiers": 0, "patients": 0}
    deja = {u for (u,) in db.query(Utilisateur.nom_utilisateur).all()}
    empreinte = hash_password(MOT_DE_PASSE_DEMO)   # bcrypt est lent : une seule fois

    for identifiant, prenom, nom, role in COMPTES:
        if identifiant not in deja:
            db.add(Utilisateur(nom_utilisateur=identifiant, prenom=prenom, nom=nom,
                               mot_de_passe_hash=empreinte, role=role))
            crees["comptes"] += 1

    for identifiant, prenom, nom, poste, reserve in BRANCARDIERS:
        if identifiant not in deja:
            # Disponibles dès la création (statut par défaut), mais sans position : le simulateur
            # de badges les place dans l'hôpital (voir docs/scenario-demonstration.md)
            db.add(Brancardier(nom_utilisateur=identifiant, prenom=prenom, nom=nom,
                               mot_de_passe_hash=empreinte, role=Role.BRANCARDIER,
                               poste_id=poste, reserve_urgent=reserve))
            crees["brancardiers"] += 1

    connus = {i for (i,) in db.query(Patient.id_hospitalisation).all()}
    for ipp, prenom, nom, sexe, identite in PATIENTS:
        if ipp not in connus:
            db.add(Patient(id_hospitalisation=ipp, code_bracelet=f"QR-{ipp}", prenom=prenom, nom=nom,
                           sexe=sexe, statut_identite=identite))
            crees["patients"] += 1

    db.commit()
    return crees


def main():
    db = SessionLocal()
    try:
        crees = charger_demo(db)
    finally:
        db.close()
    print("Données de démonstration : " + ", ".join(f"{n} {c} créé(s)" for c, n in crees.items()))
    print(f"Mot de passe de tous les comptes : {MOT_DE_PASSE_DEMO}")
    for identifiant, prenom, nom, role in COMPTES:
        print(f"  {role.value:<11} {identifiant:<24} {prenom} {nom}")
    for identifiant, prenom, nom, poste, reserve in BRANCARDIERS:
        detail = " (posté, réservé aux URGENT)" if reserve else ""
        print(f"  BRANCARDIER {identifiant:<24} {prenom} {nom}{detail}")


if __name__ == "__main__":
    main()
