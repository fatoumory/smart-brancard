// Appels au backend propres au brancardier connecté

import { apiFetch } from "./api";

/** Profil du brancardier connecté : { id, prenom, nom, statut, compteur_mission, ... } */
export function getMonProfil() {
    return apiFetch("/auth/me");
}

/** Change le statut du brancardier connecté : "DISPONIBLE", "EN_PAUSE" ou "INDISPONIBLE" */
export function changerMonStatut(statut) {
    return apiFetch("/utilisateurs/me/statut", { method: "PATCH", json: { statut } });
}
