import { BrowserRouter } from 'react-router-dom';
import { Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Regulateur from './pages/Regulateur';
import Brancardier from './pages/Brancardier';
import Medecin from './pages/Medecin';
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
        <Route path="/brancardier" element={<RouteProtegee role="brancardier"><Brancardier /></RouteProtegee>} />
        <Route path="/medecin" element={<RouteProtegee role="medecin"><Medecin /></RouteProtegee>} />
      </Routes>
    </BrowserRouter>
  );
}


export default App
