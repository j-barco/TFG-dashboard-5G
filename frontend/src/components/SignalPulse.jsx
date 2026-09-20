const STATUS_STYLES = {
  online: { color: "var(--color-signal-cyan)", label: "En línea", animate: true },
  degraded: { color: "var(--color-signal-amber)", label: "Degradado", animate: true },
  offline: { color: "var(--color-signal-coral)", label: "Sin servicio", animate: false },
  unmonitored: { color: "var(--color-base-500)", label: "No monitorizable", animate: false },
};

/**
 * Indicador de estado con forma de barras de analizador de espectro, en
 * vez del punto de semáforo genérico -- conecta visualmente el panel con
 * la naturaleza radioeléctrica del sistema que monitoriza.
 */
export default function SignalPulse({ status = "unmonitored", size = "md" }) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.unmonitored;
  const heights = size === "sm" ? [6, 10, 8, 12] : [10, 16, 12, 20];
  const width = size === "sm" ? 2 : 3;

  return (
    <span
      className="inline-flex items-end gap-[2px]"
      role="img"
      aria-label={style.label}
      title={style.label}
    >
      {heights.map((h, i) => (
        <span
          key={i}
          className={style.animate ? "signal-bar" : ""}
          style={{
            display: "block",
            width,
            height: h,
            borderRadius: 1,
            background: style.color,
            opacity: style.animate ? 1 : 0.45,
          }}
        />
      ))}
    </span>
  );
}
