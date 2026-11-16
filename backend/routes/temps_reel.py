# routes/temps_reel.py
# WebSocket du temps réel : chaque écran ouvert (dashboard, mobile, suivi du médecin) s'y connecte
# et reçoit les sujets qui changent (voir services/temps_reel.py).

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from database import SessionLocal
from services.auth_service import utilisateur_du_jeton
from services.temps_reel import diffuseur

router = APIRouter(tags=["Temps réel"])

# Le navigateur doit s'identifier dans ce délai après l'ouverture, sinon la connexion est fermée
DELAI_IDENTIFICATION_S = 5

# Code de fermeture « non autorisé » (les codes 4000 à 4999 sont libres pour l'application)
FERMETURE_NON_AUTORISE = 4401


def identifier(jeton: str) -> bool:
    """Le jeton désigne-t-il un compte actif ? (même vérification que les routes HTTP)"""
    db = SessionLocal()
    try:
        return utilisateur_du_jeton(db, jeton) is not None
    finally:
        db.close()


#  Connexion d'un écran
# 1. L'écran ouvre ws://.../ws puis envoie {"jeton": "<son JWT>"} en premier message.
#    Le jeton n'est pas mis dans l'adresse : il apparaîtrait dans les journaux du serveur.
# 2. Le serveur répond {"type": "connecte"}, puis {"type": "maj", "sujets": [...]} à chaque changement.
# 3. L'écran peut envoyer « ping » de temps en temps pour garder la connexion ouverte.
@router.websocket("/ws")
async def temps_reel(websocket: WebSocket):
    await websocket.accept()
    try:
        premier = await asyncio.wait_for(websocket.receive_text(), timeout=DELAI_IDENTIFICATION_S)
        jeton = json.loads(premier).get("jeton", "")
    except (asyncio.TimeoutError, ValueError, AttributeError, WebSocketDisconnect):
        jeton = ""
    # La base est lue de façon bloquante : hors de la boucle asyncio
    if not jeton or not await asyncio.to_thread(identifier, jeton):
        try:
            await websocket.close(code=FERMETURE_NON_AUTORISE)
        except RuntimeError:
            pass  # le navigateur a déjà fermé
        return

    await diffuseur.connecter(websocket)
    try:
        await websocket.send_json({"type": "connecte"})
        while True:
            # Messages de l'écran (« ping ») : ignorés, ils servent seulement à garder la connexion
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        diffuseur.deconnecter(websocket)
