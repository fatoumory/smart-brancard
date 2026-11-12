// src/hooks/useTempsReel.js
import { useEffect, useState } from "react";
import { suivreConnexion } from "../services/tempsReel";

/** true quand la connexion temps réel (WebSocket) est ouverte */
export function useTempsReelConnecte() {
  const [connecte, setConnecte] = useState(false);
  useEffect(() => suivreConnexion(setConnecte), []);
  return connecte;
}
