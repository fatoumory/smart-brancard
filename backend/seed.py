# seed.py
# Crée le premier compte régulateur (nécessaire car /auth/register est réservé aux régulateurs)
# Prérequis : les tables existent (alembic upgrade head)
# Utilisation : python seed.py --nom-utilisateur regulateur@hopital.fr --nom Diallo --prenom Awa

import argparse
import getpass

import models  # enregistre tous les modèles
from database import SessionLocal
from models.enums import Role
from models.utilisateur import Utilisateur
from schemas.utilisateur import UtilisateurCreate
from services.auth_service import hash_password


def main():
    parser = argparse.ArgumentParser(description="Création du premier régulateur")
    parser.add_argument("--nom-utilisateur", required=True)
    parser.add_argument("--nom", required=True)
    parser.add_argument("--prenom", required=True)
    args = parser.parse_args()

    mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
    donnees = UtilisateurCreate(
        nom_utilisateur=args.nom_utilisateur, prenom=args.prenom, nom=args.nom,
        mot_de_passe=mot_de_passe, role=Role.REGULATEUR
    )

    db = SessionLocal()
    try:
        if db.query(Utilisateur).filter(Utilisateur.nom_utilisateur == donnees.nom_utilisateur).first():
            print(f"Un compte existe déjà pour {donnees.nom_utilisateur}")
            return
        db.add(Utilisateur(
            nom_utilisateur=donnees.nom_utilisateur, prenom=donnees.prenom, nom=donnees.nom,
            mot_de_passe_hash=hash_password(donnees.mot_de_passe),
            role=donnees.role
        ))
        db.commit()
        print(f"Régulateur {donnees.nom_utilisateur} créé")
    finally:
        db.close()


if __name__ == "__main__":
    main()
