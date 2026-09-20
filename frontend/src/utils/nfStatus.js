/**
 * Traduce el par (monitored, reachable) que devuelve el backend al estado
 * visual usado por SignalPulse en todas las vistas que muestran NFs.
 */
export function nfStatus(nf) {
  if (!nf.monitored) return "unmonitored";
  return nf.reachable ? "online" : "offline";
}
