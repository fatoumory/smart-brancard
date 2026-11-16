import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { BadgeCheck, CreditCard, Printer, Search, UserRoundCheck, UserRoundX, Users, X } from "lucide-react";
import EnTete from "../components/EnTete";
import { useDonnees } from "../hooks/useDonnees";
import { lireJeton } from "../services/authService";
import { changerActivation, genererCarte, listerUtilisateurs } from "../services/missionService";

const ROLES = { BRANCARDIER: "Brancardier", MEDECIN: "Médecin", REGULATEUR: "Régulateur", ADMIN: "Administrateur" };
const ORDRE_ROLES = ["BRANCARDIER", "MEDECIN", "REGULATEUR", "ADMIN"];

// Texte comparable pour la recherche : minuscules, sans accents (« Séne » est trouvé en tapant « sene »)
function normaliser(texte) {
    return (texte ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

// Le compte correspond-il à la recherche ? Chaque mot tapé doit se trouver dans le prénom ou le nom
// (« awa diallo », « diallo awa » et « dial » trouvent tous Awa Diallo)
function correspond(utilisateur, recherche) {
    const mots = normaliser(recherche).split(/\s+/).filter(Boolean);
    const identite = normaliser(`${utilisateur.prenom} ${utilisateur.nom}`);
    return mots.every((mot) => identite.includes(mot));
}

// Comptes du personnel (régulateur) :
//   - carte de connexion des brancardiers : un QR code à imprimer et à coller au dos du badge ;
//     en générer une nouvelle rend l'ancienne inutilisable (carte perdue) ;
//   - désactivation d'un compte (départ, absence longue) : il n'est jamais supprimé, car les missions
//     et le journal d'audit gardent la trace de ce qu'il a fait. Il peut être réactivé.
function Comptes() {
    const utilisateurs = useDonnees(listerUtilisateurs, 60000, ["agents"]);
    // Carte qui vient d'être générée : { prenom, nom, code } ; affichée une seule fois
    const [carte, setCarte] = useState(null);
    // Compte dont la désactivation attend confirmation
    const [aConfirmer, setAConfirmer] = useState(null);
    const [envoi, setEnvoi] = useState(false);
    const [erreur, setErreur] = useState("");
    // Le régulateur ne peut pas désactiver son propre compte (le serveur le refuse aussi)
    const moi = Number(lireJeton()?.sub);
    // Recherche par nom ou prénom, faite dans le navigateur (la liste du personnel est déjà chargée)
    const [recherche, setRecherche] = useState("");

    const tous = [...(utilisateurs.donnees ?? [])].sort((a, b) =>
        ORDRE_ROLES.indexOf(a.role) - ORDRE_ROLES.indexOf(b.role) || a.nom.localeCompare(b.nom));
    const liste = tous.filter((u) => correspond(u, recherche));

    // Appel au serveur, puis relecture de la liste ; le message d'erreur du serveur est affiché
    async function agir(action) {
        setErreur("");
        setEnvoi(true);
        try {
            return await action();
        } catch (err) {
            setErreur(err.message);
            return null;
        } finally {
            setEnvoi(false);
            utilisateurs.recharger();
        }
    }

    async function nouvelleCarte(id) {
        const reponse = await agir(() => genererCarte(id));
        if (reponse) setCarte(reponse);
    }

    async function basculer(u) {
        setAConfirmer(null);
        await agir(() => changerActivation(u.id, !u.est_actif));
    }

    return (
        <div className="min-h-screen">
            <EnTete />
            <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Comptes du personnel</h1>
                    <p className="text-sm text-slate-500 max-w-2xl">
                        Imprimez la carte de connexion d'un brancardier : il la scanne en début de garde et il est connecté pour 8 h.
                        Un compte n'est jamais supprimé : il est désactivé, et ses missions restent dans le journal.
                    </p>
                </div>

                {(erreur || utilisateurs.erreur) && (
                    <p role="alert" className="p-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl">{erreur || utilisateurs.erreur}</p>
                )}

                {carte && <CarteConnexion carte={carte} onFermer={() => setCarte(null)} />}

                <section className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
                    <div className="flex flex-wrap items-center justify-between gap-3 p-5 border-b border-slate-100">
                        <h2 className="flex items-center gap-2 text-xl font-bold text-slate-900">
                            <Users className="w-5 h-5 text-primaire" /> Comptes
                            {/* Nombre de comptes affichés, sur le total, quand une recherche est en cours */}
                            {recherche.trim() && (
                                <span className="text-sm font-medium text-slate-500">{liste.length} sur {tous.length}</span>
                            )}
                        </h2>
                        {/* Barre de recherche : filtre la liste à chaque lettre tapée */}
                        <label className="relative w-full sm:w-80">
                            <span className="sr-only">Rechercher par nom ou prénom</span>
                            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                            <input type="search" value={recherche} onChange={(e) => setRecherche(e.target.value)}
                                placeholder="Rechercher par nom ou prénom…" autoComplete="off"
                                className="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-800 focus:outline-none focus:border-primaire focus:bg-white focus:ring-2 focus:ring-primaire-clair" />
                        </label>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left min-w-[720px]">
                            <thead className="bg-slate-50 border-b border-slate-200">
                                <tr className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    <th className="px-4 py-3">Nom</th>
                                    <th className="px-4 py-3">Rôle</th>
                                    <th className="px-4 py-3">Compte</th>
                                    <th className="px-4 py-3">Carte</th>
                                    <th className="px-4 py-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {/* Aucun compte ne correspond à la recherche */}
                                {liste.length === 0 && tous.length > 0 && (
                                    <tr>
                                        <td colSpan={5} className="px-4 py-10 text-center text-slate-500">
                                            Aucun compte ne correspond à « {recherche.trim()} ».
                                        </td>
                                    </tr>
                                )}
                                {liste.map((u) => (
                                    <tr key={u.id} className={`border-b border-slate-100 ${u.est_actif ? "" : "bg-slate-50 text-slate-400"}`}>
                                        <td className="px-4 py-3">
                                            <p className={`font-medium ${u.est_actif ? "text-slate-900" : ""}`}>{u.prenom} {u.nom}</p>
                                            <p className="text-xs text-slate-500">{u.nom_utilisateur}</p>
                                        </td>
                                        <td className="px-4 py-3 text-sm">{ROLES[u.role] ?? u.role}</td>
                                        <td className="px-4 py-3 text-sm">
                                            {u.est_actif
                                                ? <span className="font-semibold text-emerald-700">Actif</span>
                                                : <span className="font-semibold">Désactivé</span>}
                                        </td>
                                        <td className="px-4 py-3 text-sm">
                                            {u.role !== "BRANCARDIER" ? "—"
                                                : u.a_une_carte ? <span className="flex items-center gap-1 text-emerald-700"><BadgeCheck className="w-4 h-4" /> Imprimée</span>
                                                    : <span className="text-slate-400">Aucune</span>}
                                        </td>
                                        <td className="px-4 py-3">
                                            <div className="flex flex-wrap justify-end gap-2">
                                                {u.role === "BRANCARDIER" && u.est_actif && (
                                                    <button type="button" onClick={() => nouvelleCarte(u.id)} disabled={envoi}
                                                        title={u.a_une_carte ? "L'ancienne carte ne fonctionnera plus" : undefined}
                                                        className="px-3 py-1.5 rounded-lg bg-white border border-slate-200 text-sm font-semibold text-slate-700 flex items-center gap-1.5 hover:bg-slate-100 cursor-pointer disabled:opacity-50">
                                                        <CreditCard className="w-4 h-4 text-primaire" /> {u.a_une_carte ? "Nouvelle carte" : "Carte"}
                                                    </button>
                                                )}
                                                {u.id !== moi && (aConfirmer === u.id ? (
                                                    <>
                                                        <button type="button" onClick={() => setAConfirmer(null)}
                                                            className="px-3 py-1.5 rounded-lg text-sm text-slate-500 cursor-pointer">Retour</button>
                                                        <button type="button" onClick={() => basculer(u)} disabled={envoi}
                                                            className="px-3 py-1.5 rounded-lg bg-red-600 text-white text-sm font-semibold cursor-pointer disabled:opacity-50">
                                                            Confirmer la désactivation
                                                        </button>
                                                    </>
                                                ) : u.est_actif ? (
                                                    // Désactivation en deux temps : la mission proposée ou acceptée de l'agent repart vers un autre
                                                    <button type="button" onClick={() => setAConfirmer(u.id)} disabled={envoi}
                                                        className="px-3 py-1.5 rounded-lg bg-white border border-red-200 text-sm font-semibold text-red-700 flex items-center gap-1.5 hover:bg-red-50 cursor-pointer disabled:opacity-50">
                                                        <UserRoundX className="w-4 h-4" /> Désactiver
                                                    </button>
                                                ) : (
                                                    <button type="button" onClick={() => basculer(u)} disabled={envoi}
                                                        className="px-3 py-1.5 rounded-lg bg-white border border-emerald-200 text-sm font-semibold text-emerald-700 flex items-center gap-1.5 hover:bg-emerald-50 cursor-pointer disabled:opacity-50">
                                                        <UserRoundCheck className="w-4 h-4" /> Réactiver
                                                    </button>
                                                ))}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            </main>
        </div>
    );
}

// Carte de connexion à imprimer : le QR code du code secret, avec le nom de l'agent.
// Le code n'est montré qu'ici, une seule fois : le serveur n'en garde que l'empreinte.
// À l'impression, seule la carte sort (voir .zone-impression dans index.css).
function CarteConnexion({ carte, onFermer }) {
    const [image, setImage] = useState(null);

    // Dessin du QR code dans le navigateur (aucun service extérieur : le code ne quitte pas l'hôpital)
    useEffect(() => {
        let actif = true;
        QRCode.toDataURL(carte.code, { width: 320, margin: 1, errorCorrectionLevel: "M" })
            .then((url) => actif && setImage(url));
        return () => { actif = false; };
    }, [carte.code]);

    return (
        <section className="bg-white rounded-2xl border-2 border-primaire shadow-sm p-5 flex flex-wrap items-start gap-6">
            <div className="zone-impression w-64 p-4 rounded-2xl border border-slate-300 bg-white text-center">
                <p className="text-xs font-semibold uppercase tracking-widest text-primaire">Smart-Brancard</p>
                {image ? <img src={image} alt={`Carte de connexion de ${carte.prenom} ${carte.nom}`} className="w-full my-2" />
                    : <div className="w-full aspect-square my-2 bg-slate-100 rounded-lg" />}
                <p className="font-bold text-slate-900">{carte.prenom} {carte.nom}</p>
                <p className="text-xs text-slate-500">Carte personnelle de connexion · ne pas prêter</p>
            </div>
            <div className="flex-1 min-w-60 space-y-3">
                <p className="font-bold text-slate-900">Carte de {carte.prenom} {carte.nom}</p>
                <p className="text-sm text-slate-500">
                    Imprimez-la maintenant et collez-la au dos du badge de l'agent : elle ne pourra plus être affichée ensuite.
                    En cas de perte, générez une nouvelle carte ; celle-ci ne fonctionnera plus.
                </p>
                <div className="flex flex-wrap gap-2">
                    <button type="button" onClick={() => window.print()}
                        className="px-4 py-2 rounded-lg bg-primaire text-white font-semibold flex items-center gap-2 cursor-pointer">
                        <Printer className="w-4 h-4" /> Imprimer la carte
                    </button>
                    <button type="button" onClick={onFermer}
                        className="px-4 py-2 rounded-lg text-slate-600 font-medium flex items-center gap-2 hover:bg-slate-100 cursor-pointer">
                        <X className="w-4 h-4" /> Fermer
                    </button>
                </div>
            </div>
        </section>
    );
}

export default Comptes;
