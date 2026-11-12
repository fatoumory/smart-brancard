// Appels au backend propres au brancardier connecté

import { apiFetch } from "./api";
import { envoyerAction, lireMission } from "./horsLigne";

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
    // Sans réseau : la mission gardée sur le téléphone (mode hors ligne)
    return lireMission("/missions/moi");
}

/** Accepte la mission proposée : elle passe ACCEPTE, l'agent rejoint le point de départ */
export function accepterMission(id) {
    return envoyerAction(`/missions/${id}/accept`, "PUT", {}, (m) => ({ ...m, statut: "ACCEPTE" }));
}

/** Refuse la mission proposée avec un motif obligatoire (clé de MOTIFS_REFUS) :
 *  elle repart vers un autre agent ou, pour du matériel défectueux, vers le régulateur */
export function refuserMission(id, motif) {
    // Sans réseau : la mission quitte l'écran, le refus part au retour du réseau
    return envoyerAction(`/missions/${id}/refuse`, "PUT", { motif }, () => null);
}

/** Prise en charge au point de départ -> la mission passe EN_TRANSIT.
 *  corps : { code_bracelet } seul quand le badge a prouvé la présence au départ (mission.agent_au_depart),
 *  { tag_nfc, code_bracelet } en secours (tag de la salle + QR du bracelet du patient),
 *  ou { forcer_urgence: true } pour partir sans scan, réservé aux missions URGENT (tracé dans le journal) */
export function scannerDepart(id, corps) {
    // Sans réseau : le patient est transporté, le scan sera vérifié par le serveur au retour du réseau
    return envoyerAction(`/missions/${id}/scan-depart`, "POST", corps, (m) => ({ ...m, statut: "EN_TRANSIT" }));
}

/** Arrivée : tag NFC de la salle de destination -> la mission passe TERMINE, l'agent redevient disponible */
export function scannerArrivee(id, tagNfc) {
    return envoyerAction(`/missions/${id}/scan-arrivee`, "POST", { tag_nfc: tagNfc }, () => null);
}

/** Bouton « Arrivé » (secours) : l'agent déclare l'arrivée quand elle n'a pas été détectée par son badge.
 *  La mission passe TERMINE (méthode MANUEL au journal) et l'agent redevient disponible */
export function declarerArrivee(id) {
    return envoyerAction(`/missions/${id}/arrivee`, "POST", {}, () => null);
}

/** Appel du régulateur pendant une mission (bracelet illisible, échecs de scan...) :
 *  raison = "BRACELET_ILLISIBLE" | "ECHECS_SCAN" | "AUTRE" ; une alerte s'affiche sur son dashboard */
export function appelerRegulateur(id, raison) {
    return envoyerAction(`/missions/${id}/appel-regulateur`, "POST", { raison });
}

/** Missions terminées par l'agent aujourd'hui, de la plus récente à la plus ancienne (onglet Journal) */
export function getMonJournal() {
    return apiFetch("/missions/moi/journal");
}

/** Dernière position connue de l'agent : { noeud_id, noeud_nom, date_heure } ; null s'il n'a jamais été détecté */
export function getMaPosition() {
    return apiFetch("/detections/me");
}
