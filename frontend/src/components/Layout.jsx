import { NavLink, useNavigate } from "react-router-dom";
import { Activity, RadioTower, Server, Users, Network, LogOut, AlertTriangle } from "lucide-react";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/", label: "Resumen", icon: Activity, end: true },
  { to: "/topologia", label: "Topología", icon: Network },
  { to: "/gnb", label: "gNB", icon: RadioTower },
  { to: "/nucleo", label: "Núcleo", icon: Server },
  { to: "/suscriptores", label: "Suscriptores", icon: Users },
];

export default function Layout({ children }) {
  const { authEnabled, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="min-h-screen flex bg-base-950 text-base-100">
      <aside className="w-60 shrink-0 border-r border-base-700 flex flex-col grid-backdrop">
        <div className="px-5 py-6 border-b border-base-700">
          <p className="font-display text-lg font-semibold tracking-tight text-base-100">
            Panel 5G
          </p>
          <p className="font-mono text-[11px] text-base-400 mt-1">
            srsRAN · Open5GS · PLMN 001/01
          </p>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-base-800 text-signal-cyan"
                    : "text-base-300 hover:text-base-100 hover:bg-base-800/60"
                }`
              }
            >
              <Icon size={17} strokeWidth={2} />
              {label}
            </NavLink>
          ))}
        </nav>

        {!authEnabled && (
          <div className="mx-3 mb-3 flex items-start gap-2 rounded-md border border-signal-amber/40 bg-signal-amber/10 px-3 py-2.5 text-[11px] text-signal-amber">
            <AlertTriangle size={14} className="mt-[1px] shrink-0" />
            <span>Autenticación desactivada en este backend. No usar fuera de un laboratorio aislado.</span>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="mx-3 mb-4 flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium text-base-400 hover:text-signal-coral hover:bg-base-800/60 transition-colors"
        >
          <LogOut size={17} strokeWidth={2} />
          Cerrar sesión
        </button>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-6xl mx-auto px-8 py-8">{children}</div>
      </main>
    </div>
  );
}
