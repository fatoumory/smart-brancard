// src/services/tempsReel.js
// Temps réel : une seule connexion WebSocket (/ws) partagée par tous les écrans de l'application.
// Le serveur n'envoie que le « sujet » qui a changé ({ type: "maj", sujets: ["missions"] }) :
// chaque écran recharge alors ses données par les routes habituelles (voir hooks/useDonnees.js).
// Si la connexion tombe (réseau, serveur redémarré), elle est rouverte automatiquement ;
// en attendant, les écrans continuent de se recharger à intervalle régulier.

import { API_URL } from "../config";
import { getToken } from "./authService";

// Attente avant de rouvrir une connexion perdue : 1 s, 2 s, 4 s... jusqu'à 30 s
const ATTENTE_MIN_MS = 1000;
const ATTENTE_MAX_MS = 30000;
// « ping » régulier : certains proxys ferment une connexion restée muette
const INTERVALLE_PING_MS = 25000;

// Abonnés : fonction appelée avec la liste des sujets reçus
const abonnes = new Set();
// Écouteurs de l'état de la connexion (bandeau « temps réel » du dashboard)
const ecouteursEtat = new Set();

let socket = null;
let connecte = false;
let attenteMs = ATTENTE_MIN_MS;
let minuteurReconnexion = null;
let minuteurPing = null;

/** Adresse du WebSocket, déduite de celle de l'API :
 *  http://localhost:8000 -> ws://localhost:8000/ws ; /api (mode mobile, proxy) -> wss://<site>/api/ws */
function adresseWebSocket() {
  const base = new URL(API_URL, window.location.href);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  return `${base.href.replace(/\/$/, "")}/ws`;
}

function changerEtat(valeur) {
  connecte = valeur;
  ecouteursEtat.forEach((f) => f(valeur));
}

function ouvrir() {
  const jeton = getToken();
  // Pas connecté à l'application, ou plus personne n'écoute : rien à ouvrir
  if (!jeton || abonnes.size === 0 || socket) return;

  // ws : cette connexion-ci. Une ancienne connexion, fermée entre-temps (écran quitté puis rouvert),
  // peut encore recevoir des événements : ils sont ignorés, pour ne pas toucher à la nouvelle.
  const ws = new WebSocket(adresseWebSocket());
  socket = ws;

  // 1er message : le jeton (il n'est pas mis dans l'adresse, qui apparaît dans les journaux du serveur)
  ws.onopen = () => ws.send(JSON.stringify({ jeton }));

  ws.onmessage = (evenement) => {
    if (socket !== ws) return;
    let message;
    try {
      message = JSON.parse(evenement.data);
    } catch {
      return;
    }
    if (message.type === "connecte") {
      attenteMs = ATTENTE_MIN_MS;
      changerEtat(true);
      clearInterval(minuteurPing);
      minuteurPing = setInterval(() => ws.readyState === WebSocket.OPEN && ws.send("ping"), INTERVALLE_PING_MS);
    } else if (message.type === "maj") {
      abonnes.forEach((f) => f(message.sujets));
    }
  };

  ws.onclose = (evenement) => {
    if (socket !== ws) return;   // ancienne connexion : la nouvelle continue
    socket = null;
    clearInterval(minuteurPing);
    changerEtat(false);
    // 4401 : jeton refusé (expiré, compte désactivé) : inutile d'insister
    if (evenement.code === 4401 || abonnes.size === 0) return;
    minuteurReconnexion = setTimeout(ouvrir, attenteMs);
    attenteMs = Math.min(attenteMs * 2, ATTENTE_MAX_MS);
  };
}

function fermerSiPlusPersonne() {
  if (abonnes.size > 0) return;
  clearTimeout(minuteurReconnexion);
  clearInterval(minuteurPing);
  const ancien = socket;
  socket = null;
  ancien?.close();
  changerEtat(false);
}

/** S'abonne aux changements : rappel(sujets) à chaque message. Renvoie la fonction de désabonnement. */
export function abonner(rappel) {
  abonnes.add(rappel);
  ouvrir();
  return () => {
    abonnes.delete(rappel);
    fermerSiPlusPersonne();
  };
}

/** Suit l'état de la connexion : rappel(true | false). Renvoie la fonction de désabonnement. */
export function suivreConnexion(rappel) {
  ecouteursEtat.add(rappel);
  rappel(connecte);
  return () => ecouteursEtat.delete(rappel);
}

/** Déconnexion de l'application : la connexion temps réel est fermée */
export function fermerTempsReel() {
  abonnes.clear();
  fermerSiPlusPersonne();
}
