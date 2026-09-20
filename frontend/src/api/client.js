import axios from "axios";

// La URL del backend se configura en tiempo de compilación (ver .env /
// .env.example) -- por defecto asume que corre en la misma máquina.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE_URL,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Si el token expira o es inválido, cualquier petición protegida devuelve
// 401 -- se limpia la sesión local y se fuerza una vuelta al login, en vez
// de dejar la interfaz en un estado inconsistente mostrando errores sueltos.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      localStorage.removeItem("auth_enabled");
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
