import { BrowserRouter } from 'react-router-dom';
import { Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Regulateur from './pages/Regulateur';
import Brancardier from './pages/Brancardier';
import Medecin from './pages/Medecin';
import SuiviDemande from './pages/SuiviDemande';
import MesDemandes from './pages/MesDemandes';
import Simulateur from './pages/Simulateur';
import Comptes from './pages/Comptes';
import RouteProtegee from './routes/RouteProtegee';

// L'état de connexion est lu depuis le localStorage (token JWT) :
// il survit au rechargement de la page
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/regulateur" element={<RouteProtegee role="regulateur"><Regulateur /></RouteProtegee>} />
        {/* Simulateur des badges BLE : réservé au régulateur (le serveur refuse les autres rôles) */}
        <Route path="/regulateur/simulateur" element={<RouteProtegee role="regulateur"><Simulateur /></RouteProtegee>} />
        {/* Cartes de connexion des brancardiers, désactivation des comptes */}
        <Route path="/regulateur/comptes" element={<RouteProtegee role="regulateur"><Comptes /></RouteProtegee>} />
        <Route path="/brancardier" element={<RouteProtegee role="brancardier"><Brancardier /></RouteProtegee>} />
        <Route path="/medecin" element={<RouteProtegee role="medecin"><Medecin /></RouteProtegee>} />
        <Route path="/medecin/demandes" element={<RouteProtegee role="medecin"><MesDemandes /></RouteProtegee>} />
        <Route path="/medecin/suivi/:id" element={<RouteProtegee role="medecin"><SuiviDemande /></RouteProtegee>} />
      </Routes>
    </BrowserRouter>
  );
}


export default App
