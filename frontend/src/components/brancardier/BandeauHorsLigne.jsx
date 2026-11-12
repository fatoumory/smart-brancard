import { useEffect, useState } from "react";
import { CloudUpload, TriangleAlert, WifiOff, X } from "lucide-react";
import { etatHorsLigne, oublierAbandonnees, suivreHorsLigne } from "../../services/horsLigne";

// Bandeau du mode hors ligne, en haut de l'application du brancardier :
//   - réseau coupé : la mission en cours reste affichée, les actions sont gardées ;
//   - actions en attente : combien partiront au retour du réseau ;
//   - actions abandonnées : le serveur les a refusées au retour du réseau (mission réaffectée...).
function BandeauHorsLigne() {
    const [etat, setEtat] = useState(etatHorsLigne);
    useEffect(() => suivreHorsLigne(setEtat), []);
    const { reseauCoupe, enAttente, abandonnees } = etat;

    return (
        <>
            {(reseauCoupe || enAttente > 0) && (
                <div role="status" className="mb-4 p-4 rounded-2xl bg-slate-800 text-white flex items-start gap-3">
                    {reseauCoupe ? <WifiOff className="w-6 h-6 shrink-0" /> : <CloudUpload className="w-6 h-6 shrink-0 animate-pulse" />}
                    <div className="text-sm">
                        <p className="font-bold">{reseauCoupe ? "Réseau coupé" : "Envoi en cours…"}</p>
                        <p className="text-white/80">
                            {reseauCoupe && "Votre mission reste affichée. Continuez normalement : "}
                            {enAttente > 0
                                ? `${enAttente} action${enAttente > 1 ? "s" : ""} ${enAttente > 1 ? "seront envoyées" : "sera envoyée"} au retour du réseau, avec son heure réelle.`
                                : "vos actions seront envoyées au retour du réseau."}
                        </p>
                    </div>
                </div>
            )}

            {abandonnees.length > 0 && (
                <div role="alert" className="mb-4 p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 flex items-start gap-3">
                    <TriangleAlert className="w-6 h-6 shrink-0" />
                    <div className="flex-1 text-sm">
                        <p className="font-bold">Action{abandonnees.length > 1 ? "s" : ""} non prise{abandonnees.length > 1 ? "s" : ""} en compte</p>
                        <ul className="list-disc pl-4">
                            {abandonnees.map((message, i) => <li key={i}>{message}</li>)}
                        </ul>
                    </div>
                    <button type="button" onClick={oublierAbandonnees} aria-label="Fermer" className="p-1 cursor-pointer">
                        <X className="w-5 h-5" />
                    </button>
                </div>
            )}
        </>
    );
}

export default BandeauHorsLigne;
