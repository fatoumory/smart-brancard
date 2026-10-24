import { useState } from "react";
import { FileText, Navigation, User } from "lucide-react";
import EcranMission from "../components/brancardier/EcranMission";
import EcranJournal from "../components/brancardier/EcranJournal";
import EcranProfil from "../components/brancardier/EcranProfil";
import { useDonnees } from "../hooks/useDonnees";
import { MissionTerminee } from "../components/brancardier/MissionEnCours";
import MaPosition from "../components/brancardier/MaPosition";
import { useBaliseSimulee } from "../hooks/useBaliseSimulee";
import { accepterMission, changerMonStatut, getMaMission, getMonProfil, refuserMission, scannerArrivee, scannerDepart } from "../services/brancardierService";
import { listerNoeuds } from "../services/missionService";
import { STATUTS_AGENT } from "../services/referentiel";

// Le profil (statut, missions du jour) est relu toutes les 30 s, en attendant les WebSockets du Sprint 4
const INTERVALLE_MS = 30000;
// La mission est relue plus souvent : une proposition n'attend la réponse que 30 à 60 s
const INTERVALLE_MISSION_MS = 5000;


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
    const profil = useDonnees(getMonProfil, INTERVALLE_MS);
    const moi = profil.donnees;
    const statut = moi && STATUTS_AGENT[moi.statut];
    // Mission proposée, acceptée ou en transit (null si l'agent n'en a pas)
    const mission = useDonnees(getMaMission, INTERVALLE_MISSION_MS);
    // Mission que l'agent vient de terminer (scan d'arrivée réussi) : confirmation affichée jusqu'à fermeture
    const [missionTerminee, setMissionTerminee] = useState(null);
    // Position de l'agent (balise BLE simulée), envoyée toutes les 2 min quel que soit l'onglet
    const balise = useBaliseSimulee();
    // Lieux de l'hôpital pour le sélecteur « Je suis à » : le plan change rarement, chargé une fois
    const lieux = useDonnees(listerNoeuds);

    // Change le statut sur le serveur, puis relit le profil pour afficher le nouvel état.
    // dureePauseMinutes n'est envoyé que pour une pause (15 ou 45 min) : le serveur en déduit l'heure de fin. Renvoie true si le changement a réussi
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

    // Scan de départ réussi : l'agent est au point de départ.
    // Le serveur a enregistré cette position ; la balise simulée la reprend, pour ne pas renvoyer l'ancien lieu.
    async function prendreEnCharge(corps) {
        const enTransit = await scanner(() => scannerDepart(mission.donnees.id, corps));
        balise.setLieu(enTransit.noeud_source_id);
    }

    // Scan d'arrivée réussi : le serveur renvoie la mission TERMINE, gardée pour la confirmation.
    // L'agent est maintenant à la destination : même mise à jour de la balise.
    async function terminerMission(tagNfc) {
        const terminee = await scanner(() => scannerArrivee(mission.donnees.id, tagNfc));
        setMissionTerminee(terminee);
        balise.setLieu(terminee.noeud_destination_id);
    }

    const titre = ONGLETS.find((o) => o.id === onglet).titre;
    const erreur = erreurStatut || profil.erreur || mission.erreur;


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

                {/* Sélecteur « Je suis à » : simulation des balises BLE (prototype) */}
                {moi && onglet === "mission" && <MaPosition balise={balise} lieux={lieux.donnees ?? []} />}

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
                        onScanArrivee={terminerMission} />
                )}

                {moi && onglet === "journal" && <EcranJournal />}
                {moi && onglet === "profil" && <EcranProfil moi={moi} />}
            </main>

            {/* Barre de navigation du bas : grandes zones faciles à toucher avec le pouce */}
            <nav className="fixed bottom-0 inset-x-0 bg-white border-t border-slate-200"
                style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
                <div className="max-w-md mx-auto grid grid-cols-3">
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
