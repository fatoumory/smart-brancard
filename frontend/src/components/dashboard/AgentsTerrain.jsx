import { MapPin, Users } from "lucide-react";
import { STATUTS_AGENT, formaterHeure } from "../../services/referentiel";

// Couleurs CSS du petit camembert (mêmes teintes que les points de statut)
const COULEURS_CAMEMBERT = {
    DISPONIBLE: "#047857", EN_MISSION: "#1565c0", EN_PAUSE: "#ea580c", INDISPONIBLE: "#94a3b8",
};

// Liste des brancardiers avec leur statut, leur position et leur nombre de missions du jour.
function AgentsTerrain({ agents, erreur }) {
    return (
        <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
                <h2 className="flex items-center gap-2 text-xl font-bold text-slate-900">
                    <Users className="w-5 h-5 text-primaire" />
                    Agents terrain
                </h2>
                {agents?.length > 0 && <Camembert agents={agents} />}
            </div>

            {erreur && <p className="p-5 text-sm text-red-700">{erreur}</p>}
            {agents?.length === 0 && <p className="p-5 text-sm text-slate-500">Aucun brancardier enregistré.</p>}

            <ul className="divide-y divide-slate-100">
                {agents?.map((agent) => {
                    const statut = STATUTS_AGENT[agent.statut] ?? STATUTS_AGENT.INDISPONIBLE;
                    return (
                        <li key={agent.id} className="flex items-center justify-between px-5 py-4">
                            <div>
                                <p className="font-medium text-slate-900">{agent.prenom} {agent.nom}</p>
                                <Position agent={agent} />
                            </div>
                            <div className="text-right">
                                <p className={`flex items-center justify-end gap-2 font-medium ${statut.texte}`}>
                                    <span className={`w-2.5 h-2.5 rounded-full ${statut.point}`} />
                                    {statut.libelle}
                                </p>
                                <p className="text-sm font-mono text-slate-500">
                                    {agent.compteur_mission} mission{agent.compteur_mission > 1 ? "s" : ""}
                                </p>
                            </div>
                        </li>
                    );
                })}
            </ul>
        </section>
    );
}

// Position de l'agent : dernière balise qui l'a détecté (champs position_* de GET /utilisateurs)
function Position({ agent }) {
    // Jamais détecté par une balise
    if (!agent.position_noeud_nom) {
        return (
            <p className="flex items-center gap-1 text-sm text-slate-400">
                <MapPin className="w-3.5 h-3.5" /> Position inconnue
            </p>
        );
    }
    // Dernière détection de plus de 10 min : l'agent a pu bouger, la position est affichée comme incertaine
    const incertaine = !agent.position_recente;
    return (
        <p className={`flex items-center gap-1 text-sm ${incertaine ? "text-slate-400 italic" : "text-slate-500"}`}
            title={incertaine ? "Aucune détection depuis plus de 10 minutes" : undefined}>
            <MapPin className="w-3.5 h-3.5 shrink-0" />
            {agent.position_noeud_nom}
            {incertaine && ` · vu à ${formaterHeure(agent.position_date)}`}
        </p>
    );
}


// Répartition des agents par statut, dessinée avec un dégradé conique CSS
function Camembert({ agents }) {
    let debut = 0;
    const parts = Object.keys(COULEURS_CAMEMBERT).map((statut) => {
        const part = (agents.filter((a) => a.statut === statut).length / agents.length) * 100;
        const segment = `${COULEURS_CAMEMBERT[statut]} ${debut}% ${debut + part}%`;
        debut += part;
        return segment;
    });
    return (
        <div
            className="w-12 h-12 rounded-full"
            style={{ background: `conic-gradient(${parts.join(", ")})` }}
            title="Répartition des agents par statut"
        />
    );
}

export default AgentsTerrain;
