// src/hooks/useDonnees.js
import { useCallback, useEffect, useState } from "react";

/**
 * Charge des données depuis le backend et les garde à jour.
 * @param {() => Promise<any>} chargeur fonction stable (définie hors du composant ou avec useCallback)
 * @param {number} [intervalleMs] si fourni, recharge automatiquement à cet intervalle
 * @returns {{ donnees, erreur, chargement, misAJourA, recharger }}
 */
export function useDonnees(chargeur, intervalleMs) {
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

  // Rafraîchissement périodique (en attendant les WebSockets du Sprint 4)
  useEffect(() => {
    if (!intervalleMs) return undefined;
    const minuteur = setInterval(() => setVersion((v) => v + 1), intervalleMs);
    return () => clearInterval(minuteur);
  }, [intervalleMs]);

  const recharger = useCallback(() => {
    setEtat((p) => ({ ...p, chargement: true }));
    setVersion((v) => v + 1);
  }, []);

  return { ...etat, recharger };
}
