import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Loader2, Send, Shield } from "lucide-react";
import EnTete from "../components/EnTete";
import RecherchePatient from "../components/RecherchePatient";
import { useDonnees } from "../hooks/useDonnees";
import { creerMission, listerNoeuds } from "../services/missionService";
import { MATERIELS, URGENCES } from "../services/referentiel";

const FORMULAIRE_VIDE = {
    patient: null,
    niveau_urgence: "BASSE",
    noeud_source_id: "", noeud_destination_id: "",
    materiel_requis: "RIEN", materiel_deja_dispo: false,
    consigne: "",
};

const libelleClasse = "block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2";
const champClasse = "w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 focus:outline-none focus:border-primaire focus:bg-white focus:ring-2 focus:ring-primaire-clair";

// Seules les salles de soins sont proposées (pas les couloirs ni les ascenseurs)
const listerServices = () => listerNoeuds("SERVICE");

// Formulaire de demande de transport (maquette "Demande de transport patient").
// L'assistant vocal de la maquette arrive au Sprint 4.
function Medecin() {
    const navigate = useNavigate();
    const noeuds = useDonnees(listerServices);
    const [form, setForm] = useState(FORMULAIRE_VIDE);
    const [erreur, setErreur] = useState("");
    const [envoi, setEnvoi] = useState(false);

    const services = noeuds.donnees ?? [];
    const etages = [...new Set(services.map((s) => s.etage))].sort();
    const urgence = URGENCES[form.niveau_urgence];

    function modifier(champ) {
        return (e) => {
            const valeur = e.target.type === "checkbox" ? e.target.checked : e.target.value;
            setForm((f) => ({
                ...f,
                [champ]: valeur,
                // Sans matériel, la case "déjà disponible" n'a pas de sens
                ...(champ === "materiel_requis" && valeur === "RIEN" && { materiel_deja_dispo: false }),
            }));
        };
    }

    async function handleSubmit(e) {
        e.preventDefault();
        setErreur("");
        if (!form.patient) {
            setErreur("Choisissez le patient à transporter.");
            return;
        }
        if (form.noeud_source_id === form.noeud_destination_id) {
            setErreur("Le service de destination doit être différent du service d'origine.");
            return;
        }
        setEnvoi(true);
        try {
            const mission = await creerMission({
                patient_id: form.patient.id,
                niveau_urgence: form.niveau_urgence,
                noeud_source_id: Number(form.noeud_source_id),
                noeud_destination_id: Number(form.noeud_destination_id),
                materiel_requis: form.materiel_requis,
                materiel_deja_dispo: form.materiel_deja_dispo,
                consigne: form.consigne.trim() || null,
            });
            navigate(`/medecin/suivi/${mission.id}`);
        } catch (err) {
            setErreur(err.message);
            setEnvoi(false);
        }
    }

    function selectService(champ, libelle) {
        return (
            <div>
                <label htmlFor={champ} className={libelleClasse}>{libelle}</label>
                <select id={champ} required value={form[champ]} onChange={modifier(champ)} className={`${champClasse} cursor-pointer`}>
                    <option value="" disabled>{noeuds.chargement ? "Chargement…" : "Choisir un service"}</option>
                    {etages.map((etage) => (
                        <optgroup key={etage} label={etage === 0 ? "Rez-de-chaussée" : `Étage ${etage}`}>
                            {services.filter((s) => s.etage === etage).map((s) => (
                                <option key={s.id} value={s.id}>{s.nom_salle}</option>
                            ))}
                        </optgroup>
                    ))}
                </select>
            </div>
        );
    }

    return (
        <div className="min-h-screen">
            <EnTete />
            <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8">
                <h1 className="text-2xl font-bold text-slate-900">Demande de transport patient</h1>
                <p className="text-slate-500 mt-1">Remplissez le formulaire pour créer un ordre de brancardage.</p>

                <form onSubmit={handleSubmit} className="mt-6 bg-white rounded-2xl border border-slate-200 shadow-sm p-6 sm:p-8 space-y-5">
                    <h2 className="text-lg font-semibold text-slate-900">Données de la mission</h2>

                    {(erreur || noeuds.erreur) && (
                        <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl flex items-center gap-2">
                            <AlertCircle className="w-4 h-4 shrink-0" />
                            <span>{erreur || noeuds.erreur}</span>
                        </div>
                    )}

                    {/* Patient déjà admis : identité logistique uniquement, aucune donnée clinique (CDC §7.2) */}
                    <div>
                        <label htmlFor="patient" className={libelleClasse}>Patient</label>
                        <RecherchePatient patient={form.patient} champClasse={champClasse}
                            onChoisir={(patient) => setForm((f) => ({ ...f, patient }))} />
                    </div>

                    {/* Urgence et délai garanti */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 items-end">
                        <div>
                            <label htmlFor="urgence" className={libelleClasse}>Niveau d'urgence</label>
                            <select id="urgence" value={form.niveau_urgence} onChange={modifier("niveau_urgence")} className={`${champClasse} cursor-pointer`}>
                                {Object.entries(URGENCES).reverse().map(([code, u]) => (
                                    <option key={code} value={code}>
                                        {code === "URGENT" ? "URGENT" : u.libelle} (délai {u.delai} min)
                                    </option>
                                ))}
                            </select>
                        </div>
                        <p className={`px-4 py-3 rounded-xl text-center text-sm font-semibold ${urgence.delaiClasse}`}>
                            Délai garanti : {urgence.delai} min
                        </p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        {selectService("noeud_source_id", "Service d'origine")}
                        {selectService("noeud_destination_id", "Service de destination")}
                    </div>

                    <div>
                        <label htmlFor="materiel" className={libelleClasse}>Matériel requis</label>
                        <select id="materiel" value={form.materiel_requis} onChange={modifier("materiel_requis")} className={`${champClasse} cursor-pointer`}>
                            {Object.entries(MATERIELS).map(([code, m]) => <option key={code} value={code}>{m.libelleFormulaire}</option>)}
                        </select>
                    </div>

                    {form.materiel_requis !== "RIEN" && (
                        <label className="flex items-start gap-3 cursor-pointer">
                            <input type="checkbox" checked={form.materiel_deja_dispo} onChange={modifier("materiel_deja_dispo")}
                                className="mt-1 w-5 h-5 accent-primaire" />
                            <span>
                                <span className="block font-medium text-slate-900">Le matériel est déjà disponible auprès du patient</span>
                                <span className="block text-sm text-slate-500">Si coché, le brancardier n'aura pas besoin de passer par le dépôt — trajet direct.</span>
                            </span>
                        </label>
                    )}

                    <div>
                        <label htmlFor="consigne" className={libelleClasse}>Consigne de sécurité transport</label>
                        <textarea id="consigne" rows={3} maxLength={500} value={form.consigne} onChange={modifier("consigne")}
                            placeholder="Instructions spéciales pour le brancardier…" className={`${champClasse} resize-none`} />
                    </div>

                    <div className="flex gap-3 pt-2">
                        <button type="submit" disabled={envoi}
                            className="flex-1 py-3.5 bg-primaire hover:bg-primaire-fonce disabled:opacity-60 text-white font-semibold rounded-xl flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed">
                            {envoi ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            {envoi ? "Envoi en cours…" : "Soumettre au régulateur"}
                        </button>
                        <button type="button" onClick={() => { setForm(FORMULAIRE_VIDE); setErreur(""); }}
                            className="px-5 py-3.5 bg-white border border-slate-200 rounded-xl font-medium text-slate-700 hover:bg-slate-50 cursor-pointer">
                            Réinitialiser
                        </button>
                    </div>
                </form>

                <p className="mt-6 p-4 bg-primaire-clair/60 border border-slate-200 rounded-xl text-sm text-slate-600 flex items-start gap-3">
                    <Shield className="w-5 h-5 text-primaire shrink-0" />
                    Seules les informations logistiques sont transmises au brancardier. Aucune donnée clinique partagée.
                </p>
            </main>
        </div>
    );
}

export default Medecin;
