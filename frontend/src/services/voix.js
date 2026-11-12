// src/services/voix.js
// Annonces au brancardier, les mains sur le brancard : sonnerie, vibration et voix en français.
// Tout est fait par le navigateur, gratuitement et sans Internet :
//   - sonnerie : quelques bips produits par l'API Web Audio (aucun fichier son à télécharger) ;
//   - vibration : navigator.vibrate (Android ; l'iPhone ne vibre pas depuis une application web) ;
//   - voix : synthèse vocale du navigateur (speechSynthesis), en français.
// Le navigateur bloque le son tant que l'utilisateur n'a pas touché l'écran : le bouton
// « Activer le son » (voir components/brancardier/ActiverSon.jsx) le débloque une fois par ouverture.

import { MATERIELS, URGENCES } from "./referentiel";

let contexteAudio = null;
let sonActive = false;
const ecouteurs = new Set();

/** Le son a-t-il été débloqué par un toucher depuis l'ouverture de l'application ? */
export function estSonActive() {
  return sonActive;
}

/** Suit l'activation du son (bandeau « Activer le son ») ; renvoie la fonction de désabonnement */
export function suivreSon(rappel) {
  ecouteurs.add(rappel);
  return () => ecouteurs.delete(rappel);
}

/** À appeler depuis un toucher (clic) : débloque la sonnerie et la voix pour la suite */
export function activerSon() {
  try {
    const Contexte = window.AudioContext ?? window.webkitAudioContext;
    if (Contexte && !contexteAudio) contexteAudio = new Contexte();
    contexteAudio?.resume();
  } catch {
    // Web Audio indisponible : la voix et la vibration restent possibles
  }
  sonActive = true;
  ecouteurs.forEach((f) => f(true));
  parler("Son activé. Vous serez prévenu à chaque nouvelle mission.");
}

/** Sonnerie courte : trois bips montants, comme un bip d'appel */
export function sonnerie() {
  if (!contexteAudio) return;
  const debut = contexteAudio.currentTime;
  [660, 880, 1100].forEach((frequence, i) => {
    const oscillateur = contexteAudio.createOscillator();
    const volume = contexteAudio.createGain();
    oscillateur.type = "sine";
    oscillateur.frequency.value = frequence;
    // Le volume monte puis redescend vite : pas de « clic » au début et à la fin du bip
    const t = debut + i * 0.22;
    volume.gain.setValueAtTime(0.0001, t);
    volume.gain.exponentialRampToValueAtTime(0.4, t + 0.02);
    volume.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
    oscillateur.connect(volume).connect(contexteAudio.destination);
    oscillateur.start(t);
    oscillateur.stop(t + 0.2);
  });
}

/** Vibration (Android) ; motif en millisecondes : vibration, pause, vibration... */
export function vibrer(motif = [400, 150, 400]) {
  navigator.vibrate?.(motif);
}

/** Lit un texte à voix haute en français ; une annonce en cours est remplacée par la nouvelle */
export function parler(texte) {
  const synthese = window.speechSynthesis;
  if (!synthese || !texte) return;
  synthese.cancel();
  const phrase = new SpeechSynthesisUtterance(texte);
  phrase.lang = "fr-FR";
  phrase.rate = 0.95;   // un peu plus lent : compréhensible dans un couloir bruyant
  // Une voix française installée sur l'appareil, si elle existe
  const voixFrancaise = synthese.getVoices().find((v) => v.lang?.toLowerCase().startsWith("fr"));
  if (voixFrancaise) phrase.voice = voixFrancaise;
  synthese.speak(phrase);
}

/** Texte lu à l'arrivée d'une mission : urgence, patient, trajet, matériel */
export function texteAnnonce(mission) {
  const urgence = URGENCES[mission.niveau_urgence]?.libelle ?? "";
  const materiel = mission.materiel_requis && mission.materiel_requis !== "RIEN"
    ? ` Matériel : ${MATERIELS[mission.materiel_requis]?.libelle}, ${mission.materiel_deja_dispo ? "déjà auprès du patient" : "à prendre au dépôt"}.`
    : "";
  return `Nouvelle mission, urgence ${urgence.toLowerCase()}. Patient ${mission.patient_prenom} ${mission.patient_nom}.`
    + ` De ${mission.noeud_source_nom} vers ${mission.noeud_destination_nom}.${materiel}`;
}

/** Nouvelle mission proposée : sonnerie, vibration, puis l'annonce vocale */
export function annoncerMission(mission) {
  sonnerie();
  vibrer();
  // La voix commence après la sonnerie
  setTimeout(() => parler(texteAnnonce(mission)), 750);
}
