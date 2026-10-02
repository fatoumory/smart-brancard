import { ChartColumn } from "lucide-react";

// Nombre de missions créées par heure aujourd'hui, de 6h à l'heure actuelle
function ActiviteJour({ missions }) {
    const aujourdhui = new Date().toDateString();
    const parHeure = {};
    for (const m of missions) {
        const date = new Date(m.date_creation);
        if (date.toDateString() === aujourdhui) {
            parHeure[date.getHours()] = (parHeure[date.getHours()] ?? 0) + 1;
        }
    }

    const heures = Object.keys(parHeure).map(Number);
    const fin = Math.max(new Date().getHours(), ...heures);
    const debut = Math.min(6, ...heures);
    const colonnes = Array.from({ length: fin - debut + 1 }, (_, i) => debut + i);
    const maximum = Math.max(1, ...Object.values(parHeure));

    return (
        <section className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="flex items-center gap-2 font-bold text-slate-900 mb-6">
                <ChartColumn className="w-5 h-5 text-primaire" />
                Activité aujourd'hui
            </h2>
            <div className="flex items-end justify-around gap-2 h-32">
                {colonnes.map((h) => (
                    <div key={h} className="flex flex-col items-center gap-2 h-full flex-1">
                        {/* Zone de la barre : sa hauteur est proportionnelle au nombre de missions */}
                        <div className="flex-1 w-full flex items-end justify-center">
                            <div
                                className="w-3.5 rounded-t-full bg-primaire"
                                style={{ height: `${((parHeure[h] ?? 0) / maximum) * 100}%`, minHeight: parHeure[h] ? 6 : 0 }}
                                title={`${parHeure[h] ?? 0} mission(s) à ${h}h`}
                            />
                        </div>
                        <span className="text-xs text-slate-500">{String(h).padStart(2, "0")}h</span>
                    </div>
                ))}
            </div>
        </section>
    );
}

export default ActiviteJour;
