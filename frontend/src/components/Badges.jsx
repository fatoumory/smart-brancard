import { CircleAlert } from "lucide-react";
import { MATERIELS, STATUTS_MISSION, URGENCES } from "../services/referentiel";

export function BadgeUrgence({ niveau }) {
    const urgence = URGENCES[niveau];
    return (
        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md border text-xs font-bold font-mono ${urgence.badge}`}>
            {niveau === "URGENT" && <CircleAlert className="w-3.5 h-3.5" />}
            {niveau === "URGENT" ? "URGENT" : urgence.libelle}
        </span>
    );
}

export function BadgeStatut({ statut }) {
    const s = STATUTS_MISSION[statut];
    return <span className={`inline-block px-2 py-1 rounded-md text-sm font-medium ${s.classe}`}>{s.libelle}</span>;
}

export function Materiel({ code }) {
    const materiel = MATERIELS[code];
    const Icone = materiel.icone;
    return (
        <span className="inline-flex items-center gap-1.5 text-slate-600 text-sm">
            {Icone && <Icone className="w-4 h-4 shrink-0" />}
            {materiel.libelle}
        </span>
    );
}
