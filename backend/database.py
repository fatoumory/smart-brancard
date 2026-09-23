# database.py

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Charge les variables du fichier .env (sans écraser celles déjà définies)
load_dotenv()

# URL de connexion à PostgreSQL
# Format : postgresql://utilisateur:motdepasse@hote:port/nom_base
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL manquante : copier .env.example vers .env et la renseigner")

# Le moteur: c'est lui qui établit la connexion réelle avec PostgreSQL
# pool_pre_ping=True : vérifie qu'une connexion est encore vivante avant de l'utiliser
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# La fabrique de sessions: chaque session = une "conversation" avec la base
# autocommit=False : on valide manuellement les changements (plus sécurisé)
# autoflush=False : on contrôle quand les données sont envoyées à la base
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# La classe de base dont hériteront tous nos modèles (Utilisateur, Mission, Patient)
Base = declarative_base()

# Dépendance FastAPI: ouvre une session pour chaque requête et la ferme après
def get_db():
    db = SessionLocal()
    try:
        yield db       # la session est disponible pendant le traitement de la requête
    finally:
        db.close()     # la session est fermée quoi qu'il arrive (même en cas d'erreur)
