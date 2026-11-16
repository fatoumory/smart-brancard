# services/temps_reel.py
# Temps réel : les écrans ouverts sont prévenus dès qu'une donnée change (CDC §4.7).
#
# Le serveur n'envoie pas les données elles-mêmes, seulement le « sujet » qui a changé :
#     {"type": "maj", "sujets": ["missions", "agents"]}
# L'écran recharge alors ce qui le concerne par les routes habituelles, qui vérifient les droits
# de chacun : aucune donnée patient ne passe par le WebSocket.
#
# Les sujets sont repérés automatiquement : à chaque validation en base (commit), on regarde quelles
# tables ont reçu des lignes créées, modifiées ou supprimées. Aucune route ne peut donc oublier de
# prévenir les écrans, et une action annulée (rollback) ne prévient personne.
#
# Plusieurs processus du serveur (uvicorn --workers 4) : chacun ne connaît que ses propres
# connexions. Avec REDIS_URL, les sujets passent par Redis Pub/Sub et chaque processus les
# transmet à ses écrans. Sans Redis (tests, un seul processus), ils sont transmis directement.

import asyncio
import json
import logging
import threading

from fastapi import WebSocket
from sqlalchemy import event
from sqlalchemy.orm import Session

journal = logging.getLogger("smart_brancard.temps_reel")

# Canal Redis commun à tous les processus du serveur
CANAL_REDIS = "smart_brancard:maj"

# Sujet prévenu quand une table change
SUJETS_PAR_TABLE = {
    "missions": "missions",
    "historiques": "missions",
    "patients": "missions",       # identité provisoire complétée : affichée dans les missions
    "utilisateurs": "agents",     # statut, pause, compte désactivé...
    "brancardiers": "agents",
    "detections": "agents",       # position des agents
    "alertes": "alertes",
    "aretes": "graphe",           # ascenseur ou couloir bloqué
}

# Clé où la session garde les sujets en attente de son commit
CLE_SESSION = "sujets_temps_reel"


#  Diffusion des sujets aux écrans connectés

class Diffuseur:
    def __init__(self):
        # Chaque connexion avec la boucle asyncio qui la sert (les routes tournent dans d'autres threads)
        self._connexions: dict[WebSocket, asyncio.AbstractEventLoop] = {}
        self._verrou = threading.Lock()
        # Client Redis synchrone pour publier (None : diffusion directe, un seul processus)
        self._redis = None
        self._ecoute: asyncio.Task | None = None

    #  Connexions des écrans
    async def connecter(self, websocket: WebSocket) -> None:
        with self._verrou:
            self._connexions[websocket] = asyncio.get_running_loop()

    def deconnecter(self, websocket: WebSocket) -> None:
        with self._verrou:
            self._connexions.pop(websocket, None)

    def nombre_de_connexions(self) -> int:
        with self._verrou:
            return len(self._connexions)

    #  Publication (appelée après chaque commit, depuis n'importe quel thread)
    def publier(self, sujets: list[str]) -> None:
        message = json.dumps({"type": "maj", "sujets": sujets})
        if self._redis is not None:
            try:
                # Tous les processus (celui-ci compris) le reçoivent par leur écoute Redis
                self._redis.publish(CANAL_REDIS, message)
                return
            except Exception:
                journal.warning("Redis injoignable : sujets transmis aux seuls écrans de ce processus")
        self.transmettre_depuis_un_thread(message)

    def transmettre_depuis_un_thread(self, message: str) -> None:
        """Confie l'envoi à la boucle asyncio de chaque connexion"""
        with self._verrou:
            boucles = set(self._connexions.values())
        for boucle in boucles:
            if boucle.is_closed():
                continue
            try:
                courante = asyncio.get_running_loop()
            except RuntimeError:
                courante = None
            if courante is boucle:
                boucle.create_task(self.transmettre(message, boucle))
            else:
                asyncio.run_coroutine_threadsafe(self.transmettre(message, boucle), boucle)

    async def transmettre(self, message: str, boucle: asyncio.AbstractEventLoop) -> None:
        """Envoie le message aux connexions servies par cette boucle ; oublie celles qui sont fermées"""
        with self._verrou:
            connexions = [ws for ws, b in self._connexions.items() if b is boucle]
        for websocket in connexions:
            try:
                await websocket.send_text(message)
            except Exception:
                self.deconnecter(websocket)

    #  Redis Pub/Sub (plusieurs processus du serveur)
    async def demarrer_redis(self, url: str) -> None:
        """Publie et écoute par Redis ; sans Redis joignable, reste en diffusion directe"""
        try:
            import redis
            import redis.asyncio as redis_async
            client = redis.Redis.from_url(url)
            client.ping()
            abonne = redis_async.Redis.from_url(url).pubsub()
            await abonne.subscribe(CANAL_REDIS)
        except Exception as e:
            journal.warning("Redis indisponible (%s) : diffusion directe, un seul processus", e)
            return
        self._redis = client
        self._ecoute = asyncio.create_task(self._ecouter(abonne))
        journal.info("Temps réel par Redis Pub/Sub (%s)", CANAL_REDIS)

    async def _ecouter(self, abonne) -> None:
        """Transmet aux écrans de ce processus les sujets publiés par tous les processus"""
        boucle = asyncio.get_running_loop()
        async for message in abonne.listen():
            if message.get("type") == "message":
                donnees = message["data"]
                texte = donnees.decode() if isinstance(donnees, bytes) else donnees
                await self.transmettre(texte, boucle)

    async def arreter(self) -> None:
        if self._ecoute is not None:
            self._ecoute.cancel()
            self._ecoute = None
        self._redis = None


diffuseur = Diffuseur()


#  Repérage automatique des sujets, à chaque commit

@event.listens_for(Session, "after_flush")
def noter_les_sujets(session: Session, _contexte) -> None:
    """Après chaque envoi à la base : retient les sujets des lignes créées, modifiées ou supprimées"""
    sujets = session.info.setdefault(CLE_SESSION, set())
    for objet in (*session.new, *session.dirty, *session.deleted):
        sujet = SUJETS_PAR_TABLE.get(getattr(objet, "__tablename__", None))
        if sujet is not None:
            sujets.add(sujet)


@event.listens_for(Session, "after_commit")
def publier_apres_commit(session: Session) -> None:
    """Les changements sont enregistrés : on prévient les écrans"""
    sujets = session.info.pop(CLE_SESSION, None)
    if sujets:
        try:
            diffuseur.publier(sorted(sujets))
        except Exception:
            # Le temps réel ne doit jamais faire échouer une action déjà enregistrée
            journal.exception("Échec de la diffusion des sujets %s", sujets)


@event.listens_for(Session, "after_rollback")
def oublier_apres_rollback(session: Session) -> None:
    """Action annulée : rien n'a changé, personne n'est prévenu"""
    session.info.pop(CLE_SESSION, None)
