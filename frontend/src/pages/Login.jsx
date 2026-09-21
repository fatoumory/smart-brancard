import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Smartphone, FileText, LogIn, AlertCircle, Loader2 } from "lucide-react";
import { loginApi } from "../services/authService";

function Login({ setEstConnecte }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [selectedRole, setSelectedRole] = useState("medecin");
  const [erreur, setErreur] = useState(""); // État pour afficher les erreurs
  const [chargement, setChargement] = useState(false); // État pour désactiver le bouton pendant la requête
  
  const navigate = useNavigate();

  const roles = [
    {
      id: "regulateur",
      title: "Régulateur",
      subtitle: "Tableau de bord superviseur",
      icon: Activity,
    },
    {
      id: "brancardier",
      title: "Brancardier",
      subtitle: "Application mobile terrain",
      icon: Smartphone,
    },
    {
      id: "medecin",
      title: "Médecin / Prescripteur",
      subtitle: "Formulaire de transport",
      icon: FileText,
    },
  ];

  async function handleSubmit(e) {
    e.preventDefault();
    setErreur(""); // Réinitialiser l'erreur

    // 1. Empêcher la soumission si les champs sont vides
    if (!email.trim() || !password.trim()) {
      setErreur("Veuillez saisir votre identifiant et votre mot de passe.");
      return;
    }
    setChargement(true); // Désactiver le bouton pendant la requête

  

    try {
      // Tâche 3.1 & 3.2 : Appel de l'API et stockage automatique du JWT
      await loginApi(email, password);

      setEstConnecte(true);
      navigate(`/${selectedRole}`);
    } catch (err) {
      // Tâche 3.3 : Affichage dynamique de l'erreur renvoyée par le service
      setErreur(err.message);
    } finally {
      setChargement(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col items-center justify-center p-4">
      {/* En-tête / Logo */}
      <div className="flex flex-col items-center mb-6">
        <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center shadow-md mb-4">
          <Activity className="w-10 h-10 text-white" />
        </div>
        <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Smart-Brancard</h1>
        <p className="text-slate-500 text-sm mt-1">Cardio-Connect · Système de brancardage intelligent</p>
      </div>

      {/* Carte du Formulaire */}
      <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Message d'erreur s'il y en a un */}
          {erreur && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
              <span>{erreur}</span>
            </div>
          )}

          {/* Sélection du Profil */}
          <div>
            <label className="block text-sm font-semibold text-slate-800 mb-3">
              Profil de connexion
            </label>
            <div className="grid grid-cols-3 gap-3">
              {roles.map((role) => {
                const Icon = role.icon;
                const isSelected = selectedRole === role.id;
                return (
                  <button
                    key={role.id}
                    type="button"
                    onClick={() => {
                      setSelectedRole(role.id);
                      setErreur(""); // Efface l'erreur si on change de profil
                    }}
                    className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                      isSelected
                        ? "border-blue-600 bg-blue-50/70 text-blue-700 ring-1 ring-blue-600"
                        : "border-slate-200 hover:border-slate-300 text-slate-600 bg-white"
                    }`}
                  >
                    <Icon className={`w-5 h-5 mb-2 ${isSelected ? "text-blue-600" : "text-slate-500"}`} />
                    <span className="text-xs font-bold leading-tight">{role.title}</span>
                    <span className="text-[10px] text-slate-500 mt-1 leading-tight">{role.subtitle}</span>
                  </button>
                );
              })} 
            </div>
          </div>

          {/* Saisie de l'email */}
          <div>
            <label className="block text-sm font-semibold text-slate-800 mb-2">
              Identifiant institutionnel
            </label>
            <input
              type="email"
              placeholder="abdoudiallo@ch-hopital.fr"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 text-sm focus:outline-none focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100 transition-all"
            />
          </div>

          {/* Saisie du mot de passe */}
          <div>
            <label className="block text-sm font-semibold text-slate-800 mb-2">
              Mot de passe
            </label>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 text-sm focus:outline-none focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100 transition-all"
            />
          </div>

          {/* Bouton de Soumission avec état de chargement*/}
          <button
            type="submit"
            disabled={chargement} // Désactive le bouton pendant la requête
            className="w-full py-3.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-semibold rounded-xl flex items-center justify-center gap-2 shadow-sm transition-colors cursor-pointer disabled:cursor-not-allowed"          >
            {chargement ? (   
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Connexion en cours...</span>
              </>
            ) : (
              <>
                <LogIn className="w-4 h-4" />
                <span>Connexion sécurisée</span>
              </>
            )}
          </button>
        </form>

        {/* Pied de page Sécurité */}
        <div className="mt-6 pt-4 border-t border-slate-100 text-center">
          <p className="text-[11px] text-slate-400 font-medium">
            JWT · RBAC · Session 8h · HTTPS chiffré
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;