// Carte chiffrée du haut du tableau de bord (maquette : "Missions actives", "En attente"...)
const COULEURS = {
    bleu: { chiffre: "text-primaire", fond: "bg-primaire-clair", icone: "text-primaire" },
    orange: { chiffre: "text-orange-600", fond: "bg-orange-50", icone: "text-orange-600" },
    vert: { chiffre: "text-emerald-700", fond: "bg-emerald-50", icone: "text-emerald-700" },
};

function CarteIndicateur({ titre, valeur, detail, icone: Icone, couleur }) {
    const c = COULEURS[couleur];
    return (
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-start justify-between">
                <p className="text-slate-600 font-medium">{titre}</p>
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${c.fond}`}>
                    <Icone className={`w-5 h-5 ${c.icone}`} />
                </div>
            </div>
            <p className={`text-4xl font-bold mt-3 ${c.chiffre}`}>{valeur}</p>
            <p className="text-sm text-slate-500 mt-3">{detail}</p>
        </div>
    );
}

export default CarteIndicateur;
