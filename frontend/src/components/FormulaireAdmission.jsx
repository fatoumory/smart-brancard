import { useState } from "react";
import { AlertCircle, Loader2, UserPlus, UserRound, X } from "lucide-react";
import { admettrePatient, modifierIdentitePatient } from "../services/missionService";

const SEXES = { INDETERMINE: "Non précisé", FEMININ: "Femme", MASCULIN: "Homme" };

const libelleClasse = "block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5";

// Pré-remplit nom et prénom avec le texte cherché ("dupont jean" -> Dupont / Jean).
// Un IPP (que des chiffres) ne donne pas de nom.
function depuisRecherche(texte) {
    const mots = texte.trim().split(/\s+/).filter(Boolean);
    if (mots.length === 0 || /^\d+$/.test(mots[0])) return { nom: "", prenom: "" };
    const majuscule = (m) => m.charAt(0).toUpperCase() + m.slice(1).toLowerCase();
    return { nom: majuscule(mots[0]), prenom: mots.slice(1).map(majuscule).join(" ") };
}

// Admission d'un patient introuvable, ou identité confirmée d'un patient à l'identité provisoire.
// - patient absent : admission (POST /patients), identité provisoire possible (patient inconscient)
// - patient présent : complète son identité (PATCH /patients/{id}) ; l'IPP et le bracelet restent les mêmes
// Si un patient semblable existe déjà (409), le médecin choisit : c'est lui, ou c'est une autre personne.
// Ce bloc est affiché dans le formulaire de demande : pas de <form> imbriqué, les boutons sont de type "button".
function FormulaireAdmission({ patient, texteRecherche = "", onTermine, onAnnuler, champClasse }) {
    const modification = Boolean(patient);
    const [champs, setChamps] = useState(() => ({
        identite_inconnue: false,
        ...(modification ? { nom: "", prenom: "" } : depuisRecherche(texteRecherche)),
        date_naissance: patient?.date_naissance ?? "",
        sexe: patient?.sexe ?? "INDETERMINE",
    }));
    const [erreur, setErreur] = useState("");
    const [envoi, setEnvoi] = useState(false);
    // Patients semblables renvoyés par le serveur (conflit 409)
    const [similaires, setSimilaires] = useState(null);

    const inconnue = champs.identite_inconnue;

    function modifier(champ) {
        return (e) => {
            const valeur = e.target.type === "checkbox" ? e.target.checked : e.target.value;
            setChamps((c) => ({ ...c, [champ]: valeur }));
            // Une identité modifiée doit être revérifiée
            setSimilaires(null);
        };
    }

    async function envoyer(confirmerNouveau = false) {
        setErreur("");
        if (!inconnue && (!champs.nom.trim() || !champs.prenom.trim())) {
            setErreur(modification
                ? "Saisissez le nom et le prénom du patient."
                : "Saisissez le nom et le prénom, ou cochez « Identité inconnue ».");
            return;
        }
        const identite = {
            nom: champs.nom.trim(),
            prenom: champs.prenom.trim(),
            date_naissance: champs.date_naissance || null,
            sexe: champs.sexe,
            confirmer_nouveau: confirmerNouveau,
        };
        setEnvoi(true);
        try {
            const resultat = modification
                ? await modifierIdentitePatient(patient.id, identite)
                : await admettrePatient(inconnue
                    ? { identite_inconnue: true, date_naissance: identite.date_naissance, sexe: identite.sexe }
                    : identite);
            onTermine(resultat);
        } catch (err) {
            if (err.status === 409 && err.detail?.patients_similaires) {
                setSimilaires(err.detail.patients_similaires);
            } else {
                setErreur(err.message);
            }
            setEnvoi(false);
        }
    }

    return (
        <div className="p-4 sm:p-5 bg-slate-50 border border-slate-200 rounded-xl space-y-4">
            <div className="flex items-center justify-between gap-3">
                <p className="font-semibold text-slate-900 flex items-center gap-2">
                    <UserPlus className="w-5 h-5 text-primaire" />
                    {modification ? "Compléter l'identité du patient" : "Admettre un nouveau patient"}
                </p>
                <button type="button" onClick={onAnnuler} aria-label="Annuler" title="Annuler"
                    className="p-2 text-slate-500 hover:text-slate-900 hover:bg-white rounded-lg cursor-pointer">
                    <X className="w-4 h-4" />
                </button>
            </div>

            {modification && (
                <p className="text-sm text-slate-500">
                    {patient.nom} {patient.prenom} · IPP {patient.id_hospitalisation}. L'IPP et le bracelet ne changent pas.
                </p>
            )}

            {erreur && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{erreur}</span>
                </div>
            )}

            {/* Patient inconscient ou non identifiable : le serveur lui donne une identité provisoire */}
            {!modification && (
                <label className="flex items-start gap-3 cursor-pointer">
                    <input type="checkbox" checked={inconnue} onChange={modifier("identite_inconnue")}
                        className="mt-1 w-5 h-5 accent-primaire" />
                    <span>
                        <span className="block font-medium text-slate-900">Identité inconnue</span>
                        <span className="block text-sm text-slate-500">Patient inconscient ou non identifiable : une identité provisoire lui est donnée, à compléter plus tard.</span>
                    </span>
                </label>
            )}

            {!inconnue && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label htmlFor="admission-nom" className={libelleClasse}>Nom</label>
                        <input id="admission-nom" value={champs.nom} onChange={modifier("nom")} maxLength={100}
                            autoComplete="off" className={champClasse} />
                    </div>
                    <div>
                        <label htmlFor="admission-prenom" className={libelleClasse}>Prénom</label>
                        <input id="admission-prenom" value={champs.prenom} onChange={modifier("prenom")} maxLength={100}
                            autoComplete="off" className={champClasse} />
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                    <label htmlFor="admission-naissance" className={libelleClasse}>Date de naissance (facultatif)</label>
                    <input id="admission-naissance" type="date" value={champs.date_naissance} onChange={modifier("date_naissance")}
                        max={new Date().toISOString().slice(0, 10)} className={champClasse} />
                </div>
                <div>
                    <label htmlFor="admission-sexe" className={libelleClasse}>Sexe</label>
                    <select id="admission-sexe" value={champs.sexe} onChange={modifier("sexe")} className={`${champClasse} cursor-pointer`}>
                        {Object.entries(SEXES).map(([code, libelle]) => <option key={code} value={code}>{libelle}</option>)}
                    </select>
                </div>
            </div>

            {/* Homonyme possible : le médecin choisit le patient existant, ou confirme une autre personne */}
            {similaires ? (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl space-y-3">
                    <p className="text-sm font-semibold text-amber-800">
                        Un patient semblable est déjà connu. S'agit-il de la même personne ?
                    </p>
                    <ul className="space-y-2">
                        {similaires.map((p) => (
                            <li key={p.id} className="flex items-center justify-between gap-3 px-3 py-2.5 bg-white border border-amber-200 rounded-lg">
                                <span className="flex items-center gap-3 min-w-0">
                                    <UserRound className="w-4 h-4 text-slate-500 shrink-0" />
                                    <span className="min-w-0">
                                        <span className="block font-medium text-slate-900">{p.nom} {p.prenom}</span>
                                        <span className="block text-xs font-mono text-slate-500">
                                            IPP : {p.id_hospitalisation}
                                            {p.date_naissance && ` · né(e) le ${new Date(p.date_naissance).toLocaleDateString("fr-FR")}`}
                                        </span>
                                    </span>
                                </span>
                                <button type="button" onClick={() => onTermine(p)}
                                    className="px-3 py-2 bg-primaire hover:bg-primaire-fonce text-white text-sm font-semibold rounded-lg cursor-pointer shrink-0">
                                    C'est ce patient
                                </button>
                            </li>
                        ))}
                    </ul>
                    <button type="button" disabled={envoi} onClick={() => envoyer(true)}
                        className="w-full py-2.5 bg-white border border-amber-300 rounded-lg text-sm font-medium text-amber-800 hover:bg-amber-100 disabled:opacity-60 cursor-pointer">
                        Non, c'est une autre personne : {modification ? "enregistrer" : "l'admettre"}
                    </button>
                </div>
            ) : (
                <div className="flex gap-3">
                    <button type="button" disabled={envoi} onClick={() => envoyer(false)}
                        className="flex-1 py-3 bg-primaire hover:bg-primaire-fonce disabled:opacity-60 text-white font-semibold rounded-xl flex items-center justify-center gap-2 cursor-pointer disabled:cursor-not-allowed">
                        {envoi ? <Loader2 className="w-4 h-4 animate-spin" /> : <UserPlus className="w-4 h-4" />}
                        {modification ? "Enregistrer l'identité" : "Admettre le patient"}
                    </button>
                    <button type="button" onClick={onAnnuler}
                        className="px-5 py-3 bg-white border border-slate-200 rounded-xl font-medium text-slate-700 hover:bg-slate-50 cursor-pointer">
                        Annuler
                    </button>
                </div>
            )}
        </div>
    );
}

export default FormulaireAdmission;
