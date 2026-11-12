import { Radio, WifiOff } from "lucide-react";
import { useTempsReelConnecte } from "../hooks/useTempsReel";

// Pastille « Temps réel » : verte quand l'écran reçoit les changements du serveur dès qu'ils arrivent,
// grise quand la connexion est coupée (l'écran se recharge alors seulement toutes les 30 s)
function IndicateurTempsReel() {
    const connecte = useTempsReelConnecte();
    return connecte ? (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-semibold"
            title="Les changements s'affichent dès qu'ils arrivent">
            <Radio className="w-3.5 h-3.5" /> Temps réel
        </span>
    ) : (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-500 text-xs font-semibold"
            title="Connexion temps réel coupée : l'écran se recharge toutes les 30 s">
            <WifiOff className="w-3.5 h-3.5" /> Hors temps réel
        </span>
    );
}

export default IndicateurTempsReel;
