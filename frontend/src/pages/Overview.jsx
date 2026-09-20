import { RadioTower, Users, Server, RefreshCw, Activity as ActivityIcon } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { PageHeader, Card } from "../components/Card";
import SignalPulse from "../components/SignalPulse";
import { usePolling } from "../hooks/usePolling";
import { monitoring } from "../api/endpoints";
import { nfStatus } from "../utils/nfStatus";

function SummaryTile({ icon: Icon, label, value, hint }) {
  return (
    <Card className="px-5 py-4 flex-1">
      <div className="flex items-center gap-2 text-base-400 mb-2">
        <Icon size={15} strokeWidth={2} />
        <span className="text-xs font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="font-display text-3xl font-semibold text-base-100">{value}</p>
      {hint && <p className="text-xs text-base-400 mt-1">{hint}</p>}
    </Card>
  );
}

export default function Overview() {
  const core = usePolling(() => monitoring.coreStatus().then((r) => r.data), 5000);
  const gnb = usePolling(() => monitoring.gnbStatus().then((r) => r.data), 5000);
  const ues = usePolling(() => monitoring.ueStatus().then((r) => r.data), 5000);
  const throughput = usePolling(
    () => monitoring.throughputHistory().then((r) => r.data),
    5000
  );

  const functions = core.data?.functions ?? [];
  const onlineCount = functions.filter((f) => f.monitored && f.reachable).length;
  const monitoredCount = functions.filter((f) => f.monitored).length;

  return (
    <div>
      <PageHeader
        eyebrow="Estado en vivo"
        title="Resumen del sistema"
        description="Actualización automática cada 5 segundos."
        action={
          <button
            onClick={() => {
              core.refresh();
              gnb.refresh();
              ues.refresh();
            }}
            className="flex items-center gap-2 text-xs font-medium text-base-400 hover:text-signal-cyan border border-base-700 rounded-md px-3 py-2 transition-colors"
          >
            <RefreshCw size={13} />
            Actualizar ahora
          </button>
        }
      />

      <div className="flex gap-4 mb-8">
        <SummaryTile
          icon={Server}
          label="Funciones de red"
          value={`${onlineCount}/${monitoredCount}`}
          hint="activas de las monitorizables"
        />
        <SummaryTile
          icon={RadioTower}
          label="gNBs registrados"
          value={gnb.data?.gnb_count ?? "—"}
        />
        <SummaryTile
          icon={Users}
          label="UEs conectados"
          value={ues.data?.count ?? "—"}
        />
      </div>

      <h2 className="font-display text-sm font-semibold text-base-200 mb-3">
        Núcleo Open5GS
      </h2>
      <Card className="mb-8 divide-y divide-base-700">
        {functions.length === 0 && (
          <p className="px-5 py-6 text-sm text-base-400">
            {core.loading ? "Consultando el core..." : "No se pudo contactar con el backend."}
          </p>
        )}
        {functions.map((nf) => (
          <div key={nf.name} className="flex items-center justify-between px-5 py-3.5">
            <div className="flex items-center gap-3">
              <SignalPulse status={nfStatus(nf)} />
              <span className="font-mono text-sm text-base-100 uppercase">{nf.name}</span>
            </div>
            <div className="flex items-center gap-4 text-xs">
              {nf.ues_active !== null && nf.ues_active !== undefined && (
                <span className="text-base-400 font-mono">{nf.ues_active} UEs</span>
              )}
              <span
                className={
                  !nf.monitored
                    ? "text-base-500"
                    : nf.reachable
                    ? "text-signal-cyan"
                    : "text-signal-coral"
                }
              >
                {!nf.monitored
                  ? "No monitorizable"
                  : nf.reachable
                  ? "En línea"
                  : "Sin servicio"}
              </span>
            </div>
          </div>
        ))}
      </Card>

      <h2 className="font-display text-sm font-semibold text-base-200 mb-3">
        Equipos de usuario conectados
      </h2>
      <Card>
        {(!ues.data || ues.data.ues.length === 0) && (
          <p className="px-5 py-6 text-sm text-base-400">
            No hay ningún UE conectado ahora mismo.
          </p>
        )}
        {ues.data && ues.data.ues.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-base-700 text-left text-xs text-base-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">SUPI</th>
                <th className="px-5 py-3 font-medium">Estado</th>
                <th className="px-5 py-3 font-medium">DNN</th>
                <th className="px-5 py-3 font-medium">IP</th>
                <th className="px-5 py-3 font-medium">Sesión</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-base-700">
              {ues.data.ues.map((ue) => (
                <tr key={ue.supi}>
                  <td className="px-5 py-3 font-mono text-base-100">{ue.supi}</td>
                  <td className="px-5 py-3 text-base-300">{ue.ue_activity}</td>
                  <td className="px-5 py-3 font-mono text-base-300">
                    {ue.sessions[0]?.dnn ?? "—"}
                  </td>
                  <td className="px-5 py-3 font-mono text-base-300">
                    {ue.sessions[0]?.ipv4 ?? "—"}
                  </td>
                  <td className="px-5 py-3 text-base-300">
                    {ue.sessions[0]?.pdu_state ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display text-sm font-semibold text-base-200">
          Tráfico de subida del UE
        </h2>
        <span className="flex items-center gap-1.5 text-[11px] text-base-500 font-mono">
          <ActivityIcon size={12} />
          bytes/s, vía NAT del UPF
        </span>
      </div>
      <Card className="px-5 py-4">
        {(() => {
          const samples = throughput.data?.samples ?? [];
          if (samples.length < 2) {
            return (
              <p className="text-sm text-base-400 py-8 text-center">
                {throughput.loading
                  ? "Cargando histórico..."
                  : "Todavía no hay suficientes muestras acumuladas. El histórico se recalcula cada 5 segundos, incluso sin tener este panel abierto."}
              </p>
            );
          }
          const chartData = samples.map((s) => ({
            time: new Date(s.timestamp * 1000).toLocaleTimeString("es-ES"),
            bytesPerSec: Number(s.uplink_bytes_per_sec.toFixed(2)),
          }));
          const allZero = chartData.every((d) => d.bytesPerSec === 0);
          return (
            <>
              <p className="text-xs text-base-500 mb-3">
                Solo se mide la <strong>subida</strong> (tráfico del UE hacia la red
                externa).
              </p>
              {allZero && (
                <p className="text-xs text-signal-amber mb-3">
                  Sin tráfico de subida detectado todavía en esta ventana — la línea
                  permanecerá en 0 hasta que el UE envíe datos reales.
                </p>
              )}
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 4" stroke="var(--color-base-700)" />
                  <XAxis
                    dataKey="time"
                    stroke="var(--color-base-500)"
                    fontSize={11}
                    fontFamily="var(--font-mono)"
                    minTickGap={40}
                  />
                  <YAxis
                    stroke="var(--color-base-500)"
                    fontSize={11}
                    fontFamily="var(--font-mono)"
                    width={50}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--color-base-900)",
                      border: "1px solid var(--color-base-700)",
                      borderRadius: 6,
                      fontSize: 12,
                      fontFamily: "var(--font-mono)",
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="bytesPerSec"
                    name="subida (B/s)"
                    stroke="var(--color-signal-cyan)"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </>
          );
        })()}
      </Card>
    </div>
  );
}
