import { Fragment, useState } from "react";
import { Activity, ArrowRight, Ban, ChevronDown, MoreHorizontal, Route, TriangleAlert, UserRoundCog, Zap } from "lucide-react";
import { BadgeStatut, BadgeUrgence, Materiel } from "../Badges";
import ActionRegulation from "./ActionRegulation";
import { STATUTS_MISSION, URGENCES, formaterHeure, trierParPriorite } from "../../services/referentiel";

const selectClasse = "px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 cursor-pointer";

// Le régulateur peut réaffecter ou annuler tant que le patient n'est pas en transport
// (même règle que le backend : services/regulation_service.py)
const STATUTS_MODIFIABLES = ["EN_ATTENTE", "PROPOSE", "ACCEPTE"];

// Tableau des missions, trié par urgence puis ancienneté.
// Un clic sur une ligne (ou sur « ⋯ ») affiche l'itinéraire et les actions du régulateur.
// typesNoeuds : { id: type_noeud } pour distinguer les ascenseurs dans l'itinéraire
// agents : brancardiers (pour la réaffectation) ; onAction : appelé après une action réussie
// (le nom de l'agent est fourni par le backend dans chaque mission : brancardier_prenom / _nom)
function FileMissions({ missions, typesNoeuds, agents, onAction }) {
    const [filtreUrgence, setFiltreUrgence] = useState("");
    const [filtreStatut, setFiltreStatut] = useState("");
    const [ouverte, setOuverte] = useState(null);
    // Action en cours dans la ligne ouverte : "reaffecter", "annuler" ou null
    const [action, setAction] = useState(null);

    // Ouvre ou ferme le détail d'une mission ; une action commencée est abandonnée
    function basculer(id) {
        setOuverte(ouverte === id ? null : id);
        setAction(null);
    }

    // Action réussie : on referme le détail et le dashboard relit missions et agents
    function actionFaite() {
        setOuverte(null);
        setAction(null);
        onAction();
    }

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
                            <th className="px-2 py-3"><span className="sr-only">Actions</span></th>
                            <th className="px-2 py-3"><span className="sr-only">Itinéraire</span></th>
                        </tr>
                    </thead>
                    <tbody>
                        {visibles.length === 0 && (
                            <tr>
                                <td colSpan={10} className="px-4 py-10 text-center text-slate-500">
                                    Aucune mission ne correspond à ces filtres.
                                </td>
                            </tr>
                        )}
                        {visibles.map((m) => (
                            <Fragment key={m.id}>
                                <tr
                                    onClick={() => basculer(m.id)}
                                    className={`border-b border-slate-100 cursor-pointer hover:bg-slate-50 ${
                                        m.alerte_materiel ? "bg-amber-50"
                                            : m.niveau_urgence === "URGENT" && m.statut !== "TERMINE" && m.statut !== "ANNULE" ? "bg-red-50/60" : ""}`}
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
                                    <td className="px-4 py-4 text-sm"><Agent mission={m} /></td>
                                    <td className="px-4 py-4">
                                        <BadgeStatut statut={m.statut} />
                                        {/* Mission bloquée : plus proposée automatiquement, en attente d'une décision */}
                                        {m.alerte_materiel && (
                                            <span className="mt-1 flex items-center gap-1 text-xs font-semibold text-amber-700"
                                                title="Refusée pour matériel défectueux : à réaffecter ou annuler">
                                                <TriangleAlert className="w-3.5 h-3.5" /> Matériel défectueux
                                            </span>
                                        )}
                                    </td>                                    
                                    <td className="px-4 py-4 font-mono text-sm text-slate-600">{formaterHeure(m.date_creation)}</td>
                                    {/* Menu « ⋯ » : seulement si la mission peut encore être modifiée */}
                                    <td className="px-2 py-4">
                                        {STATUTS_MODIFIABLES.includes(m.statut) && (
                                            <button type="button" title="Réaffecter ou annuler" aria-label={`Actions sur la mission ${m.id}`}
                                                onClick={(e) => {
                                                    // Sans stopPropagation, le clic refermerait aussi la ligne
                                                    e.stopPropagation();
                                                    setOuverte(m.id);
                                                    setAction(null);
                                                }}
                                                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-500 hover:bg-slate-200 cursor-pointer">
                                                <MoreHorizontal className="w-5 h-5" />
                                            </button>
                                        )}
                                    </td>
                                    <td className="px-2 py-4">
                                        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${ouverte === m.id ? "rotate-180" : ""}`} />
                                    </td>
                                </tr>
                                {ouverte === m.id && (
                                    <tr className="bg-slate-50 border-b border-slate-200">
                                        <td colSpan={10} className="px-4 py-4 space-y-3">
                                            {/* Actions du régulateur : d'abord le choix, puis le panneau de l'action */}
                                            {STATUTS_MODIFIABLES.includes(m.statut) && (action ? (
                                                <ActionRegulation type={action} mission={m} agents={agents}
                                                    onFait={actionFaite} onFermer={() => setAction(null)} />
                                            ) : (
                                                <div className="flex flex-wrap gap-2">
                                                    <button type="button" onClick={() => setAction("reaffecter")}
                                                        className="px-3 py-2 rounded-lg bg-white border border-slate-200 text-sm font-semibold text-slate-700 flex items-center gap-2 hover:bg-slate-100 cursor-pointer">
                                                        <UserRoundCog className="w-4 h-4 text-primaire" /> Réaffecter
                                                    </button>
                                                    <button type="button" onClick={() => setAction("annuler")}
                                                        className="px-3 py-2 rounded-lg bg-white border border-red-200 text-sm font-semibold text-red-700 flex items-center gap-2 hover:bg-red-50 cursor-pointer">
                                                        <Ban className="w-4 h-4" /> Annuler la mission
                                                    </button>
                                                </div>
                                            ))}
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

// Agent de la mission : « A. Cissé », avec le badge « Auto » s'il a été choisi par l'algorithme
function Agent({ mission }) {
    if (mission.brancardier_id === null) return <span className="text-slate-400">—</span>;
    const nom = mission.brancardier_nom
        ? `${mission.brancardier_prenom?.[0] ?? ""}. ${mission.brancardier_nom}`
        : `Agent #${mission.brancardier_id}`;
    return (
        <span className="flex flex-col items-start gap-1">
            <span className="font-medium text-slate-900">{nom}</span>
            {/* assignation_auto : false si le régulateur l'a choisi à la main (réaffectation) */}
            {mission.assignation_auto && (
                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-primaire-clair text-primaire text-xs font-semibold">
                    <Zap className="w-3 h-3" /> Auto
                </span>
            )}
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
