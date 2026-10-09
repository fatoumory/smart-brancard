# services/taches_fond.py
# Tâches exécutées régulièrement par le serveur, sans attendre qu'un utilisateur fasse une requête.
# Exemple : un agent en pause qui a fermé son application doit quand même être remis disponible.

import asyncio
import logging
import os

from database import SessionLocal
from services.assignation_service import gerer_reprise_service_auto

journal = logging.getLogger("smart_brancard.taches_fond")

# Intervalle entre deux passages, en secondes (0 = tâches désactivées, par exemple pendant les tests)
INTERVALLE_S = float(os.getenv("TACHES_FOND_INTERVALLE", "5"))


def executer_taches_periodiques() -> None:
    """Un passage de toutes les tâches périodiques, chacune avec sa propre session"""
    db = SessionLocal()
    try:
        repris = gerer_reprise_service_auto(db)
        if repris:
            journal.info("%s agent(s) remis disponible(s) en fin de pause", repris)
    finally:
        db.close()


async def boucle_taches_fond() -> None:
    """Exécute les tâches périodiques en continu, tant que l'API tourne"""
    while True:
        try:
            # Les tâches utilisent la base de façon bloquante : on les exécute hors de la boucle asyncio
            await asyncio.to_thread(executer_taches_periodiques)
        except Exception:
            # Une erreur ponctuelle (base momentanément injoignable...) ne doit pas arrêter la boucle
            journal.exception("Échec d'un passage des tâches de fond")
        await asyncio.sleep(INTERVALLE_S)
