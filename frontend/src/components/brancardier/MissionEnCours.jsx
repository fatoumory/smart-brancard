import { useState } from "react";
import {
    Camera, Check, ChevronDown, CircleCheck, Flag, Footprints, MapPin, MessageSquareWarning, PackageOpen, PhoneCall,
    Radio, Route, ScanLine, ShieldAlert, Siren, UserRound, X,
} from "lucide-react";
import { BadgeUrgence, Materiel } from "../Badges";
import { formaterHeure } from "../../services/referentiel";
import { parler } from "../../services/voix";
import ChampScan, { LecteurQR } from "./ChampScan";

// Les 5 étapes du parcours d'une mission (CDC §5.5).
// ACCEPTE : l'agent est « En route » vers le patient ; EN_TRANSIT : le patient est « Transporté ».
const ETAPES = ["En route", "Prise en charge", "Transport", "Arrivée", "Terminé"];
const ETAPE_COURANTE = { ACCEPTE: 0, EN_TRANSIT: 2 };

// Après ce nombre d'échecs de scan, l'appel au régulateur est mis en avant
const ECHECS_AVANT_APPEL = 2;

// Raisons d'un appel au régulateur (énumération RaisonAppel du backend)
const RAISONS_APPEL = {
    BRACELET_ILLISIBLE: { libelle: "Bracelet illisible", icone: ScanLine },
    ECHECS_SCAN: { libelle: "Le scan échoue", icone: Camera },
    AUTRE: { libelle: "Autre problème", icone: MessageSquareWarning },
};

const boutonValider = "w-full h-14 rounded-2xl bg-emerald-700 hover:bg-emerald-800 disabled:opacity-60 text-white text-base font-bold flex items-center justify-center gap-2 cursor-pointer";

// Mission acceptée ou en transit (parcours à gestes réduits du Sprint 4) :
//   - en route : le badge de l'agent est détecté au point de départ (agent_au_depart), la caméra s'ouvre
//     seule et l'agent ne scanne que le bracelet du patient ; la voix confirme le bon patient ;
//   - en transport : l'arrivée est détectée après 30 s de présence dans la salle ; rien à faire.
// Secours : scan du tag de la salle, bouton « Arrivé », appel au régulateur.
function MissionEnCours({ mission, onScanDepart, onScanArrivee, onArrivee, onAppel }) {
    const enRoute = mission.statut === "ACCEPTE";
    // Échecs de scan successifs : à partir de 2, l'appel au régulateur est mis en avant
    const [echecs, setEchecs] = useState(0);

    return (
        <div className="space-y-4">
            {/* Titre et niveau d'urgence */}
            <div className="flex items-center justify-between gap-3">
                <p className="text-xl font-bold text-slate-900">{enRoute ? "Rejoignez le patient" : "Transport en cours"}</p>
                <BadgeUrgence niveau={mission.niveau_urgence} />
            </div>

            <EtapesParcours courante={ETAPE_COURANTE[mission.statut]} />

            {/* L'action de l'étape, en haut : c'est ce que l'agent doit voir d'abord */}
            {enRoute
                ? <PriseEnCharge mission={mission} onValider={onScanDepart} onEchec={() => setEchecs((n) => n + 1)} />
                : <Arrivee mission={mission} onScanArrivee={onScanArrivee} onArrivee={onArrivee} />}

            <AppelRegulateur enAvant={echecs >= ECHECS_AVANT_APPEL} onAppel={onAppel} />

            <FicheMission mission={mission} enRoute={enRoute} />

            {/* En transport : l'itinéraire calculé par Dijkstra jusqu'à la destination */}
            {!enRoute && <Itineraire mission={mission} />}
        </div>
    );
}

// Rappel de la mission : patient, lieu à rejoindre, matériel, consigne
function FicheMission({ mission, enRoute }) {
    return (
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
    );
}

