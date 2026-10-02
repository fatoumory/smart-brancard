import { NavLink, useNavigate } from "react-router-dom";
import { Activity, ChartColumn, LogOut, Mic, User } from "lucide-react";
import { getRole, lireJeton, logoutApi } from "../services/authService";

// Onglet principal de chaque rôle (maquette : "Dashboard" pour le régulateur, "Prescription" pour le médecin)
const NAVIGATION = {
    regulateur: { chemin: "/regulateur", libelle: "Dashboard", icone: ChartColumn },
    medecin: { chemin: "/medecin", libelle: "Prescription", icone: Mic },
};

function EnTete() {
    const navigate = useNavigate();
    const jeton = lireJeton();
    const role = getRole();
    const onglet = NAVIGATION[role];

    function handleDeconnexion() {
        logoutApi();
        navigate("/login", { replace: true });
    }

    return (
        <header className="bg-white border-b border-slate-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-4">
                {/* Logo */}
                <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-primaire rounded-xl flex items-center justify-center shrink-0">
                        <Activity className="w-6 h-6 text-white" />
                    </div>
                    <span className="font-bold text-slate-900 hidden sm:inline">Smart-Brancard</span>
                </div>

                {/* Onglet principal du rôle */}
                {onglet && (
                    <NavLink
                        to={onglet.chemin}
                        end={false}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl bg-primaire-clair text-primaire font-semibold text-sm"
                    >
                        <onglet.icone className="w-4 h-4" />
                        {onglet.libelle}
                    </NavLink>
                )}

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
