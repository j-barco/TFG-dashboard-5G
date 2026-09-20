import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, checkingAuth } = useAuth();

  // Evita un parpadeo hacia /login mientras se resuelve si AUTH_ENABLED
  // está activada o no (ver AuthContext) -- no se sabe todavía si hará
  // falta sesión real o si se autenticará en silencio.
  if (checkingAuth) {
    return null;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
