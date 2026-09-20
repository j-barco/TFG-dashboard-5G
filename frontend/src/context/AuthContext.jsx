import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { auth as authApi } from "../api/endpoints";
import { isTokenExpired } from "../utils/jwt";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => {
    const stored = localStorage.getItem("access_token");
    // Un token caducado (de una sesión anterior, más de 60 minutos)
    // nunca debe contar como sesión válida, en ninguna pestaña -- si no
    // se comprobara aquí, una pestaña sin endpoints protegidos (como
    // Resumen) nunca lo notaría, mientras que otra que sí los use (como
    // gNB) lo detectaría de golpe al recibir un 401, dando la sensación
    // de un comportamiento inconsistente entre pestañas del mismo panel.
    if (stored && isTokenExpired(stored)) {
      localStorage.removeItem("access_token");
      return null;
    }
    return stored;
  });
  const [authEnabled, setAuthEnabled] = useState(
    () => localStorage.getItem("auth_enabled") !== "false"
  );
  // Mientras no se resuelve la comprobación inicial, no se sabe todavía si
  // hace falta mostrar el login o saltarlo -- evita un parpadeo hacia la
  // pantalla de login en el caso AUTH_ENABLED=false.
  const [checkingAuth, setCheckingAuth] = useState(true);

  const login = useCallback(async (username, password) => {
    const response = await authApi.login(username, password);
    const { access_token, auth_enabled } = response.data;
    localStorage.setItem("access_token", access_token);
    localStorage.setItem("auth_enabled", String(auth_enabled));
    setToken(access_token);
    setAuthEnabled(auth_enabled);
    return response.data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("auth_enabled");
    setToken(null);
  }, []);

  useEffect(() => {
    // Al cargar la aplicación, se consulta el estado real de AUTH_ENABLED
    // en el backend (endpoint público, sin token) -- si está desactivada
    // y todavía no hay sesión, se obtiene un token en silencio (el propio
    // backend lo emite sin comprobar credenciales cuando está desactivada,
    // ver /auth/login), evitando mostrar la pantalla de login para algo
    // que en la práctica no protege nada.
    let cancelled = false;

    async function checkAuth() {
      try {
        const { data } = await authApi.status();
        if (cancelled) return;

        setAuthEnabled(data.auth_enabled);
        localStorage.setItem("auth_enabled", String(data.auth_enabled));

        if (!data.auth_enabled && !localStorage.getItem("access_token")) {
          await login("anonimo", "");
        }
      } catch {
        // Si el backend no responde en absoluto, se deja el flujo normal
        // de login -- fallará igual al intentar entrar, con un mensaje
        // más claro que el de esta comprobación silenciosa.
      } finally {
        if (!cancelled) setCheckingAuth(false);
      }
    }

    checkAuth();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isAuthenticated = Boolean(token);

  return (
    <AuthContext.Provider
      value={{ token, authEnabled, isAuthenticated, checkingAuth, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
