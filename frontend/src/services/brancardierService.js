// Appels au backend propres au brancardier connecté

import { apiFetch } from "./api";

/** Profil du brancardier connecté : { id, prenom, nom, statut, compteur_mission, ... } */
export function getMonProfil() {
    return apiFetch("/auth/me");
}

/** Change le statut du brancardier connecté : "DISPONIBLE", "EN_PAUSE" ou "INDISPONIBLE".
 *  Pour une pause, dureePauseMinutes (15 ou 45) : le serveur en déduit l'heure de fin (fin_pause)
 *  et remet lui-même l'agent disponible à la fin, même si l'application est fermée. */
export function changerMonStatut(statut, dureePauseMinutes) {
    return apiFetch("/utilisateurs/me/statut", {
        method: "PATCH",
        // La durée n'est envoyée que pour une pause
        json: { statut, ...(dureePauseMinutes && { duree_pause_minutes: dureePauseMinutes }) },
    });
}

