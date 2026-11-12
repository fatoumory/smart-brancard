import { MapPin, Radio } from "lucide-react";
import { useDonnees } from "../../hooks/useDonnees";
import { getMaPosition } from "../../services/brancardierService";
import { formaterHeure } from "../../services/referentiel";

// Au-delà de 10 min sans détection, le serveur ne considère plus la position comme sûre
const POSITION_PERIMEE_MS = 10 * 60 * 1000;

// Position de l'agent, en haut de l'onglet Mission : lue sur le serveur, jamais saisie par l'agent.
// Elle vient du badge capté par les récepteurs des salles (le simulateur de badges dans le prototype)
// ou du dernier scan. Mise à jour en temps réel (sujet « agents »).
function MaPosition() {
    // misAJourA : heure de la dernière lecture, qui sert à juger si la position est périmée
    const { donnees: position, misAJourA } = useDonnees(getMaPosition, 60000, ["agents"]);

    // Jamais détecté : son badge n'a encore été capté dans aucune salle
    if (!position) {
        return (
            <section className="mb-4 bg-white rounded-2xl shadow-sm p-3 flex items-center gap-3">
                <MapPin className="w-6 h-6 shrink-0 text-slate-300" />
                <p className="text-sm text-slate-500">Votre badge n'a pas encore été détecté dans une salle.</p>
            </section>
        );
    }

    const perimee = misAJourA - new Date(position.date_heure).getTime() > POSITION_PERIMEE_MS;
    return (
        <section className="mb-4 bg-white rounded-2xl shadow-sm p-3 flex items-center gap-3">
            {perimee
                ? <MapPin className="w-6 h-6 shrink-0 text-slate-400" />
                : <Radio className="w-6 h-6 shrink-0 text-emerald-600" />}
            <span className="flex-1 min-w-0">
                <span className="block text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {perimee ? "Dernière position connue" : "Détecté par votre badge"}
                </span>
                <span className="block font-semibold text-slate-900 truncate">{position.noeud_nom}</span>
            </span>
            <span className="text-xs text-slate-400 shrink-0">{formaterHeure(position.date_heure)}</span>
        </section>
    );
}

export default MaPosition;
