# Image du backend FastAPI (lancée par docker compose, voir docker-compose.yml à la racine)
FROM python:3.12-slim

# Journaux affichés tout de suite (pas de tampon), pas de fichiers .pyc dans l'image
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dépendances d'abord : cette couche reste en cache tant que requirements.txt ne change pas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'application (sans venv ni .env : voir .dockerignore)
COPY . .

# L'API ne tourne pas en administrateur dans le conteneur
RUN useradd --create-home --uid 1000 api && chown -R api /app
USER api

EXPOSE 8000

# Migrations, plan de l'hôpital, données de démonstration, puis uvicorn (voir demarrage.py)
CMD ["python", "demarrage.py"]
