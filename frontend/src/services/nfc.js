// src/services/nfc.js
// Lecture des tags NFC muraux avec Web NFC (CDC §4.6).
// Web NFC n'existe que dans Chrome sur Android, et seulement en HTTPS (npm run dev:mobile pour tester).

/** true si le téléphone et le navigateur savent lire un tag NFC */
export function nfcDisponible() {
    return typeof window !== "undefined" && "NDEFReader" in window;
}

/**
 * Attend qu'un tag soit approché du téléphone et renvoie son code.
 * Le code est le premier enregistrement texte du tag (ex : "NFC-RDC-URG") ;
 * si le tag n'en contient pas, on renvoie son numéro de série.
 * @param {AbortSignal} signal permet d'annuler l'attente (bouton « Annuler »)
 * @returns {Promise<string>}
 */
export async function lireTagNfc(signal) {
    const lecteur = new window.NDEFReader();
    // Demande l'autorisation NFC la première fois, puis active la lecture
    await lecteur.scan({ signal });

    return new Promise((resolve, reject) => {
        // Un tag a été lu
        lecteur.addEventListener("reading", ({ message, serialNumber }) => {
            const texte = message.records.find((r) => r.recordType === "text");
            if (texte) {
                resolve(new TextDecoder(texte.encoding || "utf-8").decode(texte.data).trim());
            } else {
                resolve(serialNumber);
            }
        }, { once: true });

        // Tag détecté mais illisible (éloigné trop tôt, format inconnu)
        lecteur.addEventListener("readingerror", () => {
            reject(new Error("Tag illisible : maintenez-le contre le dos du téléphone et réessayez."));
        }, { once: true });

        // Lecture annulée par l'agent
        signal.addEventListener("abort", () => {
            reject(new DOMException("Lecture annulée", "AbortError"));
        }, { once: true });
    });
}

/** Message compréhensible par l'agent pour une erreur Web NFC */
export function messageErreurNfc(erreur) {
    if (erreur.name === "NotAllowedError") return "Accès au NFC refusé : autorisez-le dans les réglages du site.";
    if (erreur.name === "NotReadableError" || erreur.name === "NotSupportedError") {
        return "NFC désactivé : activez-le dans les réglages du téléphone.";
    }
    return erreur.message;
}
