import { useState } from "react";
import { ArrowLeftRight, ChevronDown, Construction, LockOpen } from "lucide-react";
import { useDonnees } from "../../hooks/useDonnees";
import { bloquerArete, listerAretes } from "../../services/missionService";

// Passages de l'hôpital (couloirs, ascenseurs) : le régulateur bloque un ascenseur en panne ou un couloir
// fermé. Dijkstra l'ignore dès le calcul suivant : les nouvelles missions passent par un autre chemin.
// Les passages bloqués sont en haut ; la liste complète se déplie pour en bloquer un autre.
function BlocagesPassages() {
    const aretes = useDonnees(listerAretes, 60000, ["graphe"]);
    const [ouvert, setOuvert] = useState(false);
    const [envoi, setEnvoi] = useState(null);
    const [erreur, setErreur] = useState("");

    const liste = aretes.donnees ?? [];
    const bloques = liste.filter((a) => a.est_bloque);

    async function basculer(arete) {
        setErreur("");
        setEnvoi(arete.id);
        try {
            await bloquerArete(arete.id, !arete.est_bloque);
            aretes.recharger();
        } catch (err) {
            setErreur(err.message);
        } finally {
            setEnvoi(null);
        }
    }

    return (
        <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <button type="button" onClick={() => setOuvert((o) => !o)} aria-expanded={ouvert}
                className="w-full flex items-center justify-between gap-3 p-5 cursor-pointer">
                <span className="flex items-center gap-2 text-xl font-bold text-slate-900">
                    <Construction className="w-5 h-5 text-primaire" /> Ascenseurs et couloirs
                    {bloques.length > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-red-50 text-red-700 text-sm font-bold">
                            {bloques.length} bloqué{bloques.length > 1 ? "s" : ""}
                        </span>
                    )}
                </span>
                <ChevronDown className={`w-5 h-5 text-slate-400 transition-transform ${ouvert ? "rotate-180" : ""}`} />
            </button>

            {(erreur || aretes.erreur) && <p className="px-5 pb-3 text-sm text-red-700">{erreur || aretes.erreur}</p>}

            {/* Toujours visibles : les passages bloqués, pour ne pas oublier de les rouvrir */}
            {bloques.length > 0 && (
                <ul className="divide-y divide-slate-100 border-t border-slate-100 bg-red-50/40">
                    {bloques.map((a) => <Ligne key={a.id} arete={a} envoi={envoi === a.id} onBasculer={basculer} />)}
                </ul>
            )}
            {ouvert && (
                <ul className="divide-y divide-slate-100 border-t border-slate-100">
                    {liste.filter((a) => !a.est_bloque).map((a) => (
                        <Ligne key={a.id} arete={a} envoi={envoi === a.id} onBasculer={basculer} />
                    ))}
                </ul>
            )}
        </section>
    );
}

// Une ligne par passage : les deux lieux reliés, la durée, et le bouton bloquer / rouvrir
function Ligne({ arete, envoi, onBasculer }) {
    return (
        <li className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
            <span className="flex items-center gap-2 text-sm text-slate-800">
                {arete.noeud_a_nom} <ArrowLeftRight className="w-3.5 h-3.5 text-slate-400" /> {arete.noeud_b_nom}
                <span className="text-xs text-slate-400">({arete.poids} min)</span>
            </span>
            <button type="button" onClick={() => onBasculer(arete)} disabled={envoi}
                className={`px-3 py-1.5 rounded-lg text-sm font-semibold flex items-center gap-1.5 border cursor-pointer disabled:opacity-50 ${arete.est_bloque
                    ? "bg-white border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                    : "bg-white border-red-200 text-red-700 hover:bg-red-50"}`}>
                {arete.est_bloque ? <><LockOpen className="w-4 h-4" /> Rouvrir</> : <><Construction className="w-4 h-4" /> Bloquer</>}
            </button>
        </li>
    );
}

export default BlocagesPassages;
