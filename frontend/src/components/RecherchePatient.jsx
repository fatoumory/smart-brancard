import { useEffect, useState } from "react";
import { Loader2, Search, UserRound, X } from "lucide-react";
import { rechercherPatients } from "../services/missionService";

const DELAI_FRAPPE_MS = 300;

// Recherche d'un patient déjà admis (nom, prénom ou IPP), puis sélection.
// Le patient est créé à l'admission (POST /patients) : le médecin ne fait que le choisir.
function RecherchePatient({ patient, onChoisir, champClasse }) {
    const [texte, setTexte] = useState("");
    // Résultats et texte de recherche qui les a produits (pour ignorer les réponses périmées)
    const [resultats, setResultats] = useState({ pour: "", liste: [], erreur: "" });
    const requete = texte.trim();

    // Attend que la saisie se calme avant d'interroger le serveur
    useEffect(() => {
        if (requete.length < 2) return undefined;
        let actif = true;
        const minuteur = setTimeout(() => {
            rechercherPatients(requete).then(
                (liste) => actif && setResultats({ pour: requete, liste, erreur: "" }),
                (e) => actif && setResultats({ pour: requete, liste: [], erreur: e.message }),
            );
        }, DELAI_FRAPPE_MS);
        return () => { actif = false; clearTimeout(minuteur); };
    }, [requete]);

    if (patient) {
        return (
            <div className="flex items-center justify-between gap-3 px-4 py-3 bg-primaire-clair/60 border border-blue-200 rounded-xl">
                <div className="flex items-center gap-3">
                    <UserRound className="w-5 h-5 text-primaire shrink-0" />
                    <div>
                        <p className="font-semibold text-slate-900">{patient.nom} {patient.prenom}</p>
                        <p className="text-xs font-mono text-slate-500">IPP : {patient.id_hospitalisation}</p>
                    </div>
                    <BadgeIdentite patient={patient} />
                </div>
                <button type="button" onClick={() => { onChoisir(null); setTexte(""); }}
                    className="p-2 text-slate-500 hover:text-slate-900 hover:bg-white rounded-lg cursor-pointer"
                    aria-label="Changer de patient" title="Changer de patient">
                    <X className="w-4 h-4" />
                </button>
            </div>
        );
    }

    const aJour = resultats.pour === requete;
    return (
        <div>
            <div className="relative">
                <Search className="w-4 h-4 text-slate-400 absolute left-4 top-1/2 -translate-y-1/2" />
                <input id="patient" value={texte} onChange={(e) => setTexte(e.target.value)} autoComplete="off"
                    placeholder="Nom, prénom ou IPP (ex : Dupont, 00000147)" className={`${champClasse} pl-10`} />
                {requete.length >= 2 && !aJour && (
                    <Loader2 className="w-4 h-4 text-slate-400 animate-spin absolute right-4 top-1/2 -translate-y-1/2" />
                )}
            </div>

            {requete.length >= 2 && aJour && (
                <div className="mt-2 border border-slate-200 rounded-xl overflow-hidden">
                    {resultats.erreur && <p className="px-4 py-3 text-sm text-red-700">{resultats.erreur}</p>}
                    {!resultats.erreur && resultats.liste.length === 0 && (
                        <p className="px-4 py-3 text-sm text-slate-500">
                            Aucun patient trouvé. Le patient doit d'abord être admis à l'accueil.
                        </p>
                    )}
                    <ul className="divide-y divide-slate-100 max-h-64 overflow-y-auto">
                        {resultats.liste.map((p) => (
                            <li key={p.id}>
                                <button type="button" onClick={() => onChoisir(p)}
                                    className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-slate-50 cursor-pointer">
                                    <span>
                                        <span className="block font-medium text-slate-900">{p.nom} {p.prenom}</span>
                                        <span className="block text-xs font-mono text-slate-500">
                                            IPP : {p.id_hospitalisation}
                                            {p.date_naissance && ` · né(e) le ${new Date(p.date_naissance).toLocaleDateString("fr-FR")}`}
                                        </span>
                                    </span>
                                    <BadgeIdentite patient={p} />
                                </button>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
}

// Un patient admis sans identité (ex : inconscient) porte une identité provisoire
function BadgeIdentite({ patient }) {
    if (patient.statut_identite !== "PROVISOIRE") return null;
    return (
        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-amber-50 text-amber-700 border border-amber-200 shrink-0">
            Identité provisoire
        </span>
    );
}

export default RecherchePatient;
