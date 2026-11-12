// Appels au backend propres au brancardier connecté

import { apiFetch } from "./api";

/** Profil du brancardier connecté : { id, prenom, nom, statut, compteur_mission, ... } */
export function getMonProfil() {
    return apiFetch("/auth/me");
}

/** Change le statut du brancardier connecté : "DISPONIBLE", "EN_PAUSE" ou "INDISPONIBLE".
 *  Pour une pause, dureePauseMinutes (30 ou 45) : le serveur en déduit l'heure de fin (fin_pause)
 *  et remet lui-même l'agent disponible à la fin, même si l'application est fermée. */
export function changerMonStatut(statut, dureePauseMinutes) {
    return apiFetch("/utilisateurs/me/statut", {
        method: "PATCH",
        // La durée n'est envoyée que pour une pause
        json: { statut, ...(dureePauseMinutes && { duree_pause_minutes: dureePauseMinutes }) },
    });
}


/** Mission du brancardier connecté : proposée, acceptée ou en transit ; null s'il n'en a pas.
 *  Format : MissionOut (backend/schemas/mission.py), avec fin_reponse pour une mission proposée */
export function getMaMission() {
    return apiFetch("/missions/moi");
}

/** Accepte la mission proposée : elle passe ACCEPTE, l'agent rejoint le point de départ */
export function accepterMission(id) {
    return apiFetch(`/missions/${id}/accept`, { method: "PUT" });
}

/** Refuse la mission proposée avec un motif obligatoire (clé de MOTIFS_REFUS) :
 *  elle repart vers un autre agent ou, pour du matériel défectueux, vers le régulateur */
export function refuserMission(id, motif) {
    return apiFetch(`/missions/${id}/refuse`, { method: "PUT", json: { motif } });
}

/** Prise en charge au point de départ -> la mission passe EN_TRANSIT.
 *  corps : { code_bracelet } seul quand le badge a prouvé la présence au départ (mission.agent_au_depart),
 *  { tag_nfc, code_bracelet } en secours (tag de la salle + QR du bracelet du patient),
 *  ou { forcer_urgence: true } pour partir sans scan, réservé aux missions URGENT (tracé dans le journal) */
export function scannerDepart(id, corps) {
    return apiFetch(`/missions/${id}/scan-depart`, { method: "POST", json: corps });
}

/** Arrivée : tag NFC de la salle de destination -> la mission passe TERMINE, l'agent redevient disponible */
export function scannerArrivee(id, tagNfc) {
    return apiFetch(`/missions/${id}/scan-arrivee`, { method: "POST", json: { tag_nfc: tagNfc } });
}

/** Bouton « Arrivé » (secours) : l'agent déclare l'arrivée quand elle n'a pas été détectée par son badge.
 *  La mission passe TERMINE (méthode MANUEL au journal) et l'agent redevient disponible */
export function declarerArrivee(id) {
    return apiFetch(`/missions/${id}/arrivee`, { method: "POST" });
}

/** Appel du régulateur pendant une mission (bracelet illisible, échecs de scan...) :
 *  raison = "BRACELET_ILLISIBLE" | "ECHECS_SCAN" | "AUTRE" ; une alerte s'affiche sur son dashboard */
export function appelerRegulateur(id, raison) {
    return apiFetch(`/missions/${id}/appel-regulateur`, { method: "POST", json: { raison } });
}

/** Missions terminées par l'agent aujourd'hui, de la plus récente à la plus ancienne (onglet Journal) */
export function getMonJournal() {
    return apiFetch("/missions/moi/journal");
}

/** Dernière position connue de l'agent : { noeud_id, noeud_nom, date_heure } ; null s'il n'a jamais été détecté */
export function getMaPosition() {
    return apiFetch("/detections/me");
}