// Itinéraire calculé par Dijkstra, étape par étape
function Itineraire({ mission }) {
    return (
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

// Envoie une action au serveur et garde son message d'erreur pour l'afficher
// (ex : « Ce bracelet n'est pas celui du patient de la mission : vérifiez son identité »).
// onEchec : appelé à chaque refus du serveur (compteur d'échecs de scan, annonce vocale)
function useEnvoi(action, onEchec) {
    const [envoi, setEnvoi] = useState(false);
    const [erreur, setErreur] = useState("");

    async function envoyer(...args) {
        setErreur("");
        setEnvoi(true);
        try {
            await action(...args);
        } catch (err) {
            setErreur(err.message);
            onEchec?.(err);
        } finally {
            setEnvoi(false);
        }
    }

    return { envoi, erreur, envoyer };
}

// Prise en charge au point de départ.
// Badge détecté dans la salle : la caméra s'ouvre seule, un seul scan (le bracelet du patient).
// Badge pas encore détecté : l'agent est en chemin ; en secours, il peut scanner le tag de la salle.
function PriseEnCharge({ mission, onValider, onEchec }) {
    const auDepart = mission.agent_au_depart;
    const urgent = mission.niveau_urgence === "URGENT";
    // Caméra fermée par l'agent, ou après une lecture (il la rouvre d'un toucher)
    const [cameraFermee, setCameraFermee] = useState(false);
    const [saisie, setSaisie] = useState("");
    const [secours, setSecours] = useState(false);
    const [confirmerForcage, setConfirmerForcage] = useState(false);

    // Résultat dit à voix haute : l'agent a les mains sur le patient, il n'a pas à lire l'écran
    const { envoi, erreur, envoyer } = useEnvoi(async (corps) => {
        const resultat = await onValider(corps);
        // Sans réseau, le bracelet n'a pas encore pu être vérifié par le serveur : on ne dit pas « bon patient »
        parler(resultat?.horsLigne
            ? "Scan enregistré sans réseau. Il sera vérifié dès le retour du réseau."
            : `Bon patient. Direction ${mission.noeud_destination_nom}.`);
    }, (err) => {
        onEchec();
        // « Ce bracelet n'est pas celui du patient de la mission » : alerte claire, sinon le message du serveur
        parler(err.message.includes("bracelet") ? "Attention, mauvais patient. Vérifiez le bracelet." : err.message);
    });

    function scannerBracelet(code) {
        setCameraFermee(true);
        envoyer({ code_bracelet: code });
    }

    return (
        <section className="bg-white rounded-3xl shadow-sm p-5 space-y-4">
            {auDepart ? (
                <>
                    <div className="flex items-start gap-3">
                        <Radio className="w-6 h-6 text-emerald-600 shrink-0" />
                        <div>
                            <p className="font-bold text-slate-900">Vous êtes en {mission.noeud_source_nom}</p>
                            <p className="text-sm text-slate-500">Votre badge a été détecté : scannez le bracelet du patient.</p>
                        </div>
                    </div>
                    {/* La caméra s'ouvre d'elle-même dès que le badge est détecté au départ */}
                    {!cameraFermee && !envoi ? (
                        <LecteurQR onLu={scannerBracelet} onFermer={() => setCameraFermee(true)} />
                    ) : (
                        <button type="button" onClick={() => setCameraFermee(false)} disabled={envoi} className={boutonValider}>
                            <Camera className="w-5 h-5" /> {envoi ? "Vérification…" : "Scanner le bracelet"}
                        </button>
                    )}
                    {/* Bracelet abîmé, caméra en panne : le code imprimé sous le QR peut être tapé */}
                    <form onSubmit={(e) => { e.preventDefault(); envoyer({ code_bracelet: saisie }); }} className="flex gap-2">
                        <input value={saisie} onChange={(e) => setSaisie(e.target.value)} required placeholder="Code du bracelet (QR-…)"
                            aria-label="Code du bracelet" autoComplete="off" autoCapitalize="characters" spellCheck={false}
                            className="flex-1 min-w-0 h-12 px-4 rounded-xl border border-slate-300 font-mono uppercase placeholder:normal-case placeholder:font-sans focus:outline-none focus:ring-2 focus:ring-primaire" />
                        <button type="submit" disabled={envoi}
                            className="px-4 h-12 rounded-xl bg-slate-100 text-slate-700 font-semibold cursor-pointer disabled:opacity-60">
                            Valider
                        </button>
                    </form>
                </>
            ) : (
                <div className="flex items-start gap-3">
                    <Footprints className="w-6 h-6 text-primaire shrink-0" />
                    <div>
                        <p className="font-bold text-slate-900">Rendez-vous en {mission.noeud_source_nom}</p>
                        <p className="text-sm text-slate-500">La caméra s'ouvrira d'elle-même dès que votre badge y sera détecté.</p>
                    </div>
                </div>
            )}

            {erreur && <p role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur}</p>}

            {/* Secours : le badge ne répond pas. Le tag de la salle prouve la présence à sa place. */}
            {!auDepart && (
                <Depliant ouvert={secours} onBasculer={() => setSecours((o) => !o)}
                    libelle="Je suis arrivé mais mon badge n'est pas détecté">
                    <ScanDepartSecours salle={mission.noeud_source_nom} envoi={envoi} onValider={envoyer} />
                </Depliant>
            )}

            {/* Réservé aux missions URGENT : le serveur refuse le forçage pour les autres */}
            {urgent && !confirmerForcage && (
                <button type="button" onClick={() => setConfirmerForcage(true)} disabled={envoi}
                    className="w-full h-12 rounded-2xl border-2 border-red-200 text-red-700 font-semibold flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60">
                    <Siren className="w-5 h-5" /> Urgence vitale : partir sans scan
                </button>
            )}
            {urgent && confirmerForcage && (
                <Confirmation texte="Le départ sans scan est inscrit dans le journal de la mission. À utiliser seulement si le bracelet est illisible."
                    envoi={envoi} onAnnuler={() => setConfirmerForcage(false)} onConfirmer={() => envoyer({ forcer_urgence: true })} />
            )}
        </section>
    );
}

// Scan de départ du Sprint 3, gardé en secours : tag de la salle + bracelet du patient
function ScanDepartSecours({ salle, envoi, onValider }) {
    const [tag, setTag] = useState("");
    const [bracelet, setBracelet] = useState("");
    return (
        <form onSubmit={(e) => { e.preventDefault(); onValider({ tag_nfc: tag, code_bracelet: bracelet }); }} className="space-y-4 pt-2">
            <p className="text-sm text-slate-500">Scannez le tag de la salle ({salle}), puis le bracelet du patient.</p>
            <ChampScan id="tag-depart" type="nfc" libelle="Tag NFC de la salle" exemple="NFC-…" valeur={tag} onChange={setTag} />
            <ChampScan id="bracelet" type="qr" libelle="Bracelet du patient (QR code)" exemple="QR-…" valeur={bracelet} onChange={setBracelet} />
            <button type="submit" disabled={envoi} className={boutonValider}>
                <CircleCheck className="w-5 h-5" /> Valider la prise en charge
            </button>
        </form>
    );
}

// Arrivée à destination : détectée par le badge après 30 s dans la salle, sans aucun geste.
// Secours : le bouton « Arrivé » (déclaration, tracée au journal) ou le scan du tag de la salle.
function Arrivee({ mission, onScanArrivee, onArrivee }) {
    const [confirmer, setConfirmer] = useState(false);
    const [scan, setScan] = useState(false);
    const [tag, setTag] = useState("");
    const { envoi, erreur, envoyer } = useEnvoi((action) => action());

    return (
        <section className="bg-white rounded-3xl shadow-sm p-5 space-y-4">
            <div className="flex items-start gap-3">
                <Radio className="w-6 h-6 text-primaire shrink-0" />
                <div>
                    <p className="font-bold text-slate-900">Direction {mission.noeud_destination_nom}</p>
                    <p className="text-sm text-slate-500">
                        Rien à faire à l'arrivée : la mission se termine seule après 30 s dans la salle, et le médecin est prévenu.
                    </p>
                </div>
            </div>

            {erreur && <p role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur}</p>}

            {/* Secours 1 : l'agent déclare lui-même l'arrivée, en deux temps pour éviter un appui par erreur */}
            {confirmer ? (
                <Confirmation texte={`Vous déclarez être arrivé en ${mission.noeud_destination_nom} avec le patient. La déclaration est inscrite au journal.`}
                    envoi={envoi} onAnnuler={() => setConfirmer(false)} onConfirmer={() => envoyer(onArrivee)} />
            ) : (
                <button type="button" onClick={() => setConfirmer(true)} disabled={envoi}
                    className="w-full h-14 rounded-2xl bg-white border-2 border-emerald-600 text-emerald-700 font-bold flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60">
                    <Flag className="w-5 h-5" /> Arrivé
                </button>
            )}

            {/* Secours 2 : le tag de la salle, comme au Sprint 3 */}
            <Depliant ouvert={scan} onBasculer={() => setScan((o) => !o)} libelle="Scanner le tag de la salle d'arrivée">
                <form onSubmit={(e) => { e.preventDefault(); envoyer(() => onScanArrivee(tag)); }} className="space-y-4 pt-2">
                    <ChampScan id="tag-arrivee" type="nfc" libelle="Tag NFC de la salle" exemple="NFC-…" valeur={tag} onChange={setTag} />
                    <button type="submit" disabled={envoi} className={boutonValider}>
                        <Flag className="w-5 h-5" /> Terminer la mission
                    </button>
                </form>
            </Depliant>
        </section>
    );
}

