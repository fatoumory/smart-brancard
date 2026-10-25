// src/hooks/useBaliseSimulee.js
import { useEffect, useState } from "react";
import { getMaPosition, signalerPosition } from "../services/brancardierService";

// Une vraie balise BLE redétecte l'agent tant qu'il reste à portée : le lieu choisi est renvoyé
// toutes les 2 min. Le serveur considère une position de plus de 10 min comme périmée.
const INTERVALLE_BALISE_MS = 2 * 60 * 1000;

/**
 * Balise BLE simulée : position de l'agent envoyée au serveur (POST /detections).
 * Seul un lieu CHOISI par l'agent est renvoyé toutes les 2 min, tant que l'application est ouverte.
 * Une position reprise du serveur ou enregistrée par un scan n'est jamais renvoyée : si l'agent
 * se déplace sans la mettre à jour, elle devient périmée au bout de 10 min, et le serveur
 * ne le croit plus à côté (il passe après les agents localisés, sans être exclu).
 * À utiliser dans la page (et non dans un onglet) : l'envoi continue quel que soit l'onglet affiché.
 * @returns {{ lieu, choisir, apresScan, derniere, envoyeA, erreur }}
 */
export function useBaliseSimulee() {
  // id du lieu choisi par l'agent dans « Je suis à » : le seul qui est renvoyé (null sinon)
  const [lieu, setLieu] = useState(null);
  // Dernière position connue mais non confirmée par l'agent, affichée pour information :
  // { nom, date, origine: "scan" | "serveur" }
  const [derniere, setDerniere] = useState(null);
  // Heure du dernier envoi accepté par le serveur
  const [envoyeA, setEnvoyeA] = useState(null);
  const [erreur, setErreur] = useState("");

  // Ouverture de l'application : on affiche la dernière position connue du serveur, sans la renvoyer
  // (elle peut dater d'avant une pause ou de la veille).
  useEffect(() => {
    let actif = true;
    getMaPosition().then(
      (position) => {
        if (actif && position) setDerniere({ nom: position.noeud_nom, date: position.date_heure, origine: "serveur" });
      },
      () => {},   // sans position connue, l'agent la choisira lui-même
    );
    return () => { actif = false; };
  }, []);

  // Lieu choisi par l'agent : envoi immédiat, puis toutes les 2 min
  useEffect(() => {
    if (!lieu) return undefined;
    let actif = true;
    function envoyer() {
      signalerPosition(lieu).then(
        (detection) => { if (actif) { setEnvoyeA(detection.date_heure); setErreur(""); } },
        (err) => { if (actif) setErreur(err.message); },
      );
    }
    envoyer();
    const minuteur = setInterval(envoyer, INTERVALLE_BALISE_MS);
    return () => {
      actif = false;
      clearInterval(minuteur);
    };
  }, [lieu]);

  // L'agent indique où il est : c'est une position confirmée, renvoyée toutes les 2 min
  function choisir(id) {
    setLieu(id);
    setDerniere(null);
  }

  // Scan de départ ou d'arrivée réussi : le serveur a enregistré la salle scannée (position sûre).
  // On arrête de renvoyer l'ancien lieu choisi : l'agent va repartir ailleurs, et cette position
  // ne doit pas rester « fraîche » s'il ne la met pas à jour.
  function apresScan(nomSalle) {
    setLieu(null);
    setDerniere({ nom: nomSalle, date: new Date().toISOString(), origine: "scan" });
  }

  return { lieu, choisir, apresScan, derniere, envoyeA, erreur };
}
