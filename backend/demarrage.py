# demarrage.py
# Démarrage du backend dans Docker (docker compose up) : tout ce qu'on faisait à la main, dans l'ordre.
#   1. attendre que PostgreSQL accepte les connexions (au premier lancement, il crée d'abord la base) ;
#   2. appliquer les migrations (alembic upgrade head) ;
#   3. charger le plan de l'hôpital s'il manque (seed_graphe.py) ;
#   4. avec DEMO=1, charger le jeu de démonstration (seed_demo.py) ;
#   5. lancer l'API (uvicorn).
# En Python plutôt qu'en script shell : un fichier .sh enregistré sous Windows (fins de ligne CRLF)
# ne s'exécute pas dans un conteneur Linux.

import os
import secrets
import subprocess
import sys
import time

from sqlalchemy import create_engine, text

ATTENTE_MAX_S = 60


def attendre_la_base(url: str) -> None:
    """Réessaie toutes les secondes : le conteneur db peut être démarré sans être encore prêt"""
    moteur = create_engine(url, pool_pre_ping=True)
    debut = time.monotonic()
    while True:
        try:
            with moteur.connect() as connexion:
                connexion.execute(text("SELECT 1"))
            print("PostgreSQL est prêt", flush=True)
            return
        except Exception as e:
            if time.monotonic() - debut > ATTENTE_MAX_S:
                sys.exit(f"PostgreSQL injoignable après {ATTENTE_MAX_S} s : {e}")
            time.sleep(1)
        finally:
            moteur.dispose()


def lancer(*commande: str) -> None:
    """Exécute une étape ; arrête tout si elle échoue"""
    print("->", " ".join(commande), flush=True)
    subprocess.run(commande, check=True)


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL manquante (voir docker-compose.yml)")

    # Sans clé fournie, une clé aléatoire est tirée à chaque démarrage : tous les processus de
    # uvicorn la reçoivent (même clé pour tous), mais les connexions ouvertes sont perdues au redémarrage
    if not os.environ.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = secrets.token_hex(32)
        print("SECRET_KEY absente : clé temporaire générée (reconnexion nécessaire après un redémarrage)", flush=True)

    attendre_la_base(url)
    lancer(sys.executable, "-m", "alembic", "upgrade", "head")
    lancer(sys.executable, "seed_graphe.py")
    if os.environ.get("DEMO") == "1":
        lancer(sys.executable, "seed_demo.py")

    # Plusieurs processus : le temps réel passe par Redis (REDIS_URL), les tâches de fond
    # verrouillent leurs lignes (SKIP LOCKED) et peuvent tourner dans chacun
    processus = os.environ.get("WORKERS", "2")
    print(f"API sur le port 8000 ({processus} processus)", flush=True)
    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "main:app",
                               "--host", "0.0.0.0", "--port", "8000",
                               "--workers", processus, "--proxy-headers",
                               "--forwarded-allow-ips", "*"])


if __name__ == "__main__":
    main()
