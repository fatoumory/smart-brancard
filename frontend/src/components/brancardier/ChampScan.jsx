import { useEffect, useEffectEvent, useRef, useState } from "react";
import { Nfc, QrCode, X } from "lucide-react";
import { lireTagNfc, messageErreurNfc, nfcDisponible } from "../../services/nfc";

// Pause entre deux analyses d'image de la caméra : assez rapide pour l'agent, sans vider la batterie
const INTERVALLE_ANALYSE_MS = 200;
// Les images sont réduites à cette largeur avant analyse : un QR code reste lisible, et c'est plus rapide
const LARGEUR_ANALYSE = 480;

// Champ de code (tag NFC d'une salle ou bracelet QR du patient) avec ses boutons de lecture.
//   type="nfc" : bouton « Lire le tag NFC » si le téléphone le permet ; sinon, bouton de secours
//                par QR code (CDC §4.6 : démonstration sur un téléphone sans NFC)
//   type="qr"  : bouton « Scanner le QR code » (caméra)
// La saisie au clavier reste toujours possible : dernier recours si tag et QR sont illisibles.
function ChampScan({ id, libelle, exemple, valeur, onChange, type }) {
    // Lecture en cours : "nfc", "qr" ou null
    const [lecture, setLecture] = useState(null);
    const [erreur, setErreur] = useState("");
    // Permet d'arrêter l'attente d'un tag NFC (bouton Annuler, ou écran quitté)
    const annulationNfc = useRef(null);
    const nfc = type === "nfc" && nfcDisponible();

    // Écran quitté pendant une lecture NFC : on arrête d'écouter les tags
    useEffect(() => () => annulationNfc.current?.abort(), []);

    function codeLu(code) {
        onChange(code);
        setLecture(null);
        setErreur("");
    }

    async function lireNfc() {
        setErreur("");
        setLecture("nfc");
        const controleur = new AbortController();
        annulationNfc.current = controleur;
        try {
            codeLu(await lireTagNfc(controleur.signal));
        } catch (err) {
            if (err.name !== "AbortError") setErreur(messageErreurNfc(err));
            setLecture(null);
        } finally {
            // Un seul tag par lecture : le téléphone arrête d'écouter
            controleur.abort();
        }
    }

    function annuler() {
        annulationNfc.current?.abort();
        setLecture(null);
    }

    return (
        <div className="space-y-2">
            <label htmlFor={id} className="block">
                <span className="block text-sm font-semibold text-slate-700 mb-1">{libelle}</span>
                <input id={id} value={valeur} onChange={(e) => onChange(e.target.value)} required
                    placeholder={exemple} autoComplete="off" autoCapitalize="characters" spellCheck={false}
                    className="w-full h-12 px-4 rounded-xl border border-slate-300 font-mono uppercase placeholder:normal-case placeholder:font-sans focus:outline-none focus:ring-2 focus:ring-primaire" />
            </label>

            {/* Boutons de lecture, cachés pendant une lecture */}
            {!lecture && (
                <div className="flex gap-2">
                    {nfc && (
                        <button type="button" onClick={lireNfc}
                            className="flex-1 h-11 rounded-xl bg-primaire text-white text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer">
                            <Nfc className="w-5 h-5" /> Lire le tag NFC
                        </button>
                    )}
                    <button type="button" onClick={() => { setErreur(""); setLecture("qr"); }}
                        className={`flex-1 h-11 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer ${
                            nfc ? "bg-white border border-slate-300 text-slate-600" : "bg-primaire text-white"}`}>
                        <QrCode className="w-5 h-5" />
                        {type === "qr" ? "Scanner le QR code" : nfc ? "QR de secours" : "Secours : QR du tag"}
                    </button>
                </div>
            )}

            {/* Téléphone sans NFC : on explique pourquoi seul le QR est proposé */}
            {type === "nfc" && !nfc && !lecture && (
                <p className="text-xs text-slate-500">
                    NFC indisponible sur cet appareil (Chrome Android requis) : scannez le QR collé à côté du tag, ou tapez le code.
                </p>
            )}

            {lecture === "nfc" && (
                <div className="p-4 rounded-2xl bg-primaire-clair text-primaire flex items-center gap-3">
                    <Nfc className="w-8 h-8 shrink-0 animate-pulse" />
                    <p className="flex-1 text-sm font-semibold">Approchez le dos du téléphone du tag de la salle…</p>
                    <button type="button" onClick={annuler} className="text-sm font-medium text-slate-500 cursor-pointer">
                        Annuler
                    </button>
                </div>
            )}

            {lecture === "qr" && <LecteurQR onLu={codeLu} onFermer={() => setLecture(null)} />}

            {erreur && <p role="alert" className="text-sm text-red-700">{erreur}</p>}
        </div>
    );
}

