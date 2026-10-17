import { useState } from "react";
import { CircleCheck, CircleX, Flag, MapPin, Route, ShieldAlert, TriangleAlert, UserRound } from "lucide-react";
import { BadgeUrgence, Materiel } from "../Badges";
import { MOTIFS_REFUS } from "../../services/referentiel";

// Mission proposée au brancardier : détails utiles au transport, puis Accepter ou Refuser.
// Seules des informations logistiques sont affichées : nom, prénom, trajet, matériel, consigne.
function MissionProposee({ mission, envoi, onAccepter, onRefuser }) {
    // Panneau des motifs de refus ouvert, et motif choisi
    const [refusOuvert, setRefusOuvert] = useState(false);
    const [motif, setMotif] = useState(null);

    function fermerRefus() {
        setRefusOuvert(false);
        setMotif(null);
    }

    return (
        <div className="space-y-4">
            {/* Titre et niveau d'urgence */}
            <div className="flex items-center justify-between gap-3">
                <p className="text-xl font-bold text-slate-900">Nouvelle mission</p>
                <BadgeUrgence niveau={mission.niveau_urgence} />
            </div>

            {/* Fiche de la mission */}
            <section className="bg-white rounded-3xl shadow-sm divide-y divide-slate-100">
                {/* Patient */}
                <div className="p-5 flex items-center gap-4">
                    <span className="w-12 h-12 rounded-2xl bg-primaire-clair flex items-center justify-center shrink-0">
                        <UserRound className="w-6 h-6 text-primaire" />
                    </span>
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Patient</p>
                        <p className="text-lg font-bold text-slate-900">{mission.patient_nom} {mission.patient_prenom}</p>
                    </div>
                </div>

                {/* Trajet : départ puis destination, reliés par un trait vertical */}
                <div className="p-5">
                    <div className="flex gap-3">
                        <div className="flex flex-col items-center pt-1">
                            <MapPin className="w-5 h-5 text-primaire" />
                            <span className="w-0.5 flex-1 bg-slate-200 my-1" />
                            <Flag className="w-5 h-5 text-emerald-700" />
                        </div>
                        <div className="flex-1 space-y-4">
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Départ</p>
                                <p className="font-semibold text-slate-900">{mission.noeud_source_nom}</p>
                                {/* Temps pour rejoindre le patient depuis la position de l'agent (au moins 1 min affichée) */}
                                {mission.temps_agent_min != null && (
                                    <p className="text-sm text-slate-500">À environ {Math.max(1, Math.round(mission.temps_agent_min))} min de vous</p>
                                )}
                            </div>
                            <div>
                                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Destination</p>
                                <p className="font-semibold text-slate-900">{mission.noeud_destination_nom}</p>
                                {mission.duree_estimee != null && (
                                    <p className="text-sm text-slate-500">Transport d'environ {Math.max(1, Math.round(mission.duree_estimee))} min</p>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Matériel : à prendre au dépôt, sauf s'il est déjà auprès du patient */}
                <div className="p-5 flex items-center justify-between gap-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Matériel</p>
                    <div className="text-right">
                        <Materiel code={mission.materiel_requis} />
                        {mission.materiel_requis !== "RIEN" && (
                            <p className="text-xs text-slate-500 mt-1">
                                {mission.materiel_deja_dispo ? "Déjà auprès du patient" : "À prendre au dépôt"}
                            </p>
                        )}
                    </div>
                </div>

                {/* Consigne de sécurité : mise en valeur, à lire avant d'accepter */}
                {mission.consigne && (
                    <div className="p-5">
                        <p className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 text-sm flex items-start gap-2">
                            <ShieldAlert className="w-5 h-5 shrink-0" />
                            <span><span className="font-semibold">Consigne :</span> {mission.consigne}</span>
                        </p>
                    </div>
                )}
            </section>

            {/* Les deux réponses possibles : grands boutons, faciles à toucher */}
            <div className="grid grid-cols-2 gap-3">
                {/* Refuser n'envoie rien : il ouvre seulement le choix du motif */}
                <button type="button" onClick={() => setRefusOuvert((o) => !o)} disabled={envoi}
                    aria-expanded={refusOuvert} aria-controls="motifs-refus"
                    className="h-14 rounded-2xl bg-white border-2 border-red-200 text-red-700 font-bold flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60">
                    <CircleX className="w-5 h-5" /> Refuser
                </button>
                <button type="button" onClick={onAccepter} disabled={envoi}
                    className="h-14 rounded-2xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60">
                    <CircleCheck className="w-5 h-5" /> Accepter
                </button>
            </div>

            <MotifsRefus ouvert={refusOuvert} motif={motif} envoi={envoi} onChoisir={setMotif}
                onConfirmer={() => onRefuser(motif)} onAnnuler={fermerRefus} />

            {/* Itinéraire calculé par Dijkstra, étape par étape (du départ à la destination) */}
            <section className="bg-white rounded-3xl shadow-sm p-5">
                <p className="flex items-center gap-2 font-bold text-slate-900 mb-3">
                    <Route className="w-5 h-5 text-primaire" /> Itinéraire
                </p>
                <ol className="space-y-2">
                    {mission.itineraire_noms.map((nom, i) => (
                        <li key={`${mission.itineraire[i]}-${i}`} className="flex items-center gap-3 text-sm text-slate-700">
                            <span className="w-6 h-6 rounded-full bg-slate-100 text-slate-500 text-xs font-bold flex items-center justify-center shrink-0">
                                {i + 1}
                            </span>
                            {nom}
                        </li>
                    ))}
                </ol>
            </section>
        </div>
    );
}

// Choix du motif de refus : se déplie sous les boutons (même principe que le choix de la pause).
// Le motif est obligatoire : le refus n'est envoyé qu'après le bouton « Confirmer le refus ».
function MotifsRefus({ ouvert, motif, envoi, onChoisir, onConfirmer, onAnnuler }) {
    return (
        <div id="motifs-refus" inert={!ouvert}
            className={`grid transition-all duration-300 ease-out motion-reduce:transition-none ${
                ouvert ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
            {/* overflow-hidden : le contenu est masqué tant que la hauteur n'est pas dépliée */}
            <div className="overflow-hidden">
                <div className="bg-white rounded-2xl border border-slate-200 p-3 space-y-2">
                    <p className="px-1 font-semibold text-slate-900">Motif du refus</p>
                    <p className="px-1 text-sm text-slate-500">Obligatoire : il permet de réaffecter la mission rapidement.</p>

                    {/* Un bouton par motif ; aria-pressed indique le motif sélectionné */}
                    {Object.entries(MOTIFS_REFUS).map(([code, m]) => (
                        <button key={code} type="button" onClick={() => onChoisir(code)} aria-pressed={motif === code}
                            className={`w-full text-left p-4 rounded-xl border-2 cursor-pointer ${
                                motif === code ? "border-red-400 bg-red-50" : "border-slate-200 hover:bg-slate-50"}`}>
                            <span className="block font-semibold text-slate-900">{m.libelle}</span>
                            <span className="flex items-start gap-1 text-xs text-slate-500 mt-1">
                                <TriangleAlert className="w-3.5 h-3.5 shrink-0 mt-px" /> {m.consequence}
                            </span>
                        </button>
                    ))}

                    <div className="grid grid-cols-2 gap-3 pt-1">
                        <button type="button" onClick={onAnnuler}
                            className="h-12 rounded-xl text-slate-500 font-medium cursor-pointer">
                            Annuler
                        </button>
                        {/* Désactivé tant qu'aucun motif n'est choisi */}
                        <button type="button" onClick={onConfirmer} disabled={!motif || envoi}
                            className="h-12 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed">
                            Confirmer le refus
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default MissionProposee;
