import { MapPin } from "lucide-react";
import { formaterHeure } from "../../services/referentiel";

// Sélecteur « Je suis à : [lieu] », en haut de l'onglet Mission : simulation des balises BLE.
// balise : état renvoyé par useBaliseSimulee (lieu choisi, heure du dernier envoi, erreur)
// lieux : tous les lieux de l'hôpital (GET /noeuds), regroupés par étage dans la liste.
function MaPosition({ balise, lieux }) {
    const etages = [...new Set(lieux.map((l) => l.etage))].sort((a, b) => a - b);

    return (
        <section className="mb-4 bg-white rounded-2xl shadow-sm p-3">
            <label className="flex items-center gap-3">
                <MapPin className={`w-6 h-6 shrink-0 ${balise.lieu ? "text-primaire" : "text-amber-600"}`} />
                <span className="flex-1 min-w-0">
                    <span className="block text-xs font-semibold uppercase tracking-wide text-slate-400">Je suis à</span>
                    <select value={balise.lieu ?? ""} onChange={(e) => balise.setLieu(Number(e.target.value))}
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

            {/* État de la balise : erreur, position manquante, ou heure du dernier envoi */}
            {balise.erreur ? (
                <p role="alert" className="mt-2 text-xs text-red-700">{balise.erreur}</p>
            ) : !balise.lieu ? (
                <p className="mt-2 text-xs text-amber-700">
                    Indiquez où vous êtes : sans position, les missions proches ne peuvent pas vous être attribuées en priorité.
                </p>
            ) : balise.envoyeA && (
                <p className="mt-2 text-xs text-slate-400">
                    Balise simulée · position envoyée à {formaterHeure(balise.envoyeA)}, renvoyée toutes les 2 min
                </p>
            )}
        </section>
    );
}

export default MaPosition;
