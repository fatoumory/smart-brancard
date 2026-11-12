import { useEffect, useRef, useState } from "react";
import { FileText, Navigation, User } from "lucide-react";
import EcranMission from "../components/brancardier/EcranMission";
import EcranJournal from "../components/brancardier/EcranJournal";
import EcranProfil from "../components/brancardier/EcranProfil";
import { useDonnees } from "../hooks/useDonnees";
import { MissionTerminee } from "../components/brancardier/MissionEnCours";
import MaPosition from "../components/brancardier/MaPosition";
import ActiverSon from "../components/brancardier/ActiverSon";
import BandeauHorsLigne from "../components/brancardier/BandeauHorsLigne";
import { demarrerEnvoisAutomatiques, suivreHorsLigne } from "../services/horsLigne";
import { annoncerMission, parler } from "../services/voix";
import { accepterMission, appelerRegulateur, changerMonStatut, declarerArrivee, getMaMission, getMonJournal, getMonProfil,
    refuserMission, scannerArrivee, scannerDepart } from "../services/brancardierService";
import { STATUTS_AGENT } from "../services/referentiel";

// Profil et mission se mettent à jour par le temps réel (WebSocket). Ces rechargements réguliers
// sont un secours si la connexion temps réel est coupée : la mission reste relue souvent,
// car une proposition n'attend la réponse que 30 à 60 s
const INTERVALLE_MS = 30000;
const INTERVALLE_MISSION_MS = 10000;


// Barre de navigation du bas (maquette : Mission, Journal, Profil)
const ONGLETS = [
    { id: "mission", libelle: "Mission", titre: "Accueil", icone: Navigation },
    { id: "journal", libelle: "Journal", titre: "Journal", icone: FileText },
    { id: "profil", libelle: "Profil", titre: "Mon profil", icone: User },
];

