import { Gauge } from "lucide-react";

// Bandeau « Saturation flotte » (CDC §5.4) : trop de missions en attente pour les agents disponibles.
// Calculé par le serveur (GET /missions/saturation) ; la file est déjà servie avec vieillissement :
// une mission peu urgente qui attend depuis longtemps passe devant une plus urgente qui vient d'arriver.
function BandeauSaturation({ etat }) {
    if (!etat?.sature) return null;
    return (
        <section role="alert" className="p-4 rounded-2xl bg-red-600 text-white flex flex-wrap items-center gap-4">
            <Gauge className="w-8 h-8 shrink-0" />
            <div className="flex-1 min-w-60">
                <p className="text-lg font-bold">Saturation flotte</p>
                <p className="text-sm text-white/90">
                    {etat.missions_en_attente} missions en attente pour {etat.agents_disponibles} agent{etat.agents_disponibles > 1 ? "s" : ""} disponible{etat.agents_disponibles > 1 ? "s" : ""}
                    {etat.missions_en_retard > 0 && `, dont ${etat.missions_en_retard} au-delà du délai garanti`}.
                    {" "}Rappelez des agents en pause ou reportez les transports les moins urgents.
                </p>
            </div>
        </section>
    );
}

export default BandeauSaturation;
