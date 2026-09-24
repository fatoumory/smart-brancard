// src/services/authService.js

const API_URL = "http://localhost:8000"; // Adapte le port si ton backend tourne sur un autre port

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
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("role", data.role);

    return data;
  } catch (error) {
    // Tâche 3.3 : Prise en compte du cas où le backend n'est pas démarré (Failed to fetch)
    if (error.name === "TypeError" && error.message.includes("fetch")) {
      throw new Error("Impossible de contacter le serveur. Le backend est-il démarré ?", { cause: error });
    }
    throw error;
  }
}

/**
 * Déconnecte l'utilisateur : purge le token et le rôle (aucune trace sur le terminal)
 */
export function logoutApi() {
  localStorage.removeItem("token");
  localStorage.removeItem("role");
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
 * Indique si un token valide et non expiré est stocké.
 * Un token expiré (au-delà des 8h de garde) est purgé automatiquement.
 */
export function estAuthentifie() {
  const token = getToken();
  if (!token) return false;
  try {
    // Le payload du JWT est la 2e partie, encodée en base64url
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    if (payload.exp * 1000 > Date.now()) return true;
  } catch {
    // token mal formé : on le traite comme invalide
  }
  logoutApi();
  return false;
}
