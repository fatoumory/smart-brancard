import { useState } from "react";
import { LogOut, User, Volume2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { logoutApi } from "../../services/authService";
import { STATUTS_AGENT } from "../../services/referentiel";

// Préférence de l'agent, gardée sur son téléphone ; la lecture des consignes l'utilisera (Sprint 4)
const CLE_ASSISTANCE = "assistance_vocale";

// Onglet « Profil » : identité, statut, missions du jour, assistance vocale, déconnexion
function EcranProfil({ moi }) {
    const navigate = useNavigate();
    const [assistance, setAssistance] = useState(() => localStorage.getItem(CLE_ASSISTANCE) === "oui");
    const statut = STATUTS_AGENT[moi.statut];

    function basculerAssistance() {
        const active = !assistance;
        setAssistance(active);
        localStorage.setItem(CLE_ASSISTANCE, active ? "oui" : "non");
        // Confirmation à voix haute avec la synthèse vocale du navigateur
        if (active && "speechSynthesis" in window) {
            const message = new SpeechSynthesisUtterance("Assistance vocale activée. Je vous guiderai à chaque étape de votre mission.");
            message.lang = "fr-FR";
            window.speechSynthesis.cancel();
            window.speechSynthesis.speak(message);
        }
    }

    function deconnecter() {
        logoutApi();
        navigate("/login", { replace: true });
    }

    return (
        <div className="space-y-4">
            <section className="bg-white rounded-3xl shadow-sm p-5 flex items-center gap-4">
                <span className="w-16 h-16 rounded-2xl bg-primaire-clair flex items-center justify-center shrink-0">
                    <User className="w-8 h-8 text-primaire" />
                </span>
                <div>
                    <p className="text-xl font-bold text-slate-900">{moi.prenom} {moi.nom}</p>
                    <p className="text-slate-500">Brancardier</p>
                    <p className={`flex items-center gap-2 font-semibold mt-1 ${statut.texte}`}>
                        <span className={`w-2.5 h-2.5 rounded-full ${statut.point}`} />
                        {statut.libelle}
                    </p>
                </div>
            </section>

            <section className="bg-white rounded-3xl shadow-sm overflow-hidden">
                <div className="p-5 flex items-center gap-4">
                    <span className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center shrink-0">
                        <Volume2 className="w-6 h-6 text-slate-500" />
                    </span>
                    <div className="flex-1">
                        <p className="font-bold text-slate-900">Assistance vocale</p>
                        <p className="text-sm text-slate-500">Instructions dictées à chaque étape</p>
                    </div>
                    {/* Interrupteur (role="switch" : annoncé comme tel par les lecteurs d'écran) */}
                    <button type="button" role="switch" aria-checked={assistance} onClick={basculerAssistance}
                        aria-label="Assistance vocale"
                        className={`w-14 h-8 rounded-full p-1 transition-colors cursor-pointer ${assistance ? "bg-primaire" : "bg-slate-300"}`}>
                        <span className={`block w-6 h-6 rounded-full bg-white shadow transition-transform ${assistance ? "translate-x-6" : ""}`} />
                    </button>
                </div>
                <p className="px-5 pb-5 text-sm text-slate-500">
                    Activez cette option si vous êtes peu à l'aise avec la lecture. Les consignes seront lues
                    à voix haute dès la réception d'une mission.
                </p>
            </section>

            <section className="bg-white rounded-3xl shadow-sm divide-y divide-slate-100">
                <Ligne libelle="Missions réalisées" valeur={`${moi.compteur_mission ?? 0} aujourd'hui`} />
                <Ligne libelle="Identifiant" valeur={moi.nom_utilisateur} />
                <Ligne libelle="Session" valeur="8 h (durée d'une garde)" />
            </section>

            <button type="button" onClick={deconnecter}
                className="w-full h-14 rounded-2xl bg-white border border-red-200 text-red-700 font-bold flex items-center justify-center gap-2 cursor-pointer hover:bg-red-50">
                <LogOut className="w-5 h-5" /> Se déconnecter
            </button>
        </div>
    );
}

function Ligne({ libelle, valeur }) {
    return (
        <div className="flex items-center justify-between gap-4 px-5 py-4">
            <span className="text-slate-500">{libelle}</span>
            <span className="font-semibold text-slate-900 text-right">{valeur}</span>
        </div>
    );
}

export default EcranProfil;
