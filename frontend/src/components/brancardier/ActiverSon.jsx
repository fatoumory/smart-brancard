import { useEffect, useState } from "react";
import { Volume2 } from "lucide-react";
import { activerSon, estSonActive, suivreSon } from "../../services/voix";

// Bandeau « Activer le son », en haut de l'application du brancardier.
// Le navigateur refuse de jouer un son avant un premier toucher de l'écran : sans ce toucher,
// la mission arriverait sans sonnerie ni voix. Il disparaît dès que l'agent l'a touché.
function ActiverSon() {
    const [actif, setActif] = useState(estSonActive);
    useEffect(() => suivreSon(setActif), []);

    if (actif) return null;
    return (
        <button type="button" onClick={activerSon}
            className="mb-4 w-full p-4 rounded-2xl bg-amber-400 hover:bg-amber-500 text-slate-900 font-bold flex items-center gap-3 text-left cursor-pointer">
            <Volume2 className="w-8 h-8 shrink-0" />
            <span>
                Activer le son
                <span className="block text-sm font-medium">Touchez ici pour entendre l'annonce des missions.</span>
            </span>
        </button>
    );
}

export default ActiverSon;
