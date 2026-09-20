import { Smartphone, RadioTower, Cloud } from "lucide-react";
import { PageHeader, Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";
import { monitoring } from "../api/endpoints";
import { nfStatus } from "../utils/nfStatus";

// Colores por estado, coherentes con SignalPulse -- ver index.css / tokens
const STATUS_COLOR = {
  online: "var(--color-signal-cyan)",
  offline: "var(--color-signal-coral)",
  unmonitored: "var(--color-base-500)",
};

// Posiciones de las 9 funciones de plano de control dentro del clúster SBI
// (el UPF, plano de usuario, se dibuja aparte -- no comparte interfaz SBI,
// ver Implementación y Desarrollo, "El UPF no se registra contra el NRF").
// El SMF se coloca deliberadamente en la esquina inferior izquierda del
// clúster (no en su posición "natural" alfabética/por tipo), por ser la
// más cercana al UPF en el propio diagrama -- así el enlace N4 (PFCP,
// línea discontinua) queda corto y directo, sin cruzar el resto del
// clúster de forma confusa.
const CLUSTER_NF_POSITIONS = {
  amf: { x: 60, y: 30 },
  udr: { x: 220, y: 30 },
  pcf: { x: 380, y: 30 },
  nrf: { x: 60, y: 110 },
  ausf: { x: 220, y: 110 },
  udm: { x: 380, y: 110 },
  smf: { x: 60, y: 190 },
  nssf: { x: 220, y: 190 },
  bsf: { x: 380, y: 190 },
};

const NODE_W = 130;
const NODE_H = 56;

function ClusterNode({ nf, x, y }) {
  const color = STATUS_COLOR[nfStatus(nf)];
  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect
        width={NODE_W}
        height={NODE_H}
        rx={6}
        fill="var(--color-base-900)"
        stroke={color}
        strokeWidth={1.5}
      />
      <circle cx={16} cy={16} r={4} fill={color} />
      <text
        x={NODE_W / 2}
        y={NODE_H / 2 + 5}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={13}
        fill="var(--color-base-100)"
        style={{ textTransform: "uppercase" }}
      >
        {nf.name}
      </text>
    </g>
  );
}

function BigNode({ x, y, w = 120, h = 64, label, sublabel, color, icon: Icon }) {
  return (
    <g transform={`translate(${x}, ${y})`}>
      <rect
        width={w}
        height={h}
        rx={8}
        fill="var(--color-base-900)"
        stroke={color}
        strokeWidth={2}
      />
      <foreignObject x={10} y={h / 2 - 11} width={22} height={22}>
        <Icon size={20} color={color} strokeWidth={2} />
      </foreignObject>
      <text
        x={w / 2 + 10}
        y={h / 2 - (sublabel ? 2 : -5)}
        textAnchor="middle"
        fontFamily="var(--font-display)"
        fontSize={14}
        fontWeight={600}
        fill="var(--color-base-100)"
      >
        {label}
      </text>
      {sublabel && (
        <text
          x={w / 2 + 10}
          y={h / 2 + 15}
          textAnchor="middle"
          fontFamily="var(--font-mono)"
          fontSize={10}
          fill="var(--color-base-400)"
        >
          {sublabel}
        </text>
      )}
    </g>
  );
}

function Link({ x1, y1, x2, y2, label, color, dashed = false }) {
  const midX = (x1 + x2) / 2;
  const midY = (y1 + y2) / 2;
  return (
    <g>
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={color}
        strokeWidth={2}
        strokeDasharray={dashed ? "5 4" : undefined}
      />
      <rect x={midX - 15} y={midY - 9} width={30} height={16} fill="var(--color-base-950)" />
      <text
        x={midX}
        y={midY + 3}
        textAnchor="middle"
        fontFamily="var(--font-mono)"
        fontSize={11}
        fill={color}
      >
        {label}
      </text>
    </g>
  );
}