// Caméra arrière du téléphone : analyse l'image jusqu'à trouver un QR code, puis s'arrête
function LecteurQR({ onLu, onFermer }) {
    const video = useRef(null);
    const [erreur, setErreur] = useState("");
    // useEffectEvent : appelle toujours la dernière version de onLu, sans relancer la caméra
    const transmettre = useEffectEvent((code) => onLu(code));

    useEffect(() => {
        let actif = true;
        let flux = null;
        let minuteur = null;

        async function demarrer() {
            // La caméra n'existe qu'en HTTPS (ou sur localhost)
            if (!navigator.mediaDevices?.getUserMedia) {
                setErreur("Caméra inaccessible : l'application doit être ouverte en HTTPS (npm run dev:mobile).");
                return;
            }
            try {
                flux = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
            } catch (err) {
                if (actif) setErreur(err.name === "NotAllowedError"
                    ? "Accès à la caméra refusé : autorisez-le dans les réglages du site."
                    : "Aucune caméra disponible sur cet appareil.");
                return;
            }
            // Écran fermé pendant la demande d'autorisation : on libère la caméra tout de suite
            if (!actif) {
                flux.getTracks().forEach((piste) => piste.stop());
                return;
            }
            video.current.srcObject = flux;
            await video.current.play().catch(() => {});

            // Le décodeur QR n'est téléchargé qu'au premier scan (il pèse plus que le reste de l'écran)
            const { default: jsQR } = await import("jsqr");
            const toile = document.createElement("canvas");
            const contexte = toile.getContext("2d", { willReadFrequently: true });

            function analyser() {
                if (!actif) return;
                const v = video.current;
                if (v.readyState >= v.HAVE_CURRENT_DATA && v.videoWidth > 0) {
                    const echelle = Math.min(1, LARGEUR_ANALYSE / v.videoWidth);
                    toile.width = Math.round(v.videoWidth * echelle);
                    toile.height = Math.round(v.videoHeight * echelle);
                    contexte.drawImage(v, 0, 0, toile.width, toile.height);
                    const image = contexte.getImageData(0, 0, toile.width, toile.height);
                    const qr = jsQR(image.data, image.width, image.height, { inversionAttempts: "dontInvert" });
                    if (qr?.data) {
                        actif = false;
                        navigator.vibrate?.(80);   // petit retour au toucher : le code est lu
                        transmettre(qr.data.trim());
                        return;
                    }
                }
                minuteur = setTimeout(analyser, INTERVALLE_ANALYSE_MS);
            }
            analyser();
        }

        demarrer();
        // Fermeture : arrêt de l'analyse et extinction de la caméra (le voyant s'éteint)
        return () => {
            actif = false;
            clearTimeout(minuteur);
            flux?.getTracks().forEach((piste) => piste.stop());
        };
    }, []);

    return (
        <div className="relative rounded-2xl overflow-hidden bg-slate-900">
            {erreur ? (
                <p role="alert" className="p-5 text-sm text-white">{erreur}</p>
            ) : (
                <>
                    {/* playsInline + muted : sinon iPhone ouvre la vidéo en plein écran */}
                    <video ref={video} playsInline muted className="w-full aspect-square object-cover" />
                    {/* Viseur : cadre au centre de l'image */}
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="w-3/5 aspect-square rounded-2xl border-4 border-white/80" />
                    </div>
                    <p className="absolute bottom-3 inset-x-0 text-center text-sm font-semibold text-white">
                        Placez le QR code dans le cadre
                    </p>
                </>
            )}
            <button type="button" onClick={onFermer} aria-label="Fermer la caméra"
                className="absolute top-3 right-3 w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center cursor-pointer">
                <X className="w-5 h-5" />
            </button>
        </div>
    );
}

export default ChampScan;
