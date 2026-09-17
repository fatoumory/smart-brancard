# database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# URL de connexion à PostgreSQL
# Format : postgresql://utilisateur:motdepasse@hote:port/nom_base
DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/smart_brancard"

# Le moteur: c'est lui qui établit la connexion réelle avec PostgreSQL
engine = create_engine(DATABASE_URL)

# La fabrique de sessions: chaque session = une "conversation" avec la base
# autocommit=False : on valide manuellement les changements (plus sécurisé)
# autoflush=False : on contrôle quand les données sont envoyées à la base
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# La classe de base dont hériteront tous nos modèles (Utilisateur, Mission, Patient)
# SQLAlchemy s'en sert pour créer les tables automatiquement
Base = declarative_base()

# Dépendance FastAPI: ouvre une session pour chaque requête et la ferme après
# Le "yield" permet à FastAPI d'injecter la session dans les routes via Depends(get_db)
def get_db():
    db = SessionLocal()
    try:
        yield db       # la session est disponible pendant le traitement de la requête
    finally:
        db.close()     # la session est fermée quoi qu'il arrive (même en cas d'erreur)