export default function Topology() {
  const core = usePolling(() => monitoring.coreStatus().then((r) => r.data), 5000);
  const gnbStatusPoll = usePolling(() => monitoring.gnbStatus().then((r) => r.data), 5000);
  const ues = usePolling(() => monitoring.ueStatus().then((r) => r.data), 5000);

  const functions = core.data?.functions ?? [];
  const clusterNfs = functions.filter((nf) => nf.name !== "upf");
  const upfNf = functions.find((nf) => nf.name === "upf");

  const gnbConnected = (gnbStatusPoll.data?.gnb_count ?? 0) > 0;
  const gnbColor = gnbConnected ? STATUS_COLOR.online : STATUS_COLOR.offline;
  const ueCount = ues.data?.count ?? 0;
  const ueColor = ueCount > 0 ? STATUS_COLOR.online : "var(--color-base-500)";
  const upfColor = upfNf ? STATUS_COLOR[nfStatus(upfNf)] : STATUS_COLOR.unmonitored;

  const UE_POS = { x: 20, y: 250 };
  const GNB_POS = { x: 220, y: 250 };
  const AMF_ANCHOR = { x: 470, y: 88 };
  const UPF_POS = { x: 470, y: 470 };
  // Grupo del clúster SBI trasladado a (380, 40) -- ver <g transform> más
  // abajo. El SMF vive en la esquina inferior izquierda del propio clúster
  // (CLUSTER_NF_POSITIONS.smf), calculado aquí en coordenadas absolutas
  // para que el enlace N4 salga exactamente del borde del nodo, no de un
  // punto aproximado a ojo.
  const CLUSTER_ORIGIN = { x: 380, y: 40 };
  const SMF_ANCHOR = {
    x: CLUSTER_ORIGIN.x + CLUSTER_NF_POSITIONS.smf.x + NODE_W / 2,
    y: CLUSTER_ORIGIN.y + CLUSTER_NF_POSITIONS.smf.y + NODE_H,
  };
  const CLOUD_POS = { x: 660, y: 460 };

  return (
    <div>
      <PageHeader
        eyebrow="Topología"
        title="Diagrama de red en vivo"
      />

      <Card className="p-6 overflow-x-auto">
        <svg viewBox="0 0 820 560" className="w-full min-w-[760px]" style={{ height: 560 }}>
          <Link
            x1={UE_POS.x + 40}
            y1={UE_POS.y + 20}
            x2={GNB_POS.x}
            y2={GNB_POS.y + 20}
            label="Uu"
            color={ueColor}
          />
          <Link
            x1={GNB_POS.x + 120}
            y1={GNB_POS.y + 10}
            x2={AMF_ANCHOR.x}
            y2={AMF_ANCHOR.y + 20}
            label="N2"
            color={gnbColor}
          />
          <Link
            x1={GNB_POS.x + 120}
            y1={GNB_POS.y + 35}
            x2={UPF_POS.x}
            y2={UPF_POS.y + 20}
            label="N3"
            color={upfColor}
          />
          <Link
            x1={SMF_ANCHOR.x}
            y1={SMF_ANCHOR.y}
            x2={UPF_POS.x + 60}
            y2={UPF_POS.y}
            label="N4"
            color={upfColor}
            dashed
          />
          <Link
            x1={UPF_POS.x + 120}
            y1={UPF_POS.y + 32}
            x2={CLOUD_POS.x}
            y2={CLOUD_POS.y + 32}
            label="N6"
            color={upfColor}
          />

          <g transform={`translate(${CLUSTER_ORIGIN.x}, ${CLUSTER_ORIGIN.y})`}>
            <rect
              width={440}
              height={266}
              rx={12}
              fill="none"
              stroke="var(--color-base-700)"
              strokeDasharray="3 4"
            />
            <text x={12} y={-8} fontFamily="var(--font-mono)" fontSize={10} fill="var(--color-base-500)">
              NÚCLEO — INTERFAZ SBI
            </text>
            {clusterNfs.map((nf) => {
              const pos = CLUSTER_NF_POSITIONS[nf.name];
              if (!pos) return null;
              return <ClusterNode key={nf.name} nf={nf} x={pos.x} y={pos.y} />;
            })}
          </g>

          <foreignObject x={UE_POS.x} y={UE_POS.y} width={80} height={40}>
            <div className="flex items-center gap-2">
              <Smartphone size={22} color={ueColor} strokeWidth={2} />
              <span className="font-mono text-xs" style={{ color: ueColor }}>
                {ueCount} UE{ueCount === 1 ? "" : "s"}
              </span>
            </div>
          </foreignObject>

          <BigNode x={GNB_POS.x} y={GNB_POS.y} label="gNB" sublabel="n78 · srsRAN" color={gnbColor} icon={RadioTower} />

          <BigNode x={UPF_POS.x} y={UPF_POS.y} label="UPF" sublabel="plano de usuario" color={upfColor} icon={RadioTower} />

          <foreignObject x={CLOUD_POS.x} y={CLOUD_POS.y} width={150} height={64}>
            <div className="flex items-center gap-2.5">
              <Cloud size={34} color={upfColor} strokeWidth={1.75} />
              <span className="font-mono text-sm font-medium text-base-200">
                Red de datos
              </span>
            </div>
          </foreignObject>
        </svg>
      </Card>

      <p className="text-xs text-base-500 mt-4">
        El UPF no se registra contra el NRF (no implementa interfaz SBI, ver Implementación y
        Desarrollo) — su color se determina por su propio{" "}
        <code className="font-mono">/metrics</code>, no por el clúster de la derecha.
      </p>
    </div>
  );
}
