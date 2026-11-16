// src/services/horsLigne.js
// Mode hors ligne simple du brancardier (ascenseur, sous-sol : le téléphone perd le réseau).
//   - La mission en cours est gardée sur le téléphone : elle reste affichée sans réseau.
//     Seule celle-ci est gardée, et elle est effacée à la déconnexion (CDC §7.2 : pas de données
//     patients qui traînent sur le terminal).
//   - Une action faite sans réseau (accepter, scanner, « Arrivé »...) est mise en attente avec son
//     heure réelle (horodatage_client), puis envoyée au retour du réseau, dans l'ordre.
//     Le serveur vérifie cette heure et ne compte jamais deux fois une action déjà enregistrée.
//   - Une action devenue impossible entre-temps (mission réaffectée, trop ancienne) est abandonnée
//     et l'agent en est prévenu.

import { apiFetch } from "./api";

const CLE_FILE = "actions_en_attente";
const CLE_MISSION = "mission_en_cours";
// Tant que des actions attendent, nouvel essai d'envoi à cet intervalle
const INTERVALLE_ESSAI_MS = 15000;

// État partagé, suivi par le bandeau « Réseau coupé »
let reseauCoupe = typeof navigator !== "undefined" && navigator.onLine === false;
let abandonnees = [];
const ecouteurs = new Set();
let envoiEnCours = false;

function lire(cle, defaut) {
  try {
    return JSON.parse(localStorage.getItem(cle)) ?? defaut;
  } catch {
    return defaut;
  }
}

function ecrire(cle, valeur) {
  try {
    if (valeur === null) localStorage.removeItem(cle);
    else localStorage.setItem(cle, JSON.stringify(valeur));
  } catch {
    // stockage refusé : la file reste vide, les actions échouent comme avant
  }
}

function prevenir() {
  const etat = etatHorsLigne();
  ecouteurs.forEach((f) => f(etat));
}

function noterReseau(coupe) {
  if (reseauCoupe === coupe) return;
  reseauCoupe = coupe;
  prevenir();
}

/** { reseauCoupe, enAttente (nombre d'actions), abandonnees (messages) } */
export function etatHorsLigne() {
  return { reseauCoupe, enAttente: lire(CLE_FILE, []).length, abandonnees };
}

/** Suit l'état hors ligne ; renvoie la fonction de désabonnement */
export function suivreHorsLigne(rappel) {
  ecouteurs.add(rappel);
  rappel(etatHorsLigne());
  return () => ecouteurs.delete(rappel);
}

/** L'agent a lu le message des actions abandonnées */
export function oublierAbandonnees() {
  abandonnees = [];
  prevenir();
}

//  Mission gardée sur le téléphone

/** Dernière mission connue (affichée sans réseau), ou null */
export function missionGardee() {
  return lire(CLE_MISSION, null);
}

/** Garde la mission en cours ; null l'efface (mission terminée, refusée, déconnexion) */
export function garderMission(mission) {
  ecrire(CLE_MISSION, mission ?? null);
}

/** Efface tout ce que le mode hors ligne garde sur le téléphone (déconnexion) */
export function effacerHorsLigne() {
  ecrire(CLE_MISSION, null);
  ecrire(CLE_FILE, null);
  abandonnees = [];
}

/** Lecture de la mission : en ligne, elle est gardée ; sans réseau, la mission gardée est renvoyée */
export async function lireMission(chemin) {
  try {
    const mission = await apiFetch(chemin);
    noterReseau(false);
    // Des actions attendent : la mission gardée (déjà avancée sur le téléphone) reste la référence
    if (lire(CLE_FILE, []).length === 0) garderMission(mission);
    return lire(CLE_FILE, []).length === 0 ? mission : missionGardee();
  } catch (err) {
    if (!err.reseau) throw err;
    noterReseau(true);
    return missionGardee();
  }
}

/**
 * Envoie une action de l'agent. Sans réseau, elle est mise en attente avec son heure réelle.
 * @param {string} chemin ex : "/missions/12/accept"
 * @param {string} methode "PUT" | "POST"
 * @param {object} corps corps JSON de l'action
 * @param {(mission) => object|null} effetLocal ce que devient la mission gardée si l'action est
 *   mise en attente (ex : statut ACCEPTE) ; null : la mission est terminée ou quittée
 * @returns la réponse du serveur, ou { ...mission modifiée, horsLigne: true } si l'action attend
 */
export async function envoyerAction(chemin, methode, corps, effetLocal) {
  try {
    const reponse = await apiFetch(chemin, { method: methode, json: corps });
    noterReseau(false);
    return reponse;
  } catch (err) {
    if (!err.reseau) throw err;
    // Sans réseau : l'action est gardée avec l'heure à laquelle l'agent l'a faite
    const file = lire(CLE_FILE, []);
    file.push({ chemin, methode, corps: { ...corps, horodatage_client: new Date().toISOString() } });
    ecrire(CLE_FILE, file);
    const avant = missionGardee();
    const apres = avant && effetLocal ? effetLocal(avant) : avant;
    // La confirmation affichée (ex : mission terminée) part de la mission avant son effacement
    garderMission(apres);
    reseauCoupe = true;
    prevenir();
    return { ...(apres ?? avant), horsLigne: true };
  }
}

/** Envoie les actions en attente, dans l'ordre où l'agent les a faites */
export async function envoyerActionsEnAttente() {
  if (envoiEnCours) return;
  envoiEnCours = true;
  try {
    let file = lire(CLE_FILE, []);
    while (file.length > 0) {
      const [action, ...reste] = file;
      try {
        await apiFetch(action.chemin, { method: action.methode, json: action.corps });
      } catch (err) {
        // Toujours pas de réseau : on réessaiera plus tard, la file est gardée telle quelle
        if (err.reseau) {
          noterReseau(true);
          return;
        }
        // Refus du serveur (mission réaffectée, annulée, action trop ancienne...) : action abandonnée
        abandonnees = [...abandonnees, err.message];
      }
      file = reste;
      ecrire(CLE_FILE, file);
    }
    // Tout est parti : la mission gardée sera remplacée par celle du serveur à la prochaine lecture
    noterReseau(false);
  } finally {
    envoiEnCours = false;
    prevenir();
  }
}

/** Démarre les envois automatiques : retour du réseau, et nouvel essai toutes les 15 s.
 *  Renvoie la fonction d'arrêt (page du brancardier quittée). */
export function demarrerEnvoisAutomatiques() {
  const auRetour = () => envoyerActionsEnAttente();
  const coupure = () => noterReseau(true);
  window.addEventListener("online", auRetour);
  window.addEventListener("offline", coupure);
  const minuteur = setInterval(() => {
    if (lire(CLE_FILE, []).length > 0) envoyerActionsEnAttente();
  }, INTERVALLE_ESSAI_MS);
  envoyerActionsEnAttente();
  return () => {
    window.removeEventListener("online", auRetour);
    window.removeEventListener("offline", coupure);
    clearInterval(minuteur);
  };
}
