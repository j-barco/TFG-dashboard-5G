import { useState, useEffect } from "react";
import { Play, Square, RotateCw, FileText, X, Power, PlayCircle, Download, Search } from "lucide-react";
import { PageHeader, Card } from "../components/Card";
import SignalPulse from "../components/SignalPulse";
import { usePolling } from "../hooks/usePolling";
import { monitoring, coreServices, coreLifecycle } from "../api/endpoints";
import { nfStatus } from "../utils/nfStatus";
import { triggerBlobDownload } from "../utils/downloadBlob";
import { getErrorMessage } from "../utils/errorMessage";
import { withRetryOnNetworkError } from "../utils/retry";

function LogsPanel({ nf, onClose }) {
  const [logs, setLogs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [searching, setSearching] = useState(false);
  const [downloading, setDownloading] = useState(false);

  async function fetchLogs() {
    setLoading(true);
    setError(null);
    try {
      const response = await coreServices.logs(nf, 100);
      if (response.data.success) {
        setLogs(response.data.logs || "(sin líneas)");
      } else {
        setError(response.data.logs || "No se pudo obtener el log.");
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleSearch(e) {
    e.preventDefault();
    if (!searchTerm.trim()) {
      fetchLogs();
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const response = await coreServices.searchLogs(nf, searchTerm.trim());
      setLogs(response.data.success ? response.data.logs : null);
      if (!response.data.success) setError(response.data.logs);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSearching(false);
    }
  }

  function clearSearch() {
    setSearchTerm("");
    fetchLogs();
  }

  async function handleDownload() {
    setDownloading(true);
    try {
      const response = await coreServices.downloadLogs(nf);
      triggerBlobDownload(response.data, `${nf}.log`);
    } catch (err) {
      setError(err.response?.data?.detail ?? "No se pudo descargar el log completo.");
    } finally {
      setDownloading(false);
    }
  }

  useEffect(() => {
    fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mt-3 rounded-md border border-base-600 bg-base-950">
      <div className="flex items-center justify-between px-3 py-2 border-b border-base-700">
        <span className="text-xs font-mono text-base-400">últimas 100 líneas — {nf}</span>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="text-base-400 hover:text-signal-cyan transition disabled:opacity-40"
            aria-label="Descargar log completo"
            title="Descargar el fichero completo"
          >
            <Download size={13} />
          </button>
          <button
            onClick={fetchLogs}
            className="text-[11px] text-base-400 hover:text-signal-cyan transition"
          >
            Actualizar
          </button>
          <button
            onClick={onClose}
            className="text-base-500 hover:text-signal-coral transition"
            aria-label="Cerrar logs"
          >
            <X size={13} />
          </button>
        </div>
      </div>
      <form onSubmit={handleSearch} className="flex items-center gap-2 px-3 py-2 border-b border-base-700">
        <div className="relative flex-1">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-base-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Buscar en todo el log del contenedor..."
            className="w-full rounded-md border border-base-600 bg-base-900 pl-7 pr-2 py-1.5 text-[11px] text-base-100 outline-none focus-visible:border-signal-cyan"
          />
        </div>
        {searchTerm && (
          <button
            type="button"
            onClick={clearSearch}
            className="text-base-500 hover:text-signal-coral transition"
          >
            <X size={13} />
          </button>
        )}
        <button
          type="submit"
          disabled={searching}
          className="text-[11px] font-medium text-base-300 hover:text-signal-cyan transition disabled:opacity-40"
        >
          Buscar
        </button>
      </form>
      <pre className="px-3 py-2.5 text-[11px] font-mono text-base-300 overflow-x-auto max-h-72 overflow-y-auto whitespace-pre-wrap">
        {loading || searching ? (
          "Cargando..."
        ) : error ? (
          <span className="text-signal-coral">{error}</span>
        ) : (
          logs
        )}
      </pre>
    </div>
  );
}

export default function CoreServices() {
  const core = usePolling(() => monitoring.coreStatus().then((r) => r.data), 5000);
  const [pending, setPending] = useState(null);
  const [feedback, setFeedback] = useState({});
  const [openLogsFor, setOpenLogsFor] = useState(null);
  const [coreActionPending, setCoreActionPending] = useState(false);
  const [coreActionResult, setCoreActionResult] = useState(null);

  async function handleCoreLifecycle(action) {
    setCoreActionPending(true);
    setCoreActionResult(null);
    try {
      // Un fallo a nivel de red (sin respuesta del backend en absoluto,
      // p. ej. una interrupción breve de conexión) se reintenta una vez
      // en silencio antes de mostrar cualquier mensaje -- 'core up'/'core
      // down' son operaciones seguras de repetir (si ya se completaron
      // de verdad en el primer intento, el segundo confirma que no hay
      // nada más que hacer y responde al instante).
      const response = await withRetryOnNetworkError(() =>
        action === "up" ? coreLifecycle.up() : coreLifecycle.down()
      );
      setCoreActionResult(response.data);
      core.refresh();
    } catch (err) {
      setCoreActionResult({
        success: false,
        detail: getErrorMessage(err),
      });
    } finally {
      setCoreActionPending(false);
    }
  }

  async function handleAction(nf, action) {
    setPending(`${nf}-${action}`);
    try {
      const response =
        action === "start"
          ? await coreServices.start(nf)
          : action === "stop"
          ? await coreServices.stop(nf)
          : await coreServices.restart(nf);
      setFeedback((f) => ({ ...f, [nf]: response.data }));
      core.refresh();
    } catch (err) {
      setFeedback((f) => ({
        ...f,
        [nf]: {
          success: false,
          detail: getErrorMessage(err),
        },
      }));
    } finally {
      setPending(null);
    }
  }

  function toggleLogs(nf) {
    setOpenLogsFor((current) => (current === nf ? null : nf));
  }

  const functions = core.data?.functions ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Núcleo"
        title="Funciones de red"
        description="Arranque, parada y reinicio individual de cada función de red"
      />

      <Card className="px-5 py-4 mb-6 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-base-100">Acciones sobre el core al completo</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleCoreLifecycle("up")}
            disabled={coreActionPending}
            className="flex items-center gap-1.5 rounded-md bg-signal-cyan text-base-950 text-xs font-medium px-3.5 py-2 hover:brightness-110 transition disabled:opacity-50"
          >
            <PlayCircle size={13} />
            Levantar core
          </button>
          <button
            onClick={() => handleCoreLifecycle("down")}
            disabled={coreActionPending}
            className="flex items-center gap-1.5 rounded-md border border-base-600 text-xs font-medium text-base-300 px-3.5 py-2 hover:border-signal-coral hover:text-signal-coral transition disabled:opacity-50"
          >
            <Power size={13} />
            Parar core
          </button>
        </div>
      </Card>

      {coreActionResult && (
        <p
          className={`text-xs font-mono mb-4 -mt-2 ${
            coreActionResult.success ? "text-signal-cyan" : "text-signal-coral"
          }`}
        >
          {coreActionResult.detail || (coreActionResult.success ? "Hecho." : "Fallo.")}
        </p>
      )}

      <Card className="divide-y divide-base-700">
        {functions.map((nf) => {
          const busy = pending?.startsWith(nf.name);
          const fb = feedback[nf.name];
          return (
            <div key={nf.name} className="px-5 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <SignalPulse status={nfStatus(nf)} />
                  <span className="font-mono text-sm text-base-100 uppercase">{nf.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleAction(nf.name, "start")}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-md border border-base-600 text-xs font-medium text-base-300 px-3 py-1.5 hover:border-signal-cyan hover:text-signal-cyan transition disabled:opacity-40"
                  >
                    <Play size={12} />
                    Arrancar
                  </button>
                  <button
                    onClick={() => handleAction(nf.name, "restart")}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-md border border-base-600 text-xs font-medium text-base-300 px-3 py-1.5 hover:border-signal-amber hover:text-signal-amber transition disabled:opacity-40"
                  >
                    <RotateCw size={12} />
                    Reiniciar
                  </button>
                  <button
                    onClick={() => handleAction(nf.name, "stop")}
                    disabled={busy}
                    className="flex items-center gap-1.5 rounded-md border border-base-600 text-xs font-medium text-base-300 px-3 py-1.5 hover:border-signal-coral hover:text-signal-coral transition disabled:opacity-40"
                  >
                    <Square size={12} />
                    Parar
                  </button>
                  <button
                    onClick={() => toggleLogs(nf.name)}
                    className={`flex items-center gap-1.5 rounded-md border text-xs font-medium px-3 py-1.5 transition ${
                      openLogsFor === nf.name
                        ? "border-signal-cyan text-signal-cyan"
                        : "border-base-600 text-base-300 hover:border-signal-cyan hover:text-signal-cyan"
                    }`}
                  >
                    <FileText size={12} />
                    Logs
                  </button>
                </div>
              </div>
              {fb && (
                <p
                  className={`mt-2 font-mono text-xs ${
                    fb.success ? "text-signal-cyan" : "text-signal-coral"
                  }`}
                >
                  {fb.detail || (fb.success ? "Hecho." : "Fallo.")}
                </p>
              )}
              {openLogsFor === nf.name && (
                <LogsPanel nf={nf.name} onClose={() => setOpenLogsFor(null)} />
              )}
            </div>
          );
        })}
      </Card>
    </div>
  );
}
