# main.py

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # enregistre tous les modèles dans Base.metadata
from database import engine, Base
from routes.auth import router as auth_router
from routes.utilisateurs import router as utilisateurs_router

#  Création de l'application FastAPI 
app = FastAPI(
    title="Smart-Brancard API",
    description="API de gestion des flux de brancardage dans les hôpitaux",
    version="1.0.0"
)

#  CORS 
# Autorise le frontend React (Vite tourne sur le port 5173 par défaut) à appeler l'API
origines = os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origines.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#  Création des tables en base 
# Crée automatiquement toutes les tables définies dans les modèles
# si elles n'existent pas encore dans PostgreSQL
try:
    Base.metadata.create_all(bind=engine)
except UnicodeDecodeError as e:
    # Sous Windows, psycopg2 plante en décodant le message d'erreur (en français)
    # de PostgreSQL: on le décode correctement pour afficher la vraie cause
    raise RuntimeError(
        "Connexion à PostgreSQL impossible : "
        + e.object.decode("cp1252", errors="replace").strip()
        + "\n-> Vérifier DATABASE_URL dans backend/.env et que la base est démarrée (docker compose up -d)"
    ) from None

#  Enregistrement des routes 
app.include_router(auth_router)          # /auth/...
app.include_router(utilisateurs_router)  # /utilisateurs/...


#  Route de test 
@app.get("/")
def accueil():
    """Route de test: vérifie que l'API tourne correctement"""
    return {"message": "Smart-Brancard API est en ligne !"}
