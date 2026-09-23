# seed.py
# Crée le premier compte régulateur (nécessaire car /auth/register est réservé aux régulateurs)
# Utilisation : python seed.py --email regulateur@hopital.fr --nom Diallo --prenom Awa

import argparse
import getpass

import models  # enregistre tous les modèles dans Base.metadata
from database import Base, SessionLocal, engine
from models.utilisateur import Utilisateur
from schemas.utilisateur import Role, UtilisateurCreate
from services.auth_service import hash_password


def main():
    parser = argparse.ArgumentParser(description="Création du premier régulateur")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nom", required=True)
    parser.add_argument("--prenom", required=True)
    args = parser.parse_args()

    mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
    donnees = UtilisateurCreate(
        nom=args.nom, prenom=args.prenom, email=args.email,
        mot_de_passe=mot_de_passe, role=Role.regulateur
    )

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        email = donnees.email.lower()
        if db.query(Utilisateur).filter(Utilisateur.email == email).first():
            print(f"Un compte existe déjà pour {email}")
            return
        db.add(Utilisateur(
            nom=donnees.nom, prenom=donnees.prenom, email=email,
            mot_de_passe_hash=hash_password(donnees.mot_de_passe),
            role=donnees.role.value
        ))
        db.commit()
        print(f"Régulateur {email} créé")
    finally:
        db.close()


if __name__ == "__main__":
    main()