// Appel du régulateur : l'agent est bloqué (bracelet illisible, scans qui échouent).
// Une alerte s'affiche sur le dashboard du régulateur, avec l'endroit où se trouve l'agent.
// enAvant : après plusieurs échecs, le bouton devient bien visible
function AppelRegulateur({ enAvant, onAppel }) {
    const [ouvert, setOuvert] = useState(false);
    const [envoye, setEnvoye] = useState(false);
    const { envoi, erreur, envoyer } = useEnvoi(async (raison) => {
        await onAppel(raison);
        setEnvoye(true);
        setOuvert(false);
        parler("Le régulateur est prévenu.");
    });

    if (envoye) {
        return (
            <div role="status" className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm flex items-start gap-2">
                <PhoneCall className="w-5 h-5 shrink-0" />
                <div>
                    <p><span className="font-semibold">Le régulateur est prévenu.</span> Restez auprès du patient, il va vous contacter.</p>
                    <button type="button" onClick={() => setEnvoye(false)} className="mt-1 underline cursor-pointer">Appeler à nouveau</button>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            <button type="button" onClick={() => setOuvert((o) => !o)} aria-expanded={ouvert}
                className={`w-full h-12 rounded-2xl font-semibold flex items-center justify-center gap-2 cursor-pointer ${enAvant
                    ? "bg-amber-400 text-slate-900" : "bg-white border border-slate-200 text-slate-600"}`}>
                <PhoneCall className="w-5 h-5" /> Appeler le régulateur
            </button>
            {/* La raison en images : un toucher suffit */}
            {ouvert && (
                <div className="grid grid-cols-3 gap-2">
                    {Object.entries(RAISONS_APPEL).map(([code, r]) => (
                        <button key={code} type="button" onClick={() => envoyer(code)} disabled={envoi}
                            className="p-3 rounded-xl bg-white border-2 border-slate-200 hover:border-amber-400 flex flex-col items-center gap-1 text-center cursor-pointer disabled:opacity-60">
                            <r.icone className="w-8 h-8 text-amber-600" />
                            <span className="text-xs font-semibold text-slate-800 leading-tight">{r.libelle}</span>
                        </button>
                    ))}
                </div>
            )}
            {erreur && <p role="alert" className="text-sm text-red-700">{erreur}</p>}
        </div>
    );
}

// Bloc de secours qui se déplie sous un lien discret
function Depliant({ ouvert, onBasculer, libelle, children }) {
    return (
        <div>
            <button type="button" onClick={onBasculer} aria-expanded={ouvert}
                className="w-full flex items-center justify-between gap-2 py-2 text-sm font-medium text-slate-500 cursor-pointer">
                {libelle}
                <ChevronDown className={`w-4 h-4 transition-transform ${ouvert ? "rotate-180" : ""}`} />
            </button>
            {ouvert && children}
        </div>
    );
}

// Confirmation en deux temps d'une action tracée au journal
function Confirmation({ texte, envoi, onAnnuler, onConfirmer }) {
    return (
        <div className="p-3 rounded-2xl bg-red-50 border border-red-200 space-y-3">
            <p className="text-sm text-red-700">{texte}</p>
            <div className="grid grid-cols-2 gap-3">
                <button type="button" onClick={onAnnuler} className="h-12 rounded-xl text-slate-500 font-medium cursor-pointer">
                    Annuler
                </button>
                <button type="button" onClick={onConfirmer} disabled={envoi}
                    className="h-12 rounded-xl bg-red-600 hover:bg-red-700 text-white font-bold cursor-pointer disabled:opacity-60">
                    Confirmer
                </button>
            </div>
        </div>
    );
}

// Dernière étape « Terminé » : confirmation affichée après l'arrivée (détectée, déclarée ou scannée),
// jusqu'à ce que l'agent la ferme
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
