import { useState } from "react";
import { Ban, MapPin, UserRoundCheck } from "lucide-react";
import { annulerMission, reaffecterMission } from "../../services/missionService";

// Panneau affiché sous une mission quand le régulateur choisit une action du menu « ⋯ » :
//   type="reaffecter" : choisir un brancardier disponible, à qui la mission est proposée ;
//   type="annuler"    : confirmer l'annulation.
// onFait : action réussie (le dashboard relit missions et agents) ; onFermer : abandon.
function ActionRegulation({ type, mission, agents, onFait, onFermer }) {
    const [choisi, setChoisi] = useState(null);
    const [envoi, setEnvoi] = useState(false);
    const [erreur, setErreur] = useState("");

    // Seuls les agents disponibles peuvent recevoir la mission (le serveur refuse les autres).
    // Les moins chargés d'abord : même principe d'équité que l'assignation automatique.
    const candidats = agents
        .filter((a) => a.statut === "DISPONIBLE" && a.id !== mission.brancardier_id)
        .sort((a, b) => a.compteur_mission - b.compteur_mission || a.nom.localeCompare(b.nom));

    async function confirmer() {
        setErreur("");
        setEnvoi(true);
        try {
            if (type === "reaffecter") await reaffecterMission(mission.id, choisi);
            else await annulerMission(mission.id);
            onFait();
        } catch (err) {
            // Ex : « Ce brancardier n'est pas disponible » (il vient de recevoir une autre mission)
            setErreur(err.message);
        } finally {
            setEnvoi(false);
        }
    }

    return (
        <div className="p-4 rounded-xl bg-white border border-slate-200 space-y-3 max-w-2xl">
            {type === "reaffecter" ? (
                <>
                    <div>
                        <p className="font-semibold text-slate-900">Réaffecter la mission #{mission.id}</p>
                        <p className="text-sm text-slate-500">
                            La mission sera proposée à l'agent choisi : il devra l'accepter dans le délai habituel.
                            {mission.brancardier_id !== null && " L'agent actuel sera libéré."}
                        </p>
                    </div>

                    {candidats.length === 0 ? (
                        <p className="text-sm text-slate-500">Aucun autre brancardier n'est disponible pour le moment.</p>
                    ) : (
                        // Un bouton par agent disponible ; aria-pressed indique l'agent choisi
                        <div className="grid sm:grid-cols-2 gap-2">
                            {candidats.map((a) => (
                                <button key={a.id} type="button" onClick={() => setChoisi(a.id)} aria-pressed={choisi === a.id}
                                    className={`text-left p-3 rounded-lg border-2 cursor-pointer ${
                                        choisi === a.id ? "border-primaire bg-primaire-clair" : "border-slate-200 hover:bg-slate-50"}`}>
                                    <span className="block font-medium text-slate-900">{a.prenom} {a.nom}</span>
                                    <span className="flex items-center gap-1 text-xs text-slate-500">
                                        <MapPin className="w-3 h-3 shrink-0" />
                                        {a.position_noeud_nom ?? "Position inconnue"}
                                        {` · ${a.compteur_mission} mission${a.compteur_mission > 1 ? "s" : ""} aujourd'hui`}
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}
                </>
            ) : (
                <div>
                    <p className="font-semibold text-slate-900">Annuler la mission #{mission.id} ?</p>
                    <p className="text-sm text-slate-500">
                        Elle reste visible dans le journal, avec votre nom.
                        {mission.brancardier_id !== null && " Le brancardier sollicité sera libéré."}
                    </p>
                </div>
            )}

            {erreur && <p role="alert" className="p-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{erreur}</p>}

            <div className="flex justify-end gap-2">
                <button type="button" onClick={onFermer}
                    className="px-4 py-2 rounded-lg text-slate-600 font-medium hover:bg-slate-100 cursor-pointer">
                    Retour
                </button>
                {type === "reaffecter" ? (
                    // Désactivé tant qu'aucun agent n'est choisi
                    <button type="button" onClick={confirmer} disabled={!choisi || envoi}
                        className="px-4 py-2 rounded-lg bg-primaire text-white font-semibold flex items-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed">
                        <UserRoundCheck className="w-4 h-4" /> Proposer la mission
                    </button>
                ) : (
                    <button type="button" onClick={confirmer} disabled={envoi}
                        className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold flex items-center gap-2 cursor-pointer disabled:opacity-50">
                        <Ban className="w-4 h-4" /> Confirmer l'annulation
                    </button>
                )}
            </div>
        </div>
    );
}

export default ActionRegulation;
