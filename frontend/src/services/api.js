// src/services/api.js
// Point d'entrée unique vers le backend : ajoute le jeton JWT et traduit les erreurs HTTP

import { API_URL } from "../config";
import { logoutApi } from "./authService";

/**
 * Appelle une route protégée du backend et renvoie le JSON de la réponse.
 * @param {string} chemin ex : "/missions"
 * @param {RequestInit & { json?: object }} options `json` est envoyé comme corps JSON
 */
export async function apiFetch(chemin, { json, headers, ...options } = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${chemin}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${localStorage.getItem("token")}`,
        ...(json !== undefined && { "Content-Type": "application/json" }),
        ...headers,
      },
      body: json !== undefined ? JSON.stringify(json) : options.body,
    });
  } catch (error) {
    throw new Error("Impossible de contacter le serveur. Le backend est-il démarré ?", { cause: error });
  }

  // Jeton expiré ou compte désactivé : retour à l'écran de connexion
  if (response.status === 401) {
    logoutApi();
    window.location.assign("/login");
    throw new Error("Session expirée, veuillez vous reconnecter.");
  }

  if (!response.ok) {
    const corps = await response.json().catch(() => ({}));
    const erreur = new Error(messageErreur(corps.detail) ?? `Erreur serveur (${response.status}).`);
    erreur.status = response.status;
    erreur.detail = corps.detail;  // ex : la liste des patients semblables d'un conflit 409
    throw erreur;
  }

  return response.status === 204 ? null : response.json();
}

// FastAPI renvoie { detail: "texte" }, { detail: { message: "..." } } (erreur métier détaillée)
// ou { detail: [{ msg: "..." }] } (erreur de validation 422)
function messageErreur(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail[0]?.msg?.replace(/^Value error, /, "");
  return detail?.message;
}
