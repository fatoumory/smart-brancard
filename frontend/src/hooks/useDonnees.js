// src/hooks/useDonnees.js
import { useCallback, useEffect, useState } from "react";
import { abonner } from "../services/tempsReel";

// Plusieurs changements arrivent souvent ensemble (une mission proposée change aussi le statut
// de l'agent) : on attend ce court délai pour ne recharger qu'une fois
const REGROUPEMENT_MS = 300;

/**
 * Charge des données depuis le backend et les garde à jour.
 * @param {() => Promise<any>} chargeur fonction stable (définie hors du composant ou avec useCallback)
 * @param {number} [intervalleMs] si fourni, recharge aussi à cet intervalle (secours si le temps réel est coupé)
 * @param {string[]} [sujets] sujets du temps réel qui déclenchent un rechargement
 *   ("missions", "agents", "alertes", "graphe" : voir backend/services/temps_reel.py)
 * @returns {{ donnees, erreur, chargement, misAJourA, recharger }}
 */
export function useDonnees(chargeur, intervalleMs, sujets) {
  const [etat, setEtat] = useState({ donnees: null, erreur: null, chargement: true, misAJourA: null });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    // Ignore la réponse si le composant a changé de données entre-temps
    let actif = true;
    chargeur().then(
      (donnees) => actif && setEtat({ donnees, erreur: null, chargement: false, misAJourA: new Date() }),
      (e) => actif && setEtat((p) => ({ ...p, erreur: e.message, chargement: false })),
    );
    return () => { actif = false; };
  }, [chargeur, version]);

  // Rafraîchissement périodique : filet de sécurité si le WebSocket est coupé
  useEffect(() => {
    if (!intervalleMs) return undefined;
    const minuteur = setInterval(() => setVersion((v) => v + 1), intervalleMs);
    return () => clearInterval(minuteur);
  }, [intervalleMs]);

  // Temps réel : rechargement dès que le serveur annonce un changement d'un de ces sujets.
  // La liste est transformée en texte pour que l'effet ne se relance pas à chaque affichage.
  const cleSujets = sujets?.join(",") ?? "";
  useEffect(() => {
    if (!cleSujets) return undefined;
    const voulus = cleSujets.split(",");
    let minuteur = null;
    const desabonner = abonner((recus) => {
      if (!recus.some((s) => voulus.includes(s))) return;
      clearTimeout(minuteur);
      minuteur = setTimeout(() => setVersion((v) => v + 1), REGROUPEMENT_MS);
    });
    return () => {
      clearTimeout(minuteur);
      desabonner();
    };
  }, [cleSujets]);

  const recharger = useCallback(() => {
    setEtat((p) => ({ ...p, chargement: true }));
    setVersion((v) => v + 1);
  }, []);

  return { ...etat, recharger };
}
