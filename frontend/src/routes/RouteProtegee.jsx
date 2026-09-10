import {Navigate} from "react-router-dom";

function RouteProtegee({children, estConnecte}){
    if(!estConnecte){
        return <Navigate to="/login" />;
    }
    return children;
}

export default RouteProtegee;