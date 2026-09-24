import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { logoutApi } from "../services/authService";

function BoutonDeconnexion() {
    const navigate = useNavigate();

    function handleDeconnexion() {
        logoutApi();
        navigate("/login", { replace: true });
    }

    return (
        <button
            type="button"
            onClick={handleDeconnexion}
            className="flex items-center gap-2 px-3 py-2 text-sm font-semibold text-slate-600 border border-slate-200 rounded-xl hover:bg-slate-50 cursor-pointer"
        >
            <LogOut className="w-4 h-4" />
            <span>Se déconnecter</span>
        </button>
    );
}

export default BoutonDeconnexion;
