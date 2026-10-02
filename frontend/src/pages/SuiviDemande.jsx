import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { CircleCheck, CircleX, Hourglass, RefreshCw } from "lucide-react";
import EnTete from "../components/EnTete";
import { BadgeUrgence } from "../components/Badges";
import { useDonnees } from "../hooks/useDonnees";
import { getHistorique, getMission } from "../services/missionService";
import { formaterHeure } from "../services/referentiel";

// Les 4 étapes vues par le médecin (maquette "Suivi de la demande").
// Chaque étape est atteinte avec un statut de mission ; son heure vient du journal d'audit.
const ETAPES = [
    { libelle: "Demande reçue par la régulation", statuts: ["EN_ATTENTE", "PROPOSE", "EN_TRANSIT", "TERMINE"] },
    { libelle: "Assignée à un brancardier", statuts: ["PROPOSE", "EN_TRANSIT", "TERMINE"] },
    { libelle: "Prise en charge acceptée", statuts: ["EN_TRANSIT", "TERMINE"] },
    { libelle: "Patient transféré", statuts: ["TERMINE"] },
];

// Message sous les étapes, selon l'avancement
const SITUATIONS = {
    EN_ATTENTE: ["En attente d'assignation", "Le régulateur va choisir le brancardier disponible le plus proche."],
    PROPOSE: ["Proposée à un brancardier", "En attente de sa réponse."],
    EN_TRANSIT: ["Patient en cours de transport", "Le brancardier a pris en charge le patient."],
    TERMINE: ["Transfert terminé", "Le patient est arrivé à destination."],
    ANNULE: ["Mission annulée", "Cette demande a été annulée par la régulation."],
};

function SuiviDemande() {
    const { id } = useParams();
    // Mission et journal d'audit sont chargés ensemble, pour rester cohérents
    const chargeur = useCallback(() => Promise.all([getMission(id), getHistorique(id)]), [id]);
    const { donnees, erreur, chargement, recharger } = useDonnees(chargeur);
    const [mission, historique] = donnees ?? [];

    // Heure à laquelle la mission est passée pour la première fois dans un des statuts de l'étape
    function heureEtape(etape) {
        const ligne = historique?.find((h) => h.statut_modifie_en === etape.statuts[0]);
        return ligne ? formaterHeure(ligne.horodatage) : null;
    }

    return (
        <div className="min-h-screen">
            <EnTete />
            <main className="max-w-2xl mx-auto px-4 sm:px-6 py-8 space-y-5">
                {erreur && <p className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur}</p>}

                {mission && (
                    <>
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900">Suivi de la demande</h1>
                                <p className="text-slate-500 mt-1">
                                    Mission #{mission.id} · {mission.patient_nom} {mission.patient_prenom}
                                </p>
                                <p className="text-sm text-slate-500">
                                    {mission.noeud_source_nom} → {mission.noeud_destination_nom}
                                    {mission.duree_estimee != null && ` · trajet ≈ ${Math.round(mission.duree_estimee)} min`}
                                </p>
                            </div>
                            <BadgeUrgence niveau={mission.niveau_urgence} />
                        </div>

                        <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
                            <h2 className="font-semibold text-slate-900 mb-4">État de la mission</h2>
                            <ol className="space-y-3">
                                {ETAPES.map((etape) => {
                                    const faite = etape.statuts.includes(mission.statut);
                                    const heure = faite && heureEtape(etape);
                                    return (
                                        <li key={etape.libelle} className="flex items-center gap-3">
                                            <span className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${faite ? "bg-emerald-600" : "bg-slate-100"}`}>
                                                {faite
                                                    ? <CircleCheck className="w-5 h-5 text-white" />
                                                    : <Hourglass className="w-4 h-4 text-slate-500" />}
                                            </span>
                                            <span className={`flex-1 ${faite ? "font-medium text-slate-900" : "text-slate-500"}`}>{etape.libelle}</span>
                                            {heure && <span className="font-mono text-sm text-slate-500">{heure}</span>}
                                        </li>
                                    );
                                })}
                            </ol>
                        </section>

                        <section className="bg-white rounded-2xl border border-slate-200 p-5 flex items-start gap-4">
                            {mission.statut === "ANNULE"
                                ? <CircleX className="w-6 h-6 text-red-600 shrink-0" />
                                : <Hourglass className="w-6 h-6 text-slate-500 shrink-0" />}
                            <div>
                                <p className="font-semibold text-slate-900">{SITUATIONS[mission.statut][0]}</p>
                                <p className="text-sm text-slate-500">{SITUATIONS[mission.statut][1]}</p>
                            </div>
                        </section>
                    </>
                )}

                {/* Rafraîchissement manuel : la mise à jour en temps réel arrive au Sprint 4 (WebSockets) */}
                <button type="button" onClick={recharger}
                    className="w-full py-3 bg-white border border-slate-200 rounded-xl font-medium text-slate-700 hover:bg-slate-50 flex items-center justify-center gap-2 cursor-pointer">
                    <RefreshCw className={`w-4 h-4 ${chargement ? "animate-spin" : ""}`} />
                    Actualiser l'état
                </button>
                <Link to="/medecin"
                    className="w-full py-3 bg-slate-50 border border-slate-200 rounded-xl font-medium text-slate-600 hover:bg-slate-100 flex items-center justify-center gap-2">
                    Nouvelle demande de transport
                </Link>
            </main>
        </div>
    );
}

export default SuiviDemande;
