import { useState } from "react";
import { Check, CircleCheck, Flag, MapPin, PackageOpen, Route, ShieldAlert, Siren, UserRound, X } from "lucide-react";
import { BadgeUrgence, Materiel } from "../Badges";
import { formaterHeure } from "../../services/referentiel";

// Les 5 étapes du parcours d'une mission (CDC §5.5).
// ACCEPTE : l'agent est « En route » vers le patient ; EN_TRANSIT : le patient est « Transporté ».
const ETAPES = ["En route", "Prise en charge", "Transport", "Arrivée", "Terminé"];
const ETAPE_COURANTE = { ACCEPTE: 0, EN_TRANSIT: 2 };

// Mission acceptée ou en transit : où en est l'agent, ce qu'il doit faire, puis le scan de l'étape.
function MissionEnCours({ mission, onScanDepart, onScanArrivee }) {
    const enRoute = mission.statut === "ACCEPTE";

    return (
        <div className="space-y-4">
            {/* Titre et niveau d'urgence */}
            <div className="flex items-center justify-between gap-3">
                <p className="text-xl font-bold text-slate-900">{enRoute ? "Rejoignez le patient" : "Transport en cours"}</p>
                <BadgeUrgence niveau={mission.niveau_urgence} />
            </div>

            <EtapesParcours courante={ETAPE_COURANTE[mission.statut]} />

            {/* Rappel de la mission : patient, lieu à rejoindre, matériel, consigne */}
            <section className="bg-white rounded-3xl shadow-sm divide-y divide-slate-100">
                <div className="p-5 flex items-center gap-4">
                    <span className="w-12 h-12 rounded-2xl bg-primaire-clair flex items-center justify-center shrink-0">
                        <UserRound className="w-6 h-6 text-primaire" />
                    </span>
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Patient</p>
                        <p className="text-lg font-bold text-slate-900">{mission.patient_nom} {mission.patient_prenom}</p>
                    </div>
                </div>

                {/* En route : le point de départ ; en transport : la destination */}
                <div className="p-5 flex items-start gap-3">
                    {enRoute
                        ? <MapPin className="w-5 h-5 text-primaire shrink-0 mt-0.5" />
                        : <Flag className="w-5 h-5 text-emerald-700 shrink-0 mt-0.5" />}
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                            {enRoute ? "Point de départ" : "Destination"}
                        </p>
                        <p className="font-semibold text-slate-900">
                            {enRoute ? mission.noeud_source_nom : mission.noeud_destination_nom}
                        </p>
                        {/* Estimation du serveur : temps de trajet de l'agent jusqu'au patient */}
                        {enRoute && mission.arrivee_estimee && (
                            <p className="text-sm text-slate-500">Arrivée estimée à {formaterHeure(mission.arrivee_estimee)}</p>
                        )}
                        {!enRoute && mission.duree_estimee != null && (
                            <p className="text-sm text-slate-500">Environ {Math.max(1, Math.round(mission.duree_estimee))} min de trajet</p>
                        )}
                    </div>
                </div>

                {/* En route seulement : matériel à récupérer au dépôt avant de rejoindre le patient */}
                {enRoute && mission.materiel_requis !== "RIEN" && (
                    <div className="p-5 flex items-center justify-between gap-3">
                        <p className="flex items-center gap-2 text-sm text-slate-500">
                            <PackageOpen className="w-5 h-5 text-slate-400" />
                            {mission.materiel_deja_dispo ? "Déjà auprès du patient" : "À prendre au dépôt"}
                        </p>
                        <Materiel code={mission.materiel_requis} />
                    </div>
                )}

                {mission.consigne && (
                    <div className="p-5">
                        <p className="p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 text-sm flex items-start gap-2">
                            <ShieldAlert className="w-5 h-5 shrink-0" />
                            <span><span className="font-semibold">Consigne :</span> {mission.consigne}</span>
                        </p>
                    </div>
                )}
            </section>

            {/* L'action de l'étape : scan de départ, ou scan d'arrivée */}
            {enRoute
                ? <ScanDepart urgent={mission.niveau_urgence === "URGENT"} salle={mission.noeud_source_nom} onValider={onScanDepart} />
                : <ScanArrivee salle={mission.noeud_destination_nom} onValider={onScanArrivee} />}

            {/* En transport : l'itinéraire calculé par Dijkstra jusqu'à la destination */}
            {!enRoute && (
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
            )}
        </div>
    );
}

