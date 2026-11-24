import { useEffect, useEffectEvent, useState } from "react";
import { Flag, House, MapPin, Radio, RadioTower, UserRound, X } from "lucide-react";
import EnTete from "../components/EnTete";
import { Reservation } from "../components/dashboard/AgentsTerrain";
import IndicateurTempsReel from "../components/IndicateurTempsReel";
import { useDonnees } from "../hooks/useDonnees";
import { detecterBadge, listerBrancardiers, listerMissions, listerNoeuds } from "../services/missionService";
import { STATUTS_AGENT, formaterHeure } from "../services/referentiel";

// Un vrai récepteur de salle capte le badge plusieurs fois par minute : le simulateur renvoie
// la position de chaque agent posé sur le plan toutes les 5 s. C'est assez fréquent pour mesurer
// les 30 s de présence qui terminent une mission à l'arrivée.
const INTERVALLE_BADGE_MS = 5000;
// Placements gardés dans ce navigateur : un rechargement de la page ne remet pas tout le monde à zéro
const CLE_STOCKAGE = "simulateur_placements";

// Ordre d'affichage des lieux d'un étage : les services d'abord, puis le dépôt et les passages
const ORDRE_TYPES = { SERVICE: 0, DEPOT_MATERIEL: 1, COULOIR: 2, ASCENSEUR: 3 };
const STYLE_TYPES = {
    SERVICE: "bg-white border-slate-200",
    DEPOT_MATERIEL: "bg-amber-50/60 border-amber-200",
    COULOIR: "bg-slate-50 border-slate-200",
    ASCENSEUR: "bg-primaire-clair/60 border-blue-200",
};

function lirePlacements() {
    try {
        return JSON.parse(localStorage.getItem(CLE_STOCKAGE)) ?? {};
    } catch {
        return {};
    }
}

// Où l'agent doit aller pour sa mission en cours : le patient (mission acceptée) ou la destination (en transit)
function objectifDe(agentId, missions) {
    const m = missions.find((x) => x.brancardier_id === agentId && (x.statut === "ACCEPTE" || x.statut === "EN_TRANSIT"));
    if (!m) return null;
    return m.statut === "ACCEPTE"
        ? { noeudId: m.noeud_source_id, nom: m.noeud_source_nom, libelle: "Rejoindre le patient" }
        : { noeudId: m.noeud_destination_id, nom: m.noeud_destination_nom, libelle: "Déposer le patient" };
}

