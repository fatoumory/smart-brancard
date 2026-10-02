// src/config.js
// Réglages lus depuis les variables d'environnement Vite (fichier frontend/.env.local, non versionné)

// Adresse du backend FastAPI
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
