// src/hooks/useBaliseSimulee.js
import { useEffect, useState } from "react";
import { getMaPosition, signalerPosition } from "../services/brancardierService";

// Une vraie balise BLE redétecte l'agent tant qu'il reste à portée : le lieu choisi est renvoyé
// toutes les 2 min. Le serveur considère une position de plus de 10 min comme périmée.
const INTERVALLE_BALISE_MS = 2 * 60 * 1000;

/**
 * Balise BLE simulée : position de l'agent, envoyée au serveur (POST /detections)
 * dès qu'elle change, puis toutes les 2 min tant que l'application est ouverte.
 * Sans elle, l'assignation ne peut pas choisir l'agent le plus proche (CDC §5.3)
 * et l'arrivée estimée n'est jamais calculée.
 * À utiliser dans la page (et non dans un onglet) : l'envoi continue quel que soit l'onglet affiché.
 * @returns {{ lieu, setLieu, envoyeA, erreur }}
 */
export function useBaliseSimulee() {
  // id du lieu où se trouve l'agent (null tant qu'il n'est pas connu)
  const [lieu, setLieu] = useState(null);
  // Heure du dernier envoi accepté par le serveur
  const [envoyeA, setEnvoyeA] = useState(null);
  const [erreur, setErreur] = useState("");

  // Ouverture de l'application : on repart de la dernière position connue du serveur.
  // Si l'agent a déjà choisi un lieu entre-temps, son choix est gardé.
  useEffect(() => {
    let actif = true;
    getMaPosition().then(
      (position) => { if (actif && position) setLieu((choisi) => choisi ?? position.noeud_id); },
      () => {},   // sans position connue, l'agent la choisira lui-même
    );
    return () => { actif = false; };
  }, []);

  // Envoi immédiat à chaque changement de lieu, puis toutes les 2 min
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

  return { lieu, setLieu, envoyeA, erreur };
}
