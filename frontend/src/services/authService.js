// src/services/authService.js

import { API_URL } from "../config";

/**
 * Envoie les identifiants au backend et stocke le token JWT en cas de succès.
 * @param {string} email 
 * @param {string} password 
 * @returns {Promise<object>} Les données de réponse du backend
 */
export async function loginApi(email, password) {
  try {
    // FastAPI OAuth2PasswordRequestForm attend du Form Data (username/password)
    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);

    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData,
    });

    // Tâche 3.3 : Gestion des erreurs HTTP (400, 401, 422, etc.)
    if (!response.ok) {
      if (response.status === 401 || response.status === 400) {
        throw new Error("Identifiant ou mot de passe incorrect.");
      }
      throw new Error(`Erreur serveur (${response.status}). Veuillez réessayer.`);
    }

    const data = await response.json();

    // Tâche 3.2 : Extraction et sauvegarde du JWT dans le localStorage
    if (!data.access_token || !data.role) {
      throw new Error("Jeton d'accès manquant dans la réponse du serveur.");
    }
    // Le backend renvoie le rôle en majuscules (ex : "REGULATEUR") ;
    // le frontend l'utilise en minuscules pour ses routes (/regulateur)
    const role = data.role.toLowerCase();
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("role", role);

    return { ...data, role };
  } catch (error) {
    // Tâche 3.3 : Prise en compte du cas où le backend n'est pas démarré (Failed to fetch)
    if (error.name === "TypeError" && error.message.includes("fetch")) {
      throw new Error("Impossible de contacter le serveur. Le backend est-il démarré ?", { cause: error });
    }
    throw error;
  }
}

/**
 * Connexion du brancardier par sa carte : le code lu dans le QR de la carte est échangé
 * contre le même jeton de 8 h que le mot de passe (POST /auth/carte).
 * @param {string} code ex : "SBC-..." (le serveur n'en garde que l'empreinte)
 * @returns {Promise<object>} { access_token, role } avec le rôle en minuscules
 */
export async function loginCarte(code) {
  let response;
  try {
    response = await fetch(`${API_URL}/auth/carte`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
  } catch (error) {
    throw new Error("Impossible de contacter le serveur. Le backend est-il démarré ?", { cause: error });
  }
  // 401 : carte inconnue ou remplacée par une nouvelle ; 403 : compte désactivé
  if (response.status === 401) throw new Error("Carte non reconnue : elle a peut-être été remplacée. Voyez le régulateur.");
  if (response.status === 403) throw new Error("Ce compte est désactivé. Voyez le régulateur.");
  if (!response.ok) throw new Error(`Erreur serveur (${response.status}). Veuillez réessayer.`);

  const data = await response.json();
  const role = data.role.toLowerCase();
  localStorage.setItem("token", data.access_token);
  localStorage.setItem("role", role);
  return { ...data, role };
}

/**
 * Déconnecte l'utilisateur : purge le token et le rôle (aucune trace sur le terminal)
 */
export function logoutApi() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
  // Mission gardée et actions en attente du mode hors ligne (services/horsLigne.js) :
  // rien ne doit rester sur un téléphone partagé après la déconnexion (CDC §7.2)
  localStorage.removeItem("mission_en_cours");
  localStorage.removeItem("actions_en_attente");
}

/**
 * Récupère le jeton JWT stocké
 */
export function getToken() {
  return localStorage.getItem("token");
}

/**
 * Récupère le rôle de l'utilisateur connecté ("regulateur" / "brancardier" / "medecin")
 */
export function getRole() {
  return localStorage.getItem("role");
}

/**
 * Lit les informations contenues dans le jeton JWT (id, rôle, nom, prénom, expiration).
 * Renvoie null si aucun jeton n'est stocké ou s'il est mal formé.
 */
export function lireJeton() {
  const token = getToken();
  if (!token) return null;
  try {
    // Le payload du JWT est la 2e partie, encodée en base64url (UTF-8 pour les accents)
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const octets = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    return JSON.parse(new TextDecoder().decode(octets));
  } catch {
    return null;
  }
}

/**
 * Indique si un token valide et non expiré est stocké.
 * Un token expiré (au-delà des 8h de garde) est purgé automatiquement.
 */
export function estAuthentifie() {
  const payload = lireJeton();
  if (payload && payload.exp * 1000 > Date.now()) return true;
  logoutApi();
  return false;
}