// Application mobile du brancardier (PWA) : pensée pour un smartphone tenu à une main
function Brancardier() {
    const [onglet, setOnglet] = useState("mission");
    const [erreurStatut, setErreurStatut] = useState("");
    const [envoi, setEnvoi] = useState(false);
    const profil = useDonnees(getMonProfil, INTERVALLE_MS, ["agents"]);
    const moi = profil.donnees;
    const statut = moi && STATUTS_AGENT[moi.statut];
    // Mission proposée, acceptée ou en transit (null si l'agent n'en a pas)
    const mission = useDonnees(getMaMission, INTERVALLE_MISSION_MS, ["missions"]);
    // Mission que l'agent vient de terminer (scan d'arrivée réussi) : confirmation affichée jusqu'à fermeture
    const [missionTerminee, setMissionTerminee] = useState(null);
    // Mode hors ligne : les actions faites sans réseau partent dès son retour (et toutes les 15 s)
    useEffect(() => demarrerEnvoisAutomatiques(), []);
    // Quand la dernière action en attente est partie, on relit la mission et le profil du serveur
    const { recharger: rechargerMission } = mission;
    const { recharger: rechargerProfil } = profil;
    useEffect(() => {
        let avant = 0;
        return suivreHorsLigne(({ enAttente }) => {
            if (avant > 0 && enAttente === 0) {
                rechargerMission();
                rechargerProfil();
            }
            avant = enAttente;
        });
    }, [rechargerMission, rechargerProfil]);

    // Dernière mission annoncée : chaque nouvelle proposition n'est annoncée qu'une fois
    const derniereAnnoncee = useRef(null);

    // Nouvelle mission proposée : sonnerie, vibration et annonce vocale (lieu, urgence, matériel),
    // pour que l'agent n'ait pas à regarder son téléphone
    const proposee = mission.donnees?.statut === "PROPOSE" ? mission.donnees : null;
    useEffect(() => {
        if (proposee && derniereAnnoncee.current !== proposee.id) {
            derniereAnnoncee.current = proposee.id;
            annoncerMission(proposee);
        }
    }, [proposee]);

    // Mission en transport : retenue pour reconnaître sa fin quand elle vient du badge
    // (30 s de présence dans la salle d'arrivée) : la mission disparaît alors de /missions/moi
    const enTransport = useRef(null);
    const enCours = mission.donnees;
    useEffect(() => {
        if (enCours?.statut === "EN_TRANSIT") {
            enTransport.current = enCours.id;
            return;
        }
        const id = enTransport.current;
        if (enCours || id === null) return;
        enTransport.current = null;
        // Plus de mission : on retrouve celle qui vient de se terminer dans le journal du jour
        getMonJournal().then((journal) => {
            const terminee = journal.find((m) => m.id === id && m.statut === "TERMINE");
            if (!terminee) return;   // annulée ou réaffectée par le régulateur
            setMissionTerminee((deja) => deja ?? terminee);
            parler(`Arrivée détectée en ${terminee.noeud_destination_nom}. Mission terminée.`);
        }, () => {});
    }, [enCours]);

    // Change le statut sur le serveur, puis relit le profil pour afficher le nouvel état.
    // dureePauseMinutes n'est envoyé que pour une pause (30 ou 45 min) : le serveur en déduit l'heure de fin. Renvoie true si le changement a réussi
    async function changerStatut(nouveau, dureePauseMinutes) {
        setErreurStatut("");
        setEnvoi(true);
        try {
            await changerMonStatut(nouveau, dureePauseMinutes);
            profil.recharger();
            return true;
        } catch (err) {
            setErreurStatut(err.message);
            return false;
        } finally {
            setEnvoi(false);
        }
    }

    // Réponse à une mission proposée (accepter ou refuser).
    // Dans tous les cas, mission et profil sont relus : même en cas d'erreur (ex : délai de réponse
    // dépassé, « Cette mission n'attend plus de réponse »), l'écran se remet à jour.
    async function repondre(appel) {
        setErreurStatut("");
        setEnvoi(true);
        try {
            await appel();
        } catch (err) {
            setErreurStatut(err.message);
        } finally {
            setEnvoi(false);
            mission.recharger();
            profil.recharger();
        }
    }


    // Scan de départ ou d'arrivée. Pas de catch ici : une erreur (tag ou bracelet qui ne correspond pas)
    // remonte au formulaire du scan, qui l'affiche sous les champs. Dans tous les cas, mission et profil sont relus.
    async function scanner(appel) {
        try {
            return await appel();
        } finally {
            mission.recharger();
            profil.recharger();
        }
    }

    // Scan de départ : l'agent est au point de départ (le serveur enregistre aussi cette position)
    async function prendreEnCharge(corps) {
        return scanner(() => scannerDepart(mission.donnees.id, corps));
    }

    // Fin de mission par l'agent (secours) : la mission TERMINE renvoyée par le serveur est gardée
    // pour la confirmation. enTransport est vidé : la fin ne doit pas être annoncée une 2e fois.
    async function finir(appel) {
        enTransport.current = null;
        const terminee = await scanner(appel);
        setMissionTerminee(terminee);
        parler("Mission terminée.");
    }

    // Secours de l'arrivée : scan du tag de la salle, ou bouton « Arrivé »
    const terminerParScan = (tagNfc) => finir(() => scannerArrivee(mission.donnees.id, tagNfc));
    const terminerParDeclaration = () => finir(() => declarerArrivee(mission.donnees.id));

    // Appel du régulateur : une alerte s'affiche sur son dashboard
    const appeler = (raison) => appelerRegulateur(mission.donnees.id, raison);

    const titre = ONGLETS.find((o) => o.id === onglet).titre;
    // Une simple coupure de réseau est annoncée par le bandeau hors ligne, pas comme une erreur
    const erreur = erreurStatut || (profil.erreur && !profil.erreur.startsWith("Impossible de contacter") ? profil.erreur : "")
        || mission.erreur;


    return (
        <div className="min-h-screen max-w-md mx-auto bg-slate-50 flex flex-col">
            {/* En-tête bleu : nom de l'application, écran courant et statut de l'agent */}
            <header className="sticky top-0 z-10 bg-primaire text-white px-5 pt-5 pb-4">
                <p className="text-xs font-semibold uppercase tracking-widest text-white/70">Smart-Brancard</p>
                <div className="flex items-center justify-between gap-3 mt-1">
                    <h1 className="text-2xl font-bold">{titre}</h1>
                    {statut && (
                        <span className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/15 text-sm font-medium">
                            <span className={`w-2.5 h-2.5 rounded-full ${statut.point}`} />
                            {statut.libelle}
                        </span>
                    )}
                </div>
            </header>

            {/* pb-28 : laisse la place à la barre de navigation fixée en bas */}
            <main className="flex-1 px-4 py-5 pb-28">
                {erreur && (
                    <p className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur}</p>
                )}
                {!moi && profil.chargement && <p className="text-center text-slate-500 py-10">Chargement…</p>}

                {/* Tant que l'agent n'a pas touché l'écran, le navigateur bloque la sonnerie et la voix */}
                <ActiverSon />
                {/* Réseau coupé : la mission reste affichée, les actions attendent le retour du réseau */}
                <BandeauHorsLigne />

                {/* Position détectée par le badge (simulateur de badges dans le prototype) : l'agent ne la saisit plus */}
                {moi && onglet === "mission" && <MaPosition />}

                {/* Étape « Terminé » du parcours : au-dessus de l'écran suivant (attente ou nouvelle mission) */}
                {missionTerminee && onglet === "mission" && (
                    <MissionTerminee mission={missionTerminee} onFermer={() => setMissionTerminee(null)} />
                )}

                {moi && onglet === "mission" && (
                    <EcranMission moi={moi} mission={mission.donnees} changerStatut={changerStatut} envoi={envoi}
                        rechargerProfil={profil.recharger}
                        onAccepter={() => repondre(() => accepterMission(mission.donnees.id))}
                        onRefuser={(motif) => repondre(() => refuserMission(mission.donnees.id, motif))}
                        onScanDepart={prendreEnCharge}
                        onScanArrivee={terminerParScan}
                        onArrivee={terminerParDeclaration}
                        onAppel={appeler} />
                )}

                {moi && onglet === "journal" && <EcranJournal />}
                {moi && onglet === "profil" && <EcranProfil moi={moi} />}
            </main>

            {/* Barre de navigation du bas : grandes zones faciles à toucher avec le pouce.
                Même largeur que la colonne de l'application, comme l'en-tête :
                sur un écran plus large (ordinateur de démonstration), elle ne déborde pas. */}
            <nav className="fixed bottom-0 inset-x-0 max-w-md mx-auto bg-white border-t border-slate-200"
                style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
                <div className="grid grid-cols-3">
                    {ONGLETS.map((o) => (
                        <button key={o.id} type="button" onClick={() => setOnglet(o.id)}
                            aria-current={onglet === o.id ? "page" : undefined}
                            className={`flex flex-col items-center gap-1 py-3 text-xs font-semibold cursor-pointer ${
                                onglet === o.id ? "text-primaire" : "text-slate-400"}`}>
                            <o.icone className="w-6 h-6" />
                            {o.libelle}
                        </button>
                    ))}
                </div>
            </nav>
        </div>
    );
}

export default Brancardier;
