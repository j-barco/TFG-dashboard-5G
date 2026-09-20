import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { RadioTower } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const { login, isAuthenticated, checkingAuth, authEnabled } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    // Si AUTH_ENABLED=false, AuthContext ya obtiene una sesión en
    // silencio al arrancar -- si alguien llega aquí manualmente en ese
    // caso, se le saca del login sin que tenga que rellenar nada.
    if (!checkingAuth && isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [checkingAuth, isAuthenticated, navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/", { replace: true });
    } catch (err) {
      if (err.response?.status === 401) {
        setError("Usuario o contraseña incorrectos.");
      } else {
        setError("No se pudo contactar con el backend. Comprueba que esté arrancado.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (checkingAuth) {
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-base-950 grid-backdrop px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <RadioTower size={22} className="text-signal-cyan" strokeWidth={2} />
          <span className="font-display text-xl font-semibold text-base-100 tracking-tight">
            Panel 5G
          </span>
        </div>

        <form
          onSubmit={handleSubmit}
          className="bg-base-800 border border-base-700 rounded-lg px-6 py-7"
        >
          <h1 className="font-display text-base font-medium text-base-100 mb-1">
            Iniciar sesión
          </h1>
          <p className="text-sm text-base-400 mb-6">
            Acceso al panel de estado y gestión del núcleo.
          </p>

          <label className="block text-xs font-medium text-base-300 mb-1.5" htmlFor="username">
            Usuario
          </label>
          <input
            id="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            className="w-full mb-4 rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus-visible:border-signal-cyan"
          />

          <label className="block text-xs font-medium text-base-300 mb-1.5" htmlFor="password">
            Contraseña
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="w-full mb-5 rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus-visible:border-signal-cyan"
          />

          {error && (
            <p className="mb-4 text-sm text-signal-coral" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-md bg-signal-cyan text-base-950 font-medium text-sm py-2.5 hover:brightness-110 transition disabled:opacity-50"
          >
            {submitting ? "Comprobando..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
