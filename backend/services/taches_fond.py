# services/taches_fond.py
# Tâches exécutées régulièrement par le serveur, sans attendre qu'un utilisateur fasse une requête.
# Exemples : une proposition restée sans réponse dans son délai (30 à 60 s) est réaffectée ; un agent en pause qui a fermé
# son application est quand même remis disponible à la fin de sa pause.

import asyncio
import logging
import os

from database import SessionLocal
from services.assignation_service import (gerer_propositions_expirees, gerer_reprise_service_auto,
                                          traiter_file_attente)

journal = logging.getLogger("smart_brancard.taches_fond")

# Intervalle entre deux passages, en secondes (0 = tâches désactivées, par exemple pendant les tests)
INTERVALLE_S = float(os.getenv("TACHES_FOND_INTERVALLE", "5"))


def executer_taches_periodiques() -> None:
    """Un passage de toutes les tâches périodiques, chacune avec sa propre session"""
    db = SessionLocal()
    try:
        expirees = gerer_propositions_expirees(db)
        if expirees:
            journal.info("%s proposition(s) restée(s) sans réponse dans le délai, réaffectée(s)", expirees)
        repris = gerer_reprise_service_auto(db)
        if repris:
            journal.info("%s agent(s) remis disponible(s) en fin de pause", repris)
        # Missions en attente dont une exclusion vient de tomber (5 min après un refus ou une non-réponse)
        proposees = traiter_file_attente(db)
        if proposees:
            journal.info("%s mission(s) en attente proposée(s)", proposees)
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
