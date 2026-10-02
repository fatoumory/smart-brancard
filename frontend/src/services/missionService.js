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

/** Brancardiers avec leur statut et leur nombre de missions du jour (régulateur uniquement) */
export function listerBrancardiers() {
  return apiFetch("/utilisateurs?role=BRANCARDIER");
}
