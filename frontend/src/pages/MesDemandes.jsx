import { Link } from "react-router-dom";
import { ArrowRight, ChevronRight, ClipboardList, Plus, RefreshCw, UserRound } from "lucide-react";
import EnTete from "../components/EnTete";
import { BadgeStatut, BadgeUrgence } from "../components/Badges";
import { useDonnees } from "../hooks/useDonnees";
import { listerMissions } from "../services/missionService";
import { formaterHeure } from "../services/referentiel";

// Les demandes avancent en temps réel (WebSocket) ; relues aussi toutes les 30 s si la connexion est coupée
const INTERVALLE_MS = 30000;
// Statuts d'une demande pas encore terminée
const EN_COURS = ["EN_ATTENTE", "PROPOSE", "ACCEPTE", "EN_TRANSIT"];
// Demandes terminées ou annulées affichées (les plus récentes)
const NB_TERMINEES = 20;

// « Mes demandes » : les demandes de transport du médecin connecté, pour retrouver leur suivi
// après avoir quitté la page. Le serveur ne renvoie au médecin que ses propres demandes (GET /missions).
function MesDemandes() {
    const { donnees, erreur, chargement, recharger } = useDonnees(listerMissions, INTERVALLE_MS, ["missions"]);
    const missions = donnees ?? [];

    // Le serveur trie par urgence (file du régulateur) ; ici, la plus récente d'abord
    const recentes = [...missions].sort((a, b) => new Date(b.date_creation) - new Date(a.date_creation));
    const enCours = recentes.filter((m) => EN_COURS.includes(m.statut));
    const terminees = recentes.filter((m) => !EN_COURS.includes(m.statut)).slice(0, NB_TERMINEES);

    return (
        <div className="min-h-screen">
            <EnTete largeur="max-w-3xl" />
            <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-6">
                <div className="flex items-start justify-between gap-4">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Mes demandes</h1>
                        <p className="text-slate-500 mt-1">Touchez une demande pour suivre le transport.</p>
                    </div>
                    <button type="button" onClick={recharger} title="Actualiser" aria-label="Actualiser"
                        className="p-2.5 bg-white border border-slate-200 rounded-xl text-slate-600 hover:bg-slate-50 cursor-pointer shrink-0">
                        <RefreshCw className={`w-4 h-4 ${chargement ? "animate-spin" : ""}`} />
                    </button>
                </div>

                {erreur && <p className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur}</p>}

                {donnees && (
                    <>
                        <Section titre="En cours" missions={enCours}
                            vide="Aucune demande en cours." />
                        <Section titre="Terminées et annulées" missions={terminees}
                            vide="Aucune demande terminée pour le moment." />
                    </>
                )}

                <Link to="/medecin"
                    className="w-full py-3.5 bg-primaire hover:bg-primaire-fonce text-white font-semibold rounded-xl flex items-center justify-center gap-2">
                    <Plus className="w-4 h-4" />
                    Nouvelle demande de transport
                </Link>
            </main>
        </div>
    );
}

function Section({ titre, missions, vide }) {
    return (
        <section className="space-y-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {titre} ({missions.length})
            </h2>
            {missions.length === 0 ? (
                <p className="p-5 bg-white border border-slate-200 rounded-2xl text-sm text-slate-500 flex items-center gap-3">
                    <ClipboardList className="w-5 h-5 text-slate-400 shrink-0" />
                    {vide}
                </p>
            ) : (
                <ul className="space-y-3">
                    {missions.map((m) => <li key={m.id}><CarteDemande mission={m} /></li>)}
                </ul>
            )}
        </section>
    );
}

// Une demande : patient, urgence, trajet, statut, heure de création et brancardier
function CarteDemande({ mission }) {
    const agent = mission.brancardier_id !== null && EN_COURS.includes(mission.statut);
    return (
        <Link to={`/medecin/suivi/${mission.id}`}
            className="block bg-white rounded-2xl border border-slate-200 shadow-sm p-4 sm:p-5 hover:border-primaire/40 hover:bg-slate-50/60">
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <p className="font-semibold text-slate-900 truncate">{mission.patient_nom} {mission.patient_prenom}</p>
                    <p className="text-xs font-mono text-slate-500">Mission #{mission.id} · {formaterCreation(mission.date_creation)}</p>
                </div>
                <BadgeUrgence niveau={mission.niveau_urgence} />
            </div>

            <p className="mt-3 text-sm text-slate-700 flex items-center gap-2 flex-wrap">
                <span>{mission.noeud_source_nom}</span>
                <ArrowRight className="w-4 h-4 text-slate-400 shrink-0" />
                <span>{mission.noeud_destination_nom}</span>
            </p>

            <div className="mt-3 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 flex-wrap min-w-0">
                    <BadgeStatut statut={mission.statut} />
                    {agent && (
                        <span className="text-sm text-slate-600 flex items-center gap-1.5 min-w-0">
                            <UserRound className="w-4 h-4 text-slate-400 shrink-0" />
                            <span className="truncate">{mission.brancardier_prenom} {mission.brancardier_nom}</span>
                        </span>
                    )}
                </div>
                <ChevronRight className="w-5 h-5 text-slate-400 shrink-0" />
            </div>
        </Link>
    );
}

// Heure seule pour une demande du jour, date et heure sinon
function formaterCreation(dateIso) {
    const date = new Date(dateIso);
    const aujourdhui = date.toDateString() === new Date().toDateString();
    return aujourdhui
        ? `créée à ${formaterHeure(dateIso)}`
        : `créée le ${date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })} à ${formaterHeure(dateIso)}`;
}

export default MesDemandes;
