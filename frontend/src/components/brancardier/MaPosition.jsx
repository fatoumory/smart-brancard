import { MapPin } from "lucide-react";
import { formaterHeure } from "../../services/referentiel";

// Sélecteur « Je suis à : [lieu] », en haut de l'onglet Mission : simulation des balises BLE.
// balise : état renvoyé par useBaliseSimulee (lieu choisi, dernière position connue, dernier envoi, erreur).
// Le sélecteur reste vide tant que l'agent n'a pas choisi lui-même : une position reprise ou scannée
// est seulement affichée en dessous, car elle n'est pas renvoyée.
function MaPosition({ balise, lieux }) {
    const etages = [...new Set(lieux.map((l) => l.etage))].sort((a, b) => a - b);

    return (
        <section className="mb-4 bg-white rounded-2xl shadow-sm p-3">
            <label className="flex items-center gap-3">
                <MapPin className={`w-6 h-6 shrink-0 ${balise.lieu ? "text-primaire" : "text-amber-600"}`} />
                <span className="flex-1 min-w-0">
                    <span className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Je suis à</span>
                    <select value={balise.lieu ?? ""} onChange={(e) => balise.choisir(Number(e.target.value))}
                        className="w-full bg-transparent font-semibold text-slate-900 truncate cursor-pointer focus:outline-none">
                        <option value="" disabled>Choisir mon lieu…</option>
                        {etages.map((etage) => (
                            <optgroup key={etage} label={etage === 0 ? "Rez-de-chaussée" : `Étage ${etage}`}>
                                {lieux.filter((l) => l.etage === etage)
                                    .sort((a, b) => a.nom_salle.localeCompare(b.nom_salle))
                                    .map((l) => <option key={l.id} value={l.id}>{l.nom_salle}</option>)}
                            </optgroup>
                        ))}
                    </select>
                </span>
            </label>

            {/* État de la balise : erreur, lieu choisi (renvoyé), dernière position connue (non renvoyée),
                ou aucune position */}
            {balise.erreur ? (
                <p role="alert" className="mt-2 text-xs text-red-700">{balise.erreur}</p>
            ) : balise.lieu ? (
                balise.envoyeA && (
                    <p className="mt-2 text-xs text-slate-400">
                        Balise simulée · position envoyée à {formaterHeure(balise.envoyeA)}, renvoyée toutes les 2 min
                    </p>
                )
            ) : balise.derniere ? (
                <p className="mt-2 text-xs text-slate-500">
                    Dernière position connue : <span className="font-semibold">{balise.derniere.nom}</span>
                    {balise.derniere.origine === "scan" ? " (scan à " : " (à "}{formaterHeure(balise.derniere.date)}).
                    {" "}Elle n'est valable que 10 min : choisissez votre lieu pour rester prioritaire sur les missions proches.
                </p>
            ) : (
                <p className="mt-2 text-xs text-amber-700">
                    Indiquez où vous êtes : sans position, les missions proches ne peuvent pas vous être attribuées en priorité.
                </p>
            )}

        </section>
    );
}

export default MaPosition;