// Simulateur des badges BLE (prototype) : remplace les récepteurs installés dans les salles.
// La personne qui fait la démonstration choisit un agent, puis la salle où il se trouve :
// le simulateur envoie « badge de l'agent capté dans cette salle » toutes les 5 s, comme un ESP32.
// L'agent, lui, n'a plus rien à déclarer sur son téléphone.
function Simulateur() {
    const noeuds = useDonnees(listerNoeuds);
    const agents = useDonnees(listerBrancardiers, 30000, ["agents"]);
    const missions = useDonnees(listerMissions, 30000, ["missions"]);
    // { idAgent: idLieu } : agents posés sur le plan, dont le badge est envoyé
    const [placements, setPlacements] = useState(lirePlacements);
    // Agent sélectionné, que le prochain clic sur le plan va déplacer
    const [choisi, setChoisi] = useState(null);
    // Dernier envoi : heure, et message d'erreur par agent (ex : compte désactivé)
    const [heureEnvoi, setHeureEnvoi] = useState(null);
    const [erreurs, setErreurs] = useState({});

    const lieux = noeuds.donnees ?? [];
    const nomDe = Object.fromEntries(lieux.map((l) => [l.id, l.nom_salle]));
    // Seuls les comptes actifs ont un badge en service
    const listeAgents = (agents.donnees ?? []).filter((a) => a.est_actif);
    const listeMissions = missions.donnees ?? [];
    const etages = [...new Set(lieux.map((l) => l.etage))].sort((a, b) => a - b);

    // Sauvegarde des placements dans ce navigateur (sans conséquence si le stockage est refusé)
    useEffect(() => {
        try {
            localStorage.setItem(CLE_STOCKAGE, JSON.stringify(placements));
        } catch {
            // stockage indisponible : les placements restent seulement en mémoire
        }
    }, [placements]);

    // Envoie un badge et note le résultat pour cet agent
    async function envoyer(agentId, noeudId) {
        try {
            await detecterBadge(Number(agentId), noeudId);
            setErreurs((e) => ({ ...e, [agentId]: undefined }));
        } catch (err) {
            setErreurs((e) => ({ ...e, [agentId]: err.message }));
        }
    }

    // Envoi des badges de tous les agents posés sur le plan.
    // useEffectEvent : lit toujours les derniers placements, sans relancer le minuteur
    const envoyerTout = useEffectEvent(async () => {
        const entrees = Object.entries(placements);
        if (entrees.length === 0) return;
        await Promise.all(entrees.map(([agentId, noeudId]) => envoyer(agentId, noeudId)));
        setHeureEnvoi(new Date().toISOString());
    });

    // Toutes les 5 s, tant que la page est ouverte
    useEffect(() => {
        const minuteur = setInterval(envoyerTout, INTERVALLE_BADGE_MS);
        return () => clearInterval(minuteur);
    }, []);

    // Pose l'agent dans une salle : son badge y est capté tout de suite, puis toutes les 5 s
    function placer(agentId, noeudId) {
        setPlacements((p) => ({ ...p, [agentId]: noeudId }));
        envoyer(agentId, noeudId).then(() => setHeureEnvoi(new Date().toISOString()));
    }

    // Badge hors de portée de tout récepteur (agent parti, badge oublié) : plus aucun envoi
    function retirer(agentId) {
        setPlacements((p) => {
            const copie = { ...p };
            delete copie[agentId];
            return copie;
        });
    }

    const nomChoisi = listeAgents.find((a) => a.id === choisi)?.prenom;

    return (
        <div className="min-h-screen">
            <EnTete />
            <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Simulateur de badges</h1>
                        <p className="text-sm text-slate-500 max-w-2xl">
                            Remplace les récepteurs BLE des salles. Choisissez un agent, puis la salle où il se trouve :
                            son badge y est capté toutes les 5 s. Après 30 s dans la salle d'arrivée, la mission se termine seule.
                        </p>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-slate-500">
                        <IndicateurTempsReel />
                        {heureEnvoi && (
                            <span className="flex items-center gap-1.5"><RadioTower className="w-4 h-4" /> Envoi à {formaterHeure(heureEnvoi)}</span>
                        )}
                    </div>
                </div>

                {(noeuds.erreur || agents.erreur) && (
                    <p className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{noeuds.erreur || agents.erreur}</p>
                )}

                <div className="grid grid-cols-1 lg:grid-cols-[20rem_1fr] gap-6 items-start">
                    {/* Agents : un clic pour choisir celui qu'on déplace */}
                    <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                        <h2 className="flex items-center gap-2 p-4 border-b border-slate-100 font-bold text-slate-900">
                            <UserRound className="w-5 h-5 text-primaire" /> Agents
                        </h2>
                        {listeAgents.length === 0 && <p className="p-4 text-sm text-slate-500">Aucun brancardier actif.</p>}
                        <ul className="divide-y divide-slate-100">
                            {listeAgents.map((a) => {
                                const statut = STATUTS_AGENT[a.statut] ?? STATUTS_AGENT.INDISPONIBLE;
                                const lieu = placements[a.id];
                                const objectif = objectifDe(a.id, listeMissions);
                                return (
                                    <li key={a.id} className={choisi === a.id ? "bg-primaire-clair" : ""}>
                                        <button type="button" onClick={() => setChoisi(choisi === a.id ? null : a.id)}
                                            aria-pressed={choisi === a.id}
                                            className="w-full text-left px-4 pt-3 pb-2 cursor-pointer">
                                            <span className="flex items-center justify-between gap-2">
                                                <span className="font-semibold text-slate-900">{a.prenom} {a.nom}</span>
                                                <span className={`flex items-center gap-1.5 text-xs font-medium ${statut.texte}`}>
                                                    <span className={`w-2 h-2 rounded-full ${statut.point}`} /> {statut.libelle}
                                                </span>
                                            </span>
                                            {(a.poste_nom || a.reserve_urgent) && (
                                                <span className="flex flex-wrap items-center gap-2 text-xs mt-1 text-slate-500">
                                                    <Reservation agent={a} />
                                                    {a.poste_nom && `Poste : ${a.poste_nom}`}
                                                </span>
                                            )}
                                            <span className={`flex items-center gap-1 text-xs mt-1 ${lieu ? "text-slate-600" : "text-slate-400"}`}>
                                                {lieu ? <Radio className="w-3.5 h-3.5 text-emerald-600" /> : <MapPin className="w-3.5 h-3.5" />}
                                                {lieu ? `Badge capté : ${nomDe[lieu] ?? `lieu ${lieu}`}` : "Badge hors de portée"}
                                            </span>
                                        </button>
                                        <div className="px-4 pb-3 flex flex-wrap gap-2">
                                            {/* Raccourci de démonstration : l'endroit où sa mission l'attend */}
                                            {objectif && lieu !== objectif.noeudId && (
                                                <button type="button" onClick={() => placer(a.id, objectif.noeudId)}
                                                    className="px-2.5 py-1 rounded-lg bg-primaire text-white text-xs font-semibold flex items-center gap-1 cursor-pointer">
                                                    <Flag className="w-3.5 h-3.5" /> {objectif.libelle} : {objectif.nom}
                                                </button>
                                            )}
                                            {/* Agent posté, sans mission : il retourne attendre à son poste */}
                                            {!objectif && a.poste_id && lieu !== a.poste_id && (
                                                <button type="button" onClick={() => placer(a.id, a.poste_id)}
                                                    className="px-2.5 py-1 rounded-lg bg-white border border-primaire text-primaire text-xs font-semibold flex items-center gap-1 cursor-pointer">
                                                    <House className="w-3.5 h-3.5" /> Retour au poste : {a.poste_nom}
                                                </button>
                                            )}
                                            {lieu && (
                                                <button type="button" onClick={() => retirer(a.id)}
                                                    className="px-2.5 py-1 rounded-lg border border-slate-200 text-slate-500 text-xs font-medium flex items-center gap-1 cursor-pointer hover:bg-slate-50">
                                                    <X className="w-3.5 h-3.5" /> Hors de portée
                                                </button>
                                            )}
                                        </div>
                                        {erreurs[a.id] && <p role="alert" className="px-4 pb-3 text-xs text-red-700">{erreurs[a.id]}</p>}
                                    </li>
                                );
                            })}
                        </ul>
                    </section>

                    {/* Plan de l'hôpital, étage par étage : un clic pose l'agent choisi dans la salle */}
                    <section className="space-y-4">
                        <p className={`p-3 rounded-xl text-sm ${choisi !== null
                            ? "bg-primaire-clair text-primaire font-semibold" : "bg-white border border-slate-200 text-slate-500"}`}>
                            {choisi !== null ? `Cliquez sur la salle où se trouve ${nomChoisi ?? "l'agent"}.` : "Choisissez d'abord un agent dans la liste."}
                        </p>
                        {etages.map((etage) => (
                            <div key={etage} className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4">
                                <h2 className="font-bold text-slate-900 mb-3">{etage === 0 ? "Rez-de-chaussée" : `Étage ${etage}`}</h2>
                                <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3">
                                    {lieux.filter((l) => l.etage === etage)
                                        .sort((a, b) => ORDRE_TYPES[a.type_noeud] - ORDRE_TYPES[b.type_noeud] || a.nom_salle.localeCompare(b.nom_salle))
                                        .map((l) => {
                                            const presents = listeAgents.filter((a) => placements[a.id] === l.id);
                                            // Agents attendus dans cette salle pour leur mission : repère pour la démonstration
                                            const attendus = listeAgents.filter((a) => objectifDe(a.id, listeMissions)?.noeudId === l.id);
                                            return (
                                                <button key={l.id} type="button" onClick={() => choisi !== null && placer(choisi, l.id)}
                                                    disabled={choisi === null}
                                                    className={`min-h-24 text-left p-3 rounded-xl border-2 flex flex-col gap-2 transition-colors ${STYLE_TYPES[l.type_noeud]} ${
                                                        choisi !== null ? "cursor-pointer hover:border-primaire" : "cursor-default"}`}>
                                                    <span className={`text-sm ${l.type_noeud === "SERVICE" ? "font-bold text-slate-900" : "font-medium text-slate-600"}`}>
                                                        {l.nom_salle}
                                                    </span>
                                                    {attendus.length > 0 && (
                                                        <span className="flex items-center gap-1 text-[11px] font-semibold text-primaire">
                                                            <Flag className="w-3 h-3" /> Attendu : {attendus.map((a) => a.prenom).join(", ")}
                                                        </span>
                                                    )}
                                                    <span className="flex flex-wrap gap-1 mt-auto">
                                                        {presents.map((a) => (
                                                            <span key={a.id} className="px-2 py-0.5 rounded-full bg-emerald-600 text-white text-xs font-semibold">
                                                                {a.prenom}
                                                            </span>
                                                        ))}
                                                    </span>
                                                </button>
                                            );
                                        })}
                                </div>
                            </div>
                        ))}
                    </section>
                </div>
            </main>
        </div>
    );
}

export default Simulateur;
