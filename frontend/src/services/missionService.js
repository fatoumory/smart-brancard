// src/services/missionService.js
// Accès aux missions, aux patients, aux lieux de l'hôpital et aux brancardiers.
// Formats exacts : voir backend/schemas/mission.py, patient.py et graphe.py (Swagger : /docs).
//
//   Mission = { id, statut, niveau_urgence, materiel_requis, materiel_deja_dispo, consigne,
//               date_creation, patient_id, patient_ipp, patient_nom, patient_prenom,
//               prescripteur_id, brancardier_id, noeud_source_id, noeud_source_nom,
//               noeud_destination_id, noeud_destination_nom,
//               itineraire: [id des nœuds], itineraire_noms: [noms, même ordre], duree_estimee }

import { apiFetch } from "./api";

/** Lieux de l'hôpital ; typeNoeud = "SERVICE" pour les listes départ / arrivée */
export function listerNoeuds(typeNoeud) {
  return apiFetch(typeNoeud ? `/noeuds?type_noeud=${typeNoeud}` : "/noeuds");
}

/** Missions triées par urgence puis ancienneté (le médecin ne reçoit que les siennes) */
export function listerMissions() {
  return apiFetch("/missions?limite=500");
}

export function getMission(id) {
  return apiFetch(`/missions/${id}`);
}

/** Journal d'audit : une ligne par changement de statut, avec son horodatage */
export function getHistorique(id) {
  return apiFetch(`/missions/${id}/historique`);
}

/** { patient_id, noeud_source_id, noeud_destination_id, niveau_urgence,
 *    materiel_requis, materiel_deja_dispo, consigne } -> Mission */
export function creerMission(donnees) {
  return apiFetch("/missions/create", { method: "POST", json: donnees });
}

/** Recherche d'un patient admis, par nom, prénom ou IPP (2 caractères minimum) */
export function rechercherPatients(texte) {
  return apiFetch(`/patients?recherche=${encodeURIComponent(texte)}&limite=10`);
}

/** Admission d'un patient : l'IPP et le code du bracelet sont générés par le serveur.
 * { identite_inconnue, nom, prenom, date_naissance, sexe, confirmer_nouveau } -> Patient
 * Erreur 409 si un patient semblable existe : erreur.detail.patients_similaires */
export function admettrePatient(donnees) {
  return apiFetch("/patients", { method: "POST", json: donnees });
}

/** Identité confirmée d'un patient (remplace une identité provisoire) ; l'IPP et le bracelet ne changent pas.
 * { nom, prenom, date_naissance, sexe, confirmer_nouveau } -> Patient (409 comme l'admission) */
export function modifierIdentitePatient(id, donnees) {
  return apiFetch(`/patients/${id}`, { method: "PATCH", json: donnees });
}

/** Brancardiers avec leur statut et leur nombre de missions du jour (régulateur uniquement) */
export function listerBrancardiers() {
  return apiFetch("/utilisateurs?role=BRANCARDIER");
}

/** Régulateur : propose la mission au brancardier choisi (il doit être DISPONIBLE et devra accepter).
 *  Possible tant que le patient n'est pas en transport ; l'agent sollicité avant est libéré. */
export function reaffecterMission(id, brancardierId) {
  return apiFetch(`/missions/${id}/reaffecter`, { method: "PUT", json: { brancardier_id: brancardierId } });
}

/** Régulateur : annule la mission (statut ANNULE, gardée dans le journal) ; l'agent sollicité est libéré */
export function annulerMission(id) {
  return apiFetch(`/missions/${id}/annuler`, { method: "PUT" });
}

/** Régulateur : clôture d'une mission en transit dont l'arrivée n'a pas été détectée
 *  (badge muet, téléphone de l'agent éteint). Tracée au journal avec son nom ; l'agent redevient disponible */
export function cloturerMission(id) {
  return apiFetch(`/missions/${id}/cloturer`, { method: "PUT" });
}

/** État de la flotte : { sature, missions_en_attente, missions_en_retard, agents_disponibles, seuil, file } */
export function getSaturation() {
  return apiFetch("/missions/saturation");
}

/** Appels des agents au régulateur (bracelet illisible, échecs de scan...) ; traitee=false : à traiter */
export function listerAlertes(traitee) {
  return apiFetch(traitee === undefined ? "/alertes" : `/alertes?traitee=${traitee}`);
}

/** Le régulateur a pris en charge l'appel : l'alerte disparaît du dashboard */
export function traiterAlerte(id) {
  return apiFetch(`/alertes/${id}/traiter`, { method: "PUT" });
}

/** Passages de l'hôpital (couloirs, ascenseurs) avec leur état ouvert ou bloqué */
export function listerAretes() {
  return apiFetch("/aretes");
}

/** Bloque (panne, fermeture) ou rouvre un passage : les itinéraires suivants l'évitent */
export function bloquerArete(id, estBloque) {
  return apiFetch(`/aretes/${id}`, { method: "PATCH", json: { est_bloque: estBloque } });
}

/** Simulateur de badges (régulateur) : le récepteur de la salle noeudId a capté le badge de l'agent.
 *  C'est ce qu'enverrait un vrai récepteur ESP32 ; le serveur en déduit l'arrivée au départ,
 *  l'arrivée à destination (30 s de présence) et la sortie de la salle */
export function detecterBadge(brancardierId, noeudId) {
  return apiFetch("/detections/badge", { method: "POST", json: { brancardier_id: brancardierId, noeud_id: noeudId } });
}

/** Tous les comptes (régulateur) : médecins, régulateurs et brancardiers */
export function listerUtilisateurs() {
  return apiFetch("/utilisateurs");
}

/** Désactive (false) ou réactive (true) un compte ; il n'est jamais supprimé */
export function changerActivation(id, estActif) {
  return apiFetch(`/utilisateurs/${id}`, { method: "PATCH", json: { est_actif: estActif } });
}

/** Poste d'attente d'un brancardier (posteId null = aucun) et réservation aux URGENT.
 *  Un agent réservé ne reçoit que les missions URGENT (rapport Sprint 5, § 4.3) */
export function changerAffectation(id, posteId, reserveUrgent) {
  return apiFetch(`/utilisateurs/${id}/affectation`, {
    method: "PATCH", json: { poste_id: posteId, reserve_urgent: reserveUrgent },
  });
}

/** Nouvelle carte de connexion d'un brancardier : { utilisateur_id, prenom, nom, code }.
 *  Le code n'est donné qu'une fois (à imprimer en QR) ; l'ancienne carte ne fonctionne plus */
export function genererCarte(id) {
  return apiFetch(`/utilisateurs/${id}/carte`, { method: "POST" });
}
