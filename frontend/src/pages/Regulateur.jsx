import { CircleCheck, Clock, Navigation, RefreshCw, Users } from "lucide-react";
import EnTete from "../components/EnTete";
import CarteIndicateur from "../components/dashboard/CarteIndicateur";
import FileMissions from "../components/dashboard/FileMissions";
import AgentsTerrain from "../components/dashboard/AgentsTerrain";
import ActiviteJour from "../components/dashboard/ActiviteJour";
import { useDonnees } from "../hooks/useDonnees";
import { listerBrancardiers, listerMissions, listerNoeuds } from "../services/missionService";

// Rafraîchissement automatique toutes les 15 s, en attendant les WebSockets (Sprint 4)
const INTERVALLE_MS = 15000;

function Regulateur() {
    const missions = useDonnees(listerMissions, INTERVALLE_MS);
    const agents = useDonnees(listerBrancardiers, INTERVALLE_MS);
    // Le plan de l'hôpital change rarement : chargé une seule fois
    const noeuds = useDonnees(listerNoeuds);

    const liste = missions.donnees ?? [];
    const aujourdhui = new Date().toDateString();
    const compter = (statut) => liste.filter((m) => m.statut === statut).length;
    const disponibles = agents.donnees?.filter((a) => a.statut === "DISPONIBLE").length ?? 0;
    const agentsParId = Object.fromEntries((agents.donnees ?? []).map((a) => [a.id, a]));
    const typesNoeuds = Object.fromEntries((noeuds.donnees ?? []).map((n) => [n.id, n.type_noeud]));
    const terminees = liste.filter((m) => m.statut === "TERMINE"
        && new Date(m.date_creation).toDateString() === aujourdhui).length;

    function toutRecharger() {
        missions.recharger();
        agents.recharger();
    }

    return (
        <div className="min-h-screen">
            <EnTete />
            <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h1 className="text-2xl font-bold text-slate-900">Opérations</h1>
                    <div className="flex items-center gap-3 text-sm text-slate-500">
                        {missions.misAJourA && <span>Mis à jour à {missions.misAJourA.toLocaleTimeString("fr-FR")}</span>}
                        <button
                            type="button"
                            onClick={toutRecharger}
                            className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-lg font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
                        >
                            <RefreshCw className={`w-4 h-4 ${missions.chargement ? "animate-spin" : ""}`} />
                            Actualiser
                        </button>
                    </div>
                </div>

                {missions.erreur && (
                    <p className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{missions.erreur}</p>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <CarteIndicateur titre="Missions actives" valeur={compter("EN_TRANSIT")}
                        detail="En transit actuellement" icone={Navigation} couleur="bleu" />
                    <CarteIndicateur titre="En attente" valeur={compter("EN_ATTENTE")}
                        detail="File prioritaire" icone={Clock} couleur="orange" />
                    <CarteIndicateur titre="Agents disponibles" valeur={disponibles}
                        detail={`sur ${agents.donnees?.length ?? 0} agents`} icone={Users} couleur="vert" />
                    <CarteIndicateur titre="Terminées aujourd'hui" valeur={terminees}
                        detail="Depuis minuit" icone={CircleCheck} couleur="vert" />
                </div>

                {missions.donnees && <FileMissions missions={liste} agentsParId={agentsParId} typesNoeuds={typesNoeuds} />}

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
                    <AgentsTerrain agents={agents.donnees} erreur={agents.erreur} />
                    <ActiviteJour missions={liste} />
                </div>
            </main>
        </div>
    );
}

export default Regulateur;
