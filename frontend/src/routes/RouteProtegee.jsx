import { Navigate } from "react-router-dom";
import { estAuthentifie, getRole } from "../services/authService";

// Protège une page : il faut être connecté ET avoir le rôle attendu.
// Un utilisateur connecté avec un autre rôle est renvoyé vers sa propre page.
function RouteProtegee({ children, role }) {
    if (!estAuthentifie()) {
        return <Navigate to="/login" replace />;
    }
    if (role && getRole() !== role) {
        return <Navigate to={`/${getRole()}`} replace />;
    }
    return children;
}

export default RouteProtegee;