// Frise des 5 étapes : terminées en vert (coche), étape courante en bleu, suivantes en gris
function EtapesParcours({ courante }) {
    return (
        <ol className="grid grid-cols-5 gap-1 bg-white rounded-2xl shadow-sm px-2 py-3">
            {ETAPES.map((libelle, i) => {
                const faite = i < courante;
                const enCours = i === courante;
                return (
                    <li key={libelle} aria-current={enCours ? "step" : undefined}
                        className="flex flex-col items-center gap-1 text-center">
                        <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                            faite ? "bg-emerald-600 text-white"
                                : enCours ? "bg-primaire text-white ring-4 ring-primaire-clair"
                                    : "bg-slate-100 text-slate-400"}`}>
                            {faite ? <Check className="w-4 h-4" /> : i + 1}
                        </span>
                        <span className={`text-[11px] leading-tight ${enCours ? "font-bold text-primaire" : "text-slate-500"}`}>
                            {libelle}
                        </span>
                    </li>
                );
            })}
        </ol>
    );
}

// Champ de saisie d'un code (tag NFC ou bracelet).
// Il sera rempli automatiquement par la lecture NFC / QR (tâche suivante) ; en attendant, on tape le code.
function ChampCode({ id, libelle, exemple, valeur, onChange }) {
    return (
        <label htmlFor={id} className="block">
            <span className="block text-sm font-semibold text-slate-700 mb-1">{libelle}</span>
            <input id={id} value={valeur} onChange={(e) => onChange(e.target.value)} required
                placeholder={exemple} autoComplete="off" autoCapitalize="characters" spellCheck={false}
                className="w-full h-12 px-4 rounded-xl border border-slate-300 font-mono uppercase placeholder:normal-case placeholder:font-sans focus:outline-none focus:ring-2 focus:ring-primaire" />
        </label>
    );
}

// Envoie un scan au serveur et garde son message d'erreur pour l'afficher sous le formulaire
// (ex : « Ce bracelet n'est pas celui du patient de la mission : vérifiez son identité »).
function useEnvoiScan(onValider) {
    const [envoi, setEnvoi] = useState(false);
    const [erreur, setErreur] = useState("");

    async function envoyer(corps) {
        setErreur("");
        setEnvoi(true);
        try {
            await onValider(corps);
        } catch (err) {
            setErreur(err.message);
        } finally {
            setEnvoi(false);
        }
    }

    return { envoi, erreur, envoyer };
}

const boutonValider = "w-full h-14 rounded-2xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-60 text-white text-base font-bold flex items-center justify-center gap-2 cursor-pointer";

// Prise en charge : tag de la salle de départ (preuve de présence) + bracelet du patient (identité)
function ScanDepart({ urgent, salle, onValider }) {
    const [tag, setTag] = useState("");
    const [bracelet, setBracelet] = useState("");
    // Urgence vitale : départ sans scan, demandé en deux temps pour éviter un appui par erreur
    const [confirmerForcage, setConfirmerForcage] = useState(false);
    const { envoi, erreur, envoyer } = useEnvoiScan(onValider);

    function valider(e) {
        e.preventDefault();
        envoyer({ tag_nfc: tag, code_bracelet: bracelet });
    }

    return (
        <form onSubmit={valider} className="bg-white rounded-3xl shadow-sm p-5 space-y-4">
            <div>
                <p className="font-bold text-slate-900">Prise en charge du patient</p>
                <p className="text-sm text-slate-500">Arrivé en {salle} : scannez le tag de la salle, puis le bracelet du patient.</p>
            </div>
            <ChampCode id="tag-depart" libelle="Tag NFC de la salle" exemple="NFC-…" valeur={tag} onChange={setTag} />
            <ChampCode id="bracelet" libelle="Bracelet du patient (QR code)" exemple="QR-…" valeur={bracelet} onChange={setBracelet} />

            {erreur && <p role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur}</p>}

            <button type="submit" disabled={envoi} className={boutonValider}>
                <CircleCheck className="w-5 h-5" /> Valider la prise en charge
            </button>

            {/* Réservé aux missions URGENT : le serveur refuse le forçage pour les autres */}
            {urgent && !confirmerForcage && (
                <button type="button" onClick={() => setConfirmerForcage(true)} disabled={envoi}
                    className="w-full h-12 rounded-2xl border-2 border-red-200 text-red-700 font-semibold flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60">
                    <Siren className="w-5 h-5" /> Urgence vitale : partir sans scan
                </button>
            )}
            {urgent && confirmerForcage && (
                <div className="p-3 rounded-2xl bg-red-50 border border-red-200 space-y-3">
                    <p className="text-sm text-red-700">
                        Le départ sans scan est inscrit dans le journal de la mission. À utiliser seulement si le tag ou le bracelet est illisible.
                    </p>
                    <div className="grid grid-cols-2 gap-3">
                        <button type="button" onClick={() => setConfirmerForcage(false)}
                            className="h-12 rounded-xl text-slate-500 font-medium cursor-pointer">
                            Annuler
                        </button>
                        <button type="button" onClick={() => envoyer({ forcer_urgence: true })} disabled={envoi}
                            className="h-12 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold cursor-pointer disabled:opacity-60">
                            Confirmer
                        </button>
                    </div>
                </div>
            )}
        </form>
    );
}

// Arrivée : tag de la salle de destination ; la mission est alors terminée
function ScanArrivee({ salle, onValider }) {
    const [tag, setTag] = useState("");
    const { envoi, erreur, envoyer } = useEnvoiScan(onValider);

    function valider(e) {
        e.preventDefault();
        envoyer(tag);
    }

    return (
        <form onSubmit={valider} className="bg-white rounded-3xl shadow-sm p-5 space-y-4">
            <div>
                <p className="font-bold text-slate-900">Arrivée à destination</p>
                <p className="text-sm text-slate-500">Arrivé en {salle} : scannez le tag de la salle pour terminer la mission.</p>
            </div>
            <ChampCode id="tag-arrivee" libelle="Tag NFC de la salle" exemple="NFC-…" valeur={tag} onChange={setTag} />

            {erreur && <p role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur}</p>}

            <button type="submit" disabled={envoi} className={boutonValider}>
                <Flag className="w-5 h-5" /> Terminer la mission
            </button>
        </form>
    );
}

// Dernière étape « Terminé » : confirmation affichée après le scan d'arrivée, jusqu'à ce que l'agent la ferme
export function MissionTerminee({ mission, onFermer }) {
    return (
        <div role="status" className="mb-4 p-4 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-start gap-3">
            <CircleCheck className="w-6 h-6 text-emerald-700 shrink-0" />
            <div className="flex-1">
                <p className="font-bold text-emerald-800">Mission terminée</p>
                <p className="text-sm text-emerald-700">
                    {mission.patient_nom} {mission.patient_prenom} déposé(e) en {mission.noeud_destination_nom}
                    {mission.date_fin && ` à ${formaterHeure(mission.date_fin)}`}.
                </p>
            </div>
            <button type="button" onClick={onFermer} aria-label="Fermer" className="p-1 text-emerald-700 cursor-pointer">
                <X className="w-5 h-5" />
            </button>
        </div>
    );
}

export default MissionEnCours;
