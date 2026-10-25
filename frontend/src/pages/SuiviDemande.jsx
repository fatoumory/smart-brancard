import { useCallback } from "react";
import { Link, useParams } from "react-router-dom";
import { CircleCheck, CircleX, Hourglass, RefreshCw, ShieldAlert, ShieldCheck, Timer } from "lucide-react";
import EnTete from "../components/EnTete";
import { BadgeUrgence } from "../components/Badges";
import { useDonnees } from "../hooks/useDonnees";
import { getHistorique, getMission } from "../services/missionService";
import { formaterHeure } from "../services/referentiel";

// Le suivi est relu toutes les 10 s pour voir avancer la mission, en attendant les WebSockets (Sprint 4)
const INTERVALLE_MS = 10000;

// Les 4 étapes vues par le médecin (maquette "Suivi de la demande").
// Chaque étape est atteinte avec un statut de mission ; son heure vient du journal d'audit.
const ETAPES = [
    { libelle: "Demande reçue par la régulation", statuts: ["EN_ATTENTE", "PROPOSE", "ACCEPTE" ,"EN_TRANSIT", "TERMINE"] },
    { libelle: "Assignée à un brancardier", statuts: ["PROPOSE","ACCEPTE", "EN_TRANSIT", "TERMINE"] },
    // Étape atteinte dès que le brancardier accepte (statut ACCEPTE), avant même la prise en charge
    { libelle: "Prise en charge acceptée", statuts: ["ACCEPTE", "EN_TRANSIT", "TERMINE"] },
    { libelle: "Patient transféré", statuts: ["TERMINE"] },
];

// Message sous les étapes, selon l'avancement
const SITUATIONS = {
    EN_ATTENTE: ["En attente d'assignation", "Le régulateur va choisir le brancardier disponible le plus proche."],
    PROPOSE: ["Proposée à un brancardier", "En attente de sa réponse."],
    ACCEPTE: ["Brancardier en route", "Il a accepté la mission et se rend auprès du patient."],
    EN_TRANSIT: ["Patient en cours de transport", "Le brancardier a pris en charge le patient."],
    TERMINE: ["Transfert terminé", "Le patient est arrivé à destination."],
    ANNULE: ["Mission annulée", "Cette demande a été annulée par la régulation."],
};

function SuiviDemande() {
    const { id } = useParams();
    // Mission et journal d'audit sont chargés ensemble, pour rester cohérents
    const chargeur = useCallback(() => Promise.all([getMission(id), getHistorique(id)]), [id]);
    const { donnees, erreur, chargement, recharger } = useDonnees(chargeur, INTERVALLE_MS);
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

                        {mission.statut !== "ANNULE" && <GarantiePriseEnCharge mission={mission} />}

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

// Encadré « Garantie de prise en charge » (maquette) : délai garanti selon l'urgence,
// brancardier assigné, sa position et son arrivée estimée au point de départ.
// Toutes ces valeurs sont calculées par le serveur (MissionOut) ; l'arrivée estimée n'existe
// que si la position de l'agent est connue (balise détectée il y a moins de 10 min).
function GarantiePriseEnCharge({ mission }) {
    // Agent qui a accepté la mission (ou l'a déjà terminée)
    const accepte = ["ACCEPTE", "EN_TRANSIT", "TERMINE"].includes(mission.statut);
    // Agent en approche : sa position et son arrivée estimée ont un sens
    const enApproche = mission.statut === "PROPOSE" || mission.statut === "ACCEPTE";
    const depasse = mission.dans_les_delais === false;

    // Titre et couleur : garantie confirmée, délai dépassé, ou simple rappel du délai
    const [titre, classe, Icone] = depasse
        ? ["Délai garanti dépassé", "bg-red-50 border-red-200 text-red-800", ShieldAlert]
        : accepte
            ? ["Garantie de prise en charge confirmée", "bg-emerald-50 border-emerald-200 text-emerald-800", ShieldCheck]
            : ["Délai garanti", "bg-primaire-clair border-blue-200 text-primaire", Timer];

    return (
        <section className={`rounded-2xl border p-5 ${classe}`}>
            <p className="flex items-center gap-2 font-semibold">
                <Icone className="w-5 h-5" /> {titre}
            </p>
            <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="opacity-80">Délai garanti</dt>
                <dd className="font-medium">
                    {mission.delai_garanti_min} min · prise en charge avant {formaterHeure(mission.limite_prise_en_charge)}
                </dd>

                <dt className="opacity-80">Brancardier</dt>
                <dd className="font-medium">
                    {mission.brancardier_id !== null
                        ? `${mission.brancardier_prenom} ${mission.brancardier_nom}`
                        : "En cours d'attribution"}
                </dd>

                {/* Position et arrivée : seulement pendant l'approche de l'agent */}
                {mission.brancardier_id !== null && enApproche && (
                    <>
                        <dt className="opacity-80">Position actuelle</dt>
                        <dd className="font-medium">{mission.brancardier_position_nom ?? "Inconnue"}</dd>

                        <dt className="opacity-80">Arrivée estimée</dt>
                        <dd className="font-medium">
                            {mission.arrivee_estimee
                                ? `${formaterHeure(mission.arrivee_estimee)} au point de départ`
                                : "Non calculée (position de l'agent inconnue)"}
                        </dd>
                    </>
                )}

                {/* Prise en charge effective : heure du scan de départ */}
                {mission.date_prise_en_charge && (
                    <>
                        <dt className="opacity-80">Pris en charge</dt>
                        <dd className="font-medium">{formaterHeure(mission.date_prise_en_charge)}</dd>
                    </>
                )}
            </dl>
        </section>
    );
}

export default SuiviDemande;
