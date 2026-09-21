import { useState } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { Routes, Route, Link, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Regulateur from './pages/Regulateur';
import Brancardier from './pages/Brancardier';
import Medecin from './pages/Medecin';
import RouteProtegee from './routes/RouteProtegee';

function App() {

  const [estConnecte, setEstConnecte] = useState(false);

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login setEstConnecte={setEstConnecte} />} /><Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/regulateur" element={<RouteProtegee estConnecte={estConnecte}><Regulateur /></RouteProtegee>} />
        <Route path="/brancardier" element={<RouteProtegee estConnecte={estConnecte}><Brancardier /></RouteProtegee>} />
        <Route path="/medecin" element={<RouteProtegee estConnecte={estConnecte}><Medecin /></RouteProtegee>} />
      </Routes>
    </BrowserRouter>
  );
}


export default App
