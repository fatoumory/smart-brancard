import { ArrowRight, CircleCheck, Clock, FileText, TriangleAlert } from "lucide-react";
import { BadgeUrgence } from "../Badges";
import { useDonnees } from "../../hooks/useDonnees";
import { getMonJournal } from "../../services/brancardierService";
import { formaterHeure } from "../../services/referentiel";

// Onglet « Journal » : missions terminées par l'agent aujourd'hui (GET /missions/moi/journal),
// de la plus récente à la plus ancienne. Rechargé à chaque ouverture de l'onglet.
function EcranJournal() {
    const journal = useDonnees(getMonJournal);
    const missions = journal.donnees ?? [];
    // Délai garanti respecté : connu pour les missions prises en charge (dans_les_delais true / false)
    const aLHeure = missions.filter((m) => m.dans_les_delais === true).length;

    if (journal.erreur) {
        return <p className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{journal.erreur}</p>;
    }
    if (!journal.donnees) {
        return <p className="text-center text-slate-500 py-10">Chargement…</p>;
    }

    if (missions.length === 0) {
        return (
            <div className="flex flex-col items-center text-center gap-4 pt-10">
                <span className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center">
                    <FileText className="w-10 h-10 text-slate-400" />
                </span>
                <div>
                    <p className="text-lg font-bold text-slate-900">Aucune mission aujourd'hui</p>
                    <p className="text-slate-500 mt-1">Les missions que vous terminez apparaîtront ici.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Bilan de la journée */}
            <section className="bg-white rounded-2xl shadow-sm p-4 grid grid-cols-2 gap-3 text-center">
                <div>
                    <p className="text-3xl font-extrabold text-slate-900">{missions.length}</p>
                    <p className="text-sm text-slate-500">mission{missions.length > 1 ? "s" : ""} terminée{missions.length > 1 ? "s" : ""}</p>
                </div>
                <div>
                    <p className="text-3xl font-extrabold text-emerald-700">{aLHeure}</p>
                    <p className="text-sm text-slate-500">dans les délais</p>
                </div>
            </section>

            {/* Une carte par mission : heure de fin, urgence, patient, trajet, respect du délai */}
            <ul className="space-y-3">
                {missions.map((m) => (
                    <li key={m.id} className="bg-white rounded-2xl shadow-sm p-4">
                        <div className="flex items-center justify-between gap-3">
                            <span className="flex items-center gap-1.5 font-mono text-sm text-slate-500">
                                <Clock className="w-4 h-4" /> {formaterHeure(m.date_fin)}
                            </span>
                            <BadgeUrgence niveau={m.niveau_urgence} />
                        </div>
                        <p className="mt-2 font-semibold text-slate-900">{m.patient_nom} {m.patient_prenom}</p>
                        <p className="flex items-center gap-1.5 text-sm text-slate-600">
                            <span className="truncate">{m.noeud_source_nom}</span>
                            <ArrowRight className="w-3.5 h-3.5 shrink-0 text-slate-400" />
                            <span className="truncate">{m.noeud_destination_nom}</span>
                        </p>
                        {/* Délai garanti : prise en charge avant la limite (3, 8, 15 ou 30 min selon l'urgence) */}
                        {m.dans_les_delais !== null && (
                            <p className={`mt-2 flex items-center gap-1 text-xs font-semibold ${
                                m.dans_les_delais ? "text-emerald-700" : "text-red-700"}`}>
                                {m.dans_les_delais
                                    ? <><CircleCheck className="w-3.5 h-3.5" /> Pris en charge dans les délais</>
                                    : <><TriangleAlert className="w-3.5 h-3.5" /> Délai garanti de {m.delai_garanti_min} min dépassé</>}
                            </p>
                        )}
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default EcranJournal;
