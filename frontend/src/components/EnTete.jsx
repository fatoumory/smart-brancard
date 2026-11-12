import { Link, useLocation, useNavigate } from "react-router-dom";
import { Activity, ChartColumn, ClipboardList, ClipboardPlus, LogOut, RadioTower, User } from "lucide-react";
import { getRole, lireJeton, logoutApi } from "../services/authService";

// Onglets de chaque rôle (maquette : "Dashboard" pour le régulateur, "Prescription" pour le médecin).
// actif : pages où l'onglet est en surbrillance (le suivi d'une demande appartient à « Mes demandes »)
const NAVIGATION = {
    regulateur: [
        { chemin: "/regulateur", libelle: "Dashboard", icone: ChartColumn, actif: (p) => p === "/regulateur" },
        // Plan de l'hôpital où l'on déplace les agents : remplace les badges BLE dans le prototype
        { chemin: "/regulateur/simulateur", libelle: "Simulateur", icone: RadioTower,
            actif: (p) => p.startsWith("/regulateur/simulateur") },
    ],
    medecin: [
        { chemin: "/medecin", libelle: "Prescription", icone: ClipboardPlus, actif: (p) => p === "/medecin" },
        { chemin: "/medecin/demandes", libelle: "Mes demandes", icone: ClipboardList,
            actif: (p) => p.startsWith("/medecin/demandes") || p.startsWith("/medecin/suivi") },
    ],
};

// largeur : même largeur maximale que le contenu de la page, pour que le logo et l'utilisateur
// restent alignés sur lui (dashboard large du régulateur, colonne étroite du médecin)
function EnTete({ largeur = "max-w-7xl" }) {
    const navigate = useNavigate();
    const jeton = lireJeton();
    const role = getRole();
    const onglets = NAVIGATION[role] ?? [];
    const { pathname } = useLocation();

    function handleDeconnexion() {
        logoutApi();
        navigate("/login", { replace: true });
    }

    return (
        <header className="bg-white border-b border-slate-200">
            <div className={`${largeur} mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4`}>
                {/* Logo */}
                <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-primaire rounded-xl flex items-center justify-center shrink-0">
                        <Activity className="w-6 h-6 text-white" />
                    </div>
                    <span className="font-bold text-slate-900 hidden sm:inline">Smart-Brancard</span>
                </div>

                {/* Onglets du rôle ; sur un petit écran, l'icône seule quand il y en a plusieurs */}
                <nav className="flex items-center gap-1">
                    {onglets.map((o) => {
                        const actif = o.actif(pathname);
                        return (
                            <Link key={o.chemin} to={o.chemin} title={o.libelle} aria-current={actif ? "page" : undefined}
                                className={`flex items-center gap-2 px-3 sm:px-4 py-2 rounded-xl font-semibold text-sm ${
                                    actif ? "bg-primaire-clair text-primaire" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"}`}>
                                <o.icone className="w-4 h-4 shrink-0" />
                                <span className={onglets.length > 1 ? "hidden sm:inline" : ""}>{o.libelle}</span>
                            </Link>
                        );
                    })}
                </nav>

                {/* Utilisateur connecté et déconnexion */}
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-primaire-clair flex items-center justify-center shrink-0">
                        <User className="w-4 h-4 text-primaire" />
                    </div>
                    <div className="leading-tight hidden sm:block">
                        <p className="text-sm font-semibold text-slate-900">
                            {role === "medecin" ? "Dr. " : ""}{jeton?.prenom} {jeton?.nom}
                        </p>
                        <p className="text-xs text-slate-500">{jeton?.role}</p>
                    </div>
                    <button
                        type="button"
                        onClick={handleDeconnexion}
                        title="Se déconnecter"
                        aria-label="Se déconnecter"
                        className="p-2 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-lg cursor-pointer"
                    >
                        <LogOut className="w-5 h-5" />
                    </button>
                </div>
            </div>
        </header>
    );
}

export default EnTete;
