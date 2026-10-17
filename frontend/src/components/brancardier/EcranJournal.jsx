import { FileText } from "lucide-react";

// Onglet « Journal » : missions réalisées par l'agent dans la journée.
// À brancher sur la route qui listera les missions du brancardier (backend, Sprint 3) :
// aujourd'hui GET /missions est réservé au régulateur et au prescripteur.
function EcranJournal() {
    return (
        <div className="flex flex-col items-center text-center gap-4 pt-10">
            <span className="w-20 h-20 rounded-full bg-slate-100 flex items-center justify-center">
                <FileText className="w-10 h-10 text-slate-400" />
            </span>
            <div>
                <p className="text-lg font-bold text-slate-900">Aucune mission aujourd'hui</p>
                <p className="text-slate-500 mt-1">Les missions que vous réalisez apparaîtront ici.</p>
            </div>
        </div>
    );
}

export default EcranJournal;
