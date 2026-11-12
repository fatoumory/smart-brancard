import { useState } from "react";
import { BellRing, Check, MapPin } from "lucide-react";
import { traiterAlerte } from "../../services/missionService";
import { formaterHeure } from "../../services/referentiel";

// Raisons d'un appel (énumération RaisonAppel du backend)
const RAISONS = {
    BRACELET_ILLISIBLE: "Bracelet illisible",
    ECHECS_SCAN: "Échecs de scan répétés",
    AUTRE: "Autre problème",
};

// Appels des agents bloqués pendant une mission, en haut du dashboard : qui, pourquoi, où le trouver.
// « Pris en charge » retire l'alerte (le régulateur a joint l'agent) ; c'est tracé avec son nom.
function AlertesAppel({ alertes, onTraitee }) {
    const [envoi, setEnvoi] = useState(null);
    const [erreur, setErreur] = useState("");

    if (!alertes?.length) return null;

    async function traiter(id) {
        setErreur("");
        setEnvoi(id);
        try {
            await traiterAlerte(id);
            onTraitee();
        } catch (err) {
            setErreur(err.message);
        } finally {
            setEnvoi(null);
        }
    }

    return (
        <section role="alert" className="bg-amber-50 border-2 border-amber-300 rounded-2xl p-5 space-y-3">
            <h2 className="flex items-center gap-2 text-lg font-bold text-amber-900">
                <BellRing className="w-5 h-5 animate-pulse" />
                {alertes.length} agent{alertes.length > 1 ? "s" : ""} demande{alertes.length > 1 ? "nt" : ""} votre aide
            </h2>
            <ul className="space-y-2">
                {alertes.map((a) => (
                    <li key={a.id} className="bg-white rounded-xl border border-amber-200 p-3 flex flex-wrap items-center justify-between gap-3">
                        <div>
                            <p className="font-semibold text-slate-900">
                                {a.brancardier_prenom} {a.brancardier_nom} · {RAISONS[a.raison] ?? a.raison}
                            </p>
                            <p className="flex items-center gap-1 text-sm text-slate-500">
                                <MapPin className="w-3.5 h-3.5" /> {a.lieu_nom} · mission #{a.mission_id} · appel à {formaterHeure(a.date_creation)}
                            </p>
                        </div>
                        <button type="button" onClick={() => traiter(a.id)} disabled={envoi === a.id}
                            className="px-3 py-2 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-900 text-sm font-bold flex items-center gap-2 cursor-pointer disabled:opacity-50">
                            <Check className="w-4 h-4" /> Pris en charge
                        </button>
                    </li>
                ))}
            </ul>
            {erreur && <p className="text-sm text-red-700">{erreur}</p>}
        </section>
    );
}

export default AlertesAppel;
