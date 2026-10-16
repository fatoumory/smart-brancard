import { useEffect, useState } from "react";
import { Bell, ChevronDown,CircleAlert, CircleCheck, Clock, Coffee, Moon, Navigation, UtensilsCrossed } from "lucide-react";

// À la fin d'une pause, le serveur remet l'agent disponible (sa tâche de fond passe toutes les 5 s) :
// on relit le profil un peu après, pour afficher le nouveau statut
const DELAI_RELECTURE_MS = 6000;

const boutonVert = "w-full h-14 rounded-2xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-60 text-white text-base font-bold flex items-center justify-center gap-2 cursor-pointer";


// Équipe de jour de 6 h à 20 h, équipe de nuit sinon (maquette)
function estEquipeDeJour() {
    const heure = new Date().getHours();
    return heure >= 6 && heure < 20;
} 

function optionsPause() {
    return estEquipeDeJour()
        ? [{ libelle: "Pause déjeuner", minutes: 45, icone: UtensilsCrossed },
            { libelle: "Pause courte", minutes: 15, icone: Coffee }]
        : [{ libelle: "Pause dîner / nuit", minutes: 45, icone: Moon },
            { libelle: "Pause courte", minutes: 15, icone: Coffee }];
}

// Onglet « Mission » : ce que voit l'agent selon son statut.
// La réception d'une mission (accepter / refuser) arrive avec les routes de mission du Sprint 3.
function EcranMission({ moi, changerStatut, envoi, rechargerProfil }) {
    const [choixPause, setChoixPause] = useState(false);

    // La durée choisie est envoyée au serveur, qui calcule l'heure de fin (fin_pause)
    function commencerPause(minutes) {
        setChoixPause(false);
        changerStatut("EN_PAUSE", minutes);
    }

    // Retour volontaire avant la fin de la pause, ou sortie de l'état « indisponible »
    function reprendre() {
        changerStatut("DISPONIBLE");
    }

    if (moi.statut === "EN_PAUSE") {
        return <EnPause finPause={moi.fin_pause} onReprendre={reprendre} onFin={rechargerProfil} envoi={envoi} />;
    }

    if (moi.statut === "INDISPONIBLE") {
        return (
            <Etat icone={CircleAlert} couleur="text-red-700" fond="bg-red-50" titre="Indisponible"
                texte="Vous ne recevrez aucune mission tant que vous ne repassez pas en disponible.">
                <button type="button" onClick={reprendre} disabled={envoi} className={boutonVert}>
                    <CircleCheck className="w-5 h-5" /> Je suis de nouveau disponible
                </button>
            </Etat>
        );
    }

    if (moi.statut === "EN_MISSION") {
        return (
            <Etat icone={Navigation} couleur="text-primaire" fond="bg-primaire-clair" titre="Mission en cours"
                texte="Les étapes de votre mission s'afficheront ici." />
        );
    }

    // DISPONIBLE
    return (
        <Etat icone={CircleCheck} couleur="text-emerald-700" fond="bg-emerald-50" titre="Disponible"
            texte="En attente d'une mission de la régulation.">
            <p className="w-full p-4 rounded-2xl bg-primaire-clair text-primaire text-sm flex items-start gap-3 text-left">
                <Bell className="w-5 h-5 shrink-0" />
                La mission apparaîtra ici dès que la régulation vous l'aura attribuée.
            </p>
            <button type="button" onClick={() => setChoixPause((o) => !o)} disabled={envoi}
                aria-expanded={choixPause} aria-controls="choix-pause"
                className="w-full h-12 rounded-2xl bg-white border border-slate-200 text-slate-600 font-semibold flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60">
                <Clock className="w-5 h-5 text-slate-400" /> Demander une pause
                <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${choixPause ? "rotate-180" : ""}`} />
            </button>
            <ChoixPause ouvert={choixPause} envoi={envoi}
                onChoisir={commencerPause} onAnnuler={() => setChoixPause(false)} />

        </Etat>
    );
}

// Écran centré : grande icône, titre, explication, puis les actions possibles
function Etat({ icone: Icone, couleur, fond, titre, texte, children }) {
    return (
        <div className="flex flex-col items-center text-center gap-5 pt-6">
            <span className={`w-24 h-24 rounded-full flex items-center justify-center ${fond}`}>
                <Icone className={`w-12 h-12 ${couleur}`} />
            </span>
            <div>
                <p className={`text-2xl font-bold ${couleur}`}>{titre}</p>
                <p className="text-slate-500 mt-2">{texte}</p>
            </div>
            {children}
        </div>
    );
}

// Pause avec compte à rebours, calculé à partir de l'heure de fin donnée par le serveur (fin_pause).
// À la fin, c'est le serveur qui remet l'agent disponible : le téléphone se contente de relire le profil.
function EnPause({ finPause, onReprendre, onFin, envoi }) {
    const [maintenant, setMaintenant] = useState(() => Date.now());
    // Temps restant en millisecondes (null si le serveur n'a pas donné d'heure de fin)
    const restantMs = finPause ? Math.max(0, new Date(finPause).getTime() - maintenant) : null;

    // Battement de l'horloge : l'affichage est recalculé chaque seconde
    useEffect(() => {
        if (!finPause) return undefined;
        const minuteur = setInterval(() => setMaintenant(Date.now()), 1000);
        return () => clearInterval(minuteur);
    }, [finPause]);

    // Compte à rebours terminé : on laisse au serveur le temps de remettre l'agent disponible,
    // puis on relit le profil. L'effet ne se relance que quand restantMs change : une seule fois à 0.
    useEffect(() => {
        if (restantMs !== 0) return undefined;
        const minuteur = setTimeout(onFin, DELAI_RELECTURE_MS);
        return () => clearTimeout(minuteur);
    }, [restantMs, onFin]);

    // Format horloge mm:ss (ex : 754 s -> "12:34")
    const secondes = Math.ceil((restantMs ?? 0) / 1000);
    const affichage = `${String(Math.floor(secondes / 60)).padStart(2, "0")}:${String(secondes % 60).padStart(2, "0")}`;

    return (
        <Etat icone={Clock} couleur="text-orange-600" fond="bg-orange-50" titre="En pause"
            texte={`${estEquipeDeJour() ? "Équipe de jour" : "Équipe de nuit"} · reprise automatique à la fin du compte à rebours`}>
            {restantMs !== null && (
                <div className="w-full bg-white rounded-3xl shadow-sm py-6 px-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Temps restant</p>
                    <p className="text-6xl font-extrabold font-mono text-orange-600 mt-2">{affichage}</p>
                    {/* Fin atteinte : on attend la confirmation du serveur */}
                    {restantMs === 0 && <p className="text-sm text-slate-500 mt-3">Reprise du service en cours…</p>}
                </div>
            )}

            <button type="button" onClick={onReprendre} disabled={envoi} className={boutonVert}>
                <CircleCheck className="w-5 h-5" /> Reprendre le service
            </button>
        </Etat>
    );
}

// Choix de la durée de la pause : se déplie en douceur sous le bouton, dans la page
// (pas de fenêtre par-dessus l'écran). La hauteur passe de 0 à sa taille naturelle.
function ChoixPause({ ouvert, envoi, onChoisir, onAnnuler }) {
    return (
        <div id="choix-pause" inert={!ouvert}
            className={`grid w-full transition-all duration-300 ease-out motion-reduce:transition-none ${
                ouvert ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
            {/* overflow-hidden : le contenu est masqué tant que la hauteur n'est pas dépliée */}
            <div className="overflow-hidden">
                <div className="bg-white rounded-2xl border border-slate-200 p-3 space-y-2 text-left">
                    <p className="px-1 text-sm text-slate-500">
                        {estEquipeDeJour() ? "Équipe de jour" : "Équipe de nuit"} · choisissez la durée
                    </p>
                    {optionsPause().map((o) => (
                        <button key={o.libelle} type="button" onClick={() => onChoisir(o.minutes)} disabled={envoi}
                            className="w-full flex items-center gap-4 p-4 rounded-xl border border-slate-200 hover:bg-orange-50 hover:border-orange-200 cursor-pointer disabled:opacity-60">
                            <o.icone className="w-6 h-6 text-orange-600" />
                            <span className="flex-1 text-left font-semibold text-slate-900">{o.libelle}</span>
                            <span className="text-slate-500">{o.minutes} min</span>
                        </button>
                    ))}
                    <button type="button" onClick={onAnnuler}
                        className="w-full py-2 text-slate-500 font-medium cursor-pointer">
                        Annuler
                    </button>
                </div>
            </div>
        </div>
    );
}


export default EcranMission;
