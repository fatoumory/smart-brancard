import { Fragment, useState } from "react";
import { Activity, ArrowRight, ChevronDown, Route } from "lucide-react";
import { BadgeStatut, BadgeUrgence, Materiel } from "../Badges";
import { STATUTS_MISSION, URGENCES, formaterHeure, trierParPriorite } from "../../services/referentiel";

const selectClasse = "px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 cursor-pointer";

// Tableau des missions, trié par urgence puis ancienneté.
// Un clic sur une ligne affiche l'itinéraire calculé, étape par étape.
// agentsParId : { id: brancardier } pour afficher le nom de l'agent assigné
// typesNoeuds : { id: type_noeud } pour distinguer les ascenseurs dans l'itinéraire
function FileMissions({ missions, agentsParId, typesNoeuds }) {
    const [filtreUrgence, setFiltreUrgence] = useState("");
    const [filtreStatut, setFiltreStatut] = useState("");
    const [ouverte, setOuverte] = useState(null);

    const aTraiter = missions.filter((m) => m.statut === "EN_ATTENTE" || m.statut === "PROPOSE").length;
    const visibles = trierParPriorite(missions).filter((m) =>
        (!filtreUrgence || m.niveau_urgence === filtreUrgence) && (!filtreStatut || m.statut === filtreStatut));

    return (
        <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 p-5">
                <h2 className="flex items-center gap-2 text-xl font-bold text-slate-900">
                    <Activity className="w-5 h-5 text-primaire" />
                    File des missions
                    {/* Missions qui attendent encore un brancardier (non assignées ou pas encore acceptées) */}
                    {aTraiter > 0 && (
                        <span className="min-w-7 h-7 px-2 rounded-full bg-red-50 text-red-700 text-sm font-bold flex items-center justify-center"
                            title="Missions en attente de prise en charge">
                            {aTraiter}
                        </span>
                    )}
                </h2>
                <div className="flex gap-2">
                    <select value={filtreUrgence} onChange={(e) => setFiltreUrgence(e.target.value)}
                        className={selectClasse} aria-label="Filtrer par urgence">
                        <option value="">Toutes urgences</option>
                        {Object.entries(URGENCES).map(([code, u]) => <option key={code} value={code}>{u.libelle}</option>)}
                    </select>
                    <select value={filtreStatut} onChange={(e) => setFiltreStatut(e.target.value)}
                        className={selectClasse} aria-label="Filtrer par statut">
                        <option value="">Tous statuts</option>
                        {Object.entries(STATUTS_MISSION).map(([code, s]) => <option key={code} value={code}>{s.libelle}</option>)}
                    </select>
                </div>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left min-w-[900px]">
                    <thead className="bg-slate-50 border-y border-slate-200">
                        <tr className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                            <th className="px-4 py-3">ID</th>
                            <th className="px-4 py-3">Patient</th>
                            <th className="px-4 py-3">Urgence</th>
                            <th className="px-4 py-3">Trajet</th>
                            <th className="px-4 py-3">Matériels</th>
                            <th className="px-4 py-3">Agent assigné</th>
                            <th className="px-4 py-3">Statut</th>
                            <th className="px-4 py-3">Heure</th>
                            <th className="px-2 py-3"><span className="sr-only">Itinéraire</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {visibles.length === 0 && (
                            <tr>
                                <td colSpan={9} className="px-4 py-10 text-center text-slate-500">
                                    Aucune mission ne correspond à ces filtres.
                                </td>
                            </tr>
                        )}
                        {visibles.map((m) => (
                            <Fragment key={m.id}>
                                <tr
                                    onClick={() => setOuverte(ouverte === m.id ? null : m.id)}
                                    className={`border-b border-slate-100 cursor-pointer hover:bg-slate-50 ${
                                        m.niveau_urgence === "URGENT" && m.statut !== "TERMINE" && m.statut !== "ANNULE" ? "bg-red-50/60" : ""}`}
                                >
                                    <td className="px-4 py-4 font-mono text-sm text-slate-500">#{m.id}</td>
                                    <td className="px-4 py-4">
                                        <p className="font-medium text-slate-900">{m.patient_nom} {m.patient_prenom}</p>
                                        <p className="text-xs font-mono text-slate-500">IPP : {m.patient_ipp}</p>
                                    </td>
                                    <td className="px-4 py-4"><BadgeUrgence niveau={m.niveau_urgence} /></td>
                                    <td className="px-4 py-4 text-sm text-slate-800">
                                        <span className="inline-flex items-center gap-2">
                                            <span className="max-w-[9rem] truncate" title={m.noeud_source_nom}>{m.noeud_source_nom}</span>
                                            <ArrowRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                            <span className="max-w-[9rem] truncate" title={m.noeud_destination_nom}>{m.noeud_destination_nom}</span>
                                        </span>
                                    </td>
                                    <td className="px-4 py-4"><Materiel code={m.materiel_requis} /></td>
                                    <td className="px-4 py-4 text-sm"><Agent id={m.brancardier_id} agentsParId={agentsParId} /></td>
                                    <td className="px-4 py-4"><BadgeStatut statut={m.statut} /></td>
                                    <td className="px-4 py-4 font-mono text-sm text-slate-600">{formaterHeure(m.date_creation)}</td>
                                    <td className="px-2 py-4">
                                        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${ouverte === m.id ? "rotate-180" : ""}`} />
                                    </td>
                                </tr>
                                {ouverte === m.id && (
                                    <tr className="bg-slate-50 border-b border-slate-200">
                                        <td colSpan={9} className="px-4 py-4">
                                            <Itineraire mission={m} typesNoeuds={typesNoeuds} />
                                            {m.consigne && (
                                                <p className="text-sm text-slate-600 mt-3">
                                                    <span className="font-semibold">Consigne :</span> {m.consigne}
                                                </p>
                                            )}
                                        </td>
                                    </tr>
                                )}
                            </Fragment>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}

function Agent({ id, agentsParId }) {
    if (id === null) return <span className="text-slate-400">—</span>;
    const agent = agentsParId[id];
    return (
        <span className="font-medium text-slate-900">
            {agent ? `${agent.prenom[0]}. ${agent.nom}` : `Agent #${id}`}
        </span>
    );
}

// Liste d'étapes de l'itinéraire : "Urgences → Ascenseur A - RDC → ... → Réanimation"
function Itineraire({ mission, typesNoeuds }) {
    if (!mission.itineraire?.length) {
        return <p className="text-sm text-slate-500">Itinéraire pas encore calculé.</p>;
    }
    return (
        <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="flex items-center gap-1.5 font-semibold text-slate-700 mr-1">
                <Route className="w-4 h-4 text-primaire" /> Itinéraire
                {mission.duree_estimee != null && (
                    <span className="font-normal text-slate-500">(≈ {Math.round(mission.duree_estimee)} min)</span>
                )} :
            </span>
            {mission.itineraire.map((id, i) => (
                <Fragment key={`${id}-${i}`}>
                    {i > 0 && <ArrowRight className="w-3.5 h-3.5 text-slate-400" />}
                    <span className={`px-2 py-1 rounded-md border ${
                        typesNoeuds[id] === "ASCENSEUR" ? "bg-primaire-clair border-blue-200 text-primaire" : "bg-white border-slate-200 text-slate-700"}`}>
                        {mission.itineraire_noms[i]}
                    </span>
                </Fragment>
            ))}
        </div>
    );
}

export default FileMissions;
