// src/services/referentiel.js
// Libellés et couleurs des valeurs communes au backend et au frontend.
// Les clés sont exactement les énumérations du backend (backend/models/enums.py).

import { Accessibility, Bed, Wind } from "lucide-react";

// Niveaux d'urgence, du plus au moins prioritaire, avec leur délai garanti (feuille de route, Sprint 5)
export const URGENCES = {
  URGENT: { libelle: "Urgent", delai: 3, ordre: 0,
    badge: "bg-red-50 text-red-700 border-red-300", delaiClasse: "bg-red-100 text-red-700" },
  HAUTE: { libelle: "Haute", delai: 8, ordre: 1,
    badge: "bg-orange-50 text-orange-700 border-orange-300", delaiClasse: "bg-orange-100 text-orange-700" },
  MOYENNE: { libelle: "Moyenne", delai: 15, ordre: 2,
    badge: "bg-blue-50 text-blue-700 border-blue-200", delaiClasse: "bg-blue-100 text-blue-700" },
  BASSE: { libelle: "Basse", delai: 30, ordre: 3,
    badge: "bg-slate-100 text-slate-600 border-slate-300", delaiClasse: "bg-slate-200 text-slate-600" },
};

// Statuts d'une mission (décision commune de la feuille de route)
export const STATUTS_MISSION = {
  EN_ATTENTE: { libelle: "En attente", classe: "bg-slate-100 text-slate-700" },
  PROPOSE: { libelle: "Proposé", classe: "bg-blue-50 text-blue-700" },
  EN_TRANSIT: { libelle: "En transit", classe: "bg-amber-50 text-amber-700" },
  TERMINE: { libelle: "Terminé", classe: "bg-emerald-50 text-emerald-700" },
  ANNULE: { libelle: "Annulé", classe: "bg-red-50 text-red-600" },
};

// Statuts d'un brancardier
export const STATUTS_AGENT = {
  DISPONIBLE: { libelle: "Disponible", point: "bg-emerald-600", texte: "text-emerald-700" },
  EN_MISSION: { libelle: "En mission", point: "bg-primaire", texte: "text-primaire" },
  EN_PAUSE: { libelle: "En pause", point: "bg-orange-600", texte: "text-orange-600" },
  INDISPONIBLE: { libelle: "Indisponible", point: "bg-slate-400", texte: "text-slate-400" },
};

// Matériel requis pour le transport
export const MATERIELS = {
  RIEN: { libelle: "Aucun", libelleFormulaire: "Aucun (mains vides)", icone: null },
  CHAISE_ROULANTE: { libelle: "Fauteuil roulant", libelleFormulaire: "Fauteuil roulant", icone: Accessibility },
  LIT_MEDICAL: { libelle: "Lit médicalisé", libelleFormulaire: "Lit médicalisé", icone: Bed },
  OXYGENE: { libelle: "Support O₂", libelleFormulaire: "Bouteille d'oxygène", icone: Wind },
};

/** Trie les missions par urgence, puis de la plus ancienne à la plus récente */
export function trierParPriorite(missions) {
  return [...missions].sort((a, b) =>
    URGENCES[a.niveau_urgence].ordre - URGENCES[b.niveau_urgence].ordre
    || new Date(a.date_creation) - new Date(b.date_creation));
}

/** "2026-09-26T15:11:00Z" -> "15:11" (heure locale) */
export function formaterHeure(dateIso) {
  return new Date(dateIso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}
