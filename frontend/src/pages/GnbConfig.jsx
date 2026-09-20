import { useEffect, useState, useCallback } from "react";
import {
  Play,
  RadioTower,
  Power,
  AlertTriangle,
  Cpu,
  ShieldAlert,
  FileText,
  Save,
  Trash2,
  Upload,
  RefreshCw,
  Download,
  Search,
  X,
  FolderCog,
} from "lucide-react";
import { PageHeader, Card } from "../components/Card";
import SignalPulse from "../components/SignalPulse";
import { usePolling } from "../hooks/usePolling";
import { gnb as gnbApi } from "../api/endpoints";
import { triggerBlobDownload } from "../utils/downloadBlob";

const RADIO_KEYS = ["band", "dl_arfcn", "channel_bandwidth_mhz", "common_scs", "srate"];

const CUSTOM_FIELDS = [
  { key: "band", label: "Banda NR", type: "number" },
  { key: "dl_arfcn", label: "ARFCN (DL)", type: "number" },
  { key: "channel_bandwidth_mhz", label: "Ancho de banda", type: "number", suffix: "MHz" },
  { key: "common_scs", label: "Subcarrier spacing", type: "number", suffix: "kHz" },
  { key: "srate", label: "Tasa de muestreo", type: "number", step: "0.01", suffix: "MSps" },
];

function matchesPreset(config, preset) {
  return RADIO_KEYS.every((key) => Number(config[key]) === Number(preset[key]));
}

function HardwarePanel() {
  const hw = usePolling(() => gnbApi.getHardware().then((r) => r.data), 5000);
  const [starting, setStarting] = useState(false);
  const [startResult, setStartResult] = useState(null);

  async function handleStart() {
    setStarting(true);
    setStartResult(null);
    try {
      const response = await gnbApi.start();
      setStartResult({ ok: response.data.success, detail: response.data.detail });
      hw.refresh();
    } catch (err) {
      setStartResult({
        ok: false,
        detail: err.response?.data?.detail ?? "Error al contactar con el backend.",
      });
    } finally {
      setStarting(false);
    }
  }

  const running = hw.data?.running ?? false;
  const device = hw.data?.detected_device;

  return (
    <Card className="px-6 py-5 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <SignalPulse status={running ? "online" : "offline"} size="sm" />
          <span className="text-sm font-medium text-base-100">
            {running ? "gNB en marcha" : "gNB detenido"}
          </span>
        </div>
        {!running && (
          <button
            onClick={handleStart}
            disabled={starting}
            className="flex items-center gap-2 rounded-md bg-signal-cyan text-base-950 text-xs font-medium px-3 py-2 hover:brightness-110 transition disabled:opacity-50"
          >
            <Play size={13} />
            {starting ? "Arrancando..." : "Arrancar gNB"}
          </button>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs text-base-400">
        <Cpu size={13} />
        {device ? (
          <span>
            Última tarjeta detectada: <span className="font-mono text-base-200">{device}</span>
          </span>
        ) : (
          <span>Sin dato de hardware todavía (el gNB no ha arrancado en esta máquina).</span>
        )}
      </div>

      {startResult && (
        <p
          className={`mt-3 font-mono text-xs whitespace-pre-line ${
            startResult.ok ? "text-signal-cyan" : "text-signal-coral"
          }`}
        >
          {startResult.detail}
        </p>
      )}
    </Card>
  );
}

function GnbLogsPanel() {
  const [logs, setLogs] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("tail"); // "tail" | "head"
  const [tail, setTail] = useState(100);
  const [searchTerm, setSearchTerm] = useState("");
  const [searching, setSearching] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await gnbApi.getLogs(tail, mode);
      if (response.data.success) {
        setLogs(response.data.logs || "(sin líneas)");
      } else {
        setError(response.data.logs || "No se pudo obtener el log.");
      }
    } catch (err) {
      setError(err.response?.data?.detail ?? "Error al contactar con el backend.");
    } finally {
      setLoading(false);
    }
  }, [tail, mode]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  async function handleSearch(e) {
    e.preventDefault();
    if (!searchTerm.trim()) {
      fetchLogs();
      return;
    }
    setSearching(true);
    setError(null);
    try {
      const response = await gnbApi.searchLogs(searchTerm.trim());
      setLogs(response.data.success ? response.data.logs : null);
      if (!response.data.success) setError(response.data.logs);
    } catch (err) {
      setError(err.response?.data?.detail ?? "Error al contactar con el backend.");
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
      const response = await gnbApi.downloadLogs();
      triggerBlobDownload(response.data, "gnb.log");
    } catch (err) {
      setError(err.response?.data?.detail ?? "No se pudo descargar el log completo.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <Card className="lg:sticky lg:top-8">
      <div className="flex items-center justify-between px-4 py-3.5 border-b border-base-700">
        <span className="flex items-center gap-2 text-sm font-medium text-base-100">
          <FileText size={15} />
          Log del gNB
        </span>
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
            className="text-base-400 hover:text-signal-cyan transition"
            aria-label="Actualizar log"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      <form onSubmit={handleSearch} className="flex items-center gap-2 px-4 py-2.5 border-b border-base-700">
        <div className="relative flex-1">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-base-500" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Buscar en todo el log..."
            className="w-full rounded-md border border-base-600 bg-base-900 pl-7 pr-2 py-1.5 text-[11px] text-base-100 outline-none focus-visible:border-signal-cyan"
          />
        </div>
        {searchTerm && (
          <button
            type="button"
            onClick={clearSearch}
            className="text-base-500 hover:text-signal-coral transition"
            aria-label="Limpiar búsqueda"
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

      <p className="px-4 pt-2 text-[10px] text-base-500">
        La búsqueda recorre el fichero completo, no solo lo mostrado abajo.
      </p>

      {!searchTerm && (
        <div className="flex items-center gap-2 px-4 py-2.5 text-[11px]">
          <div className="flex rounded-md border border-base-600 overflow-hidden">
            <button
              onClick={() => setMode("head")}
              className={`px-2.5 py-1 transition ${
                mode === "head"
                  ? "bg-signal-cyan text-base-950 font-medium"
                  : "text-base-400 hover:text-base-200"
              }`}
            >
              Inicio
            </button>
            <button
              onClick={() => setMode("tail")}
              className={`px-2.5 py-1 transition ${
                mode === "tail"
                  ? "bg-signal-cyan text-base-950 font-medium"
                  : "text-base-400 hover:text-base-200"
              }`}
            >
              Final
            </button>
          </div>
          <select
            value={tail}
            onChange={(e) => setTail(Number(e.target.value))}
            className="ml-auto rounded-md border border-base-600 bg-base-900 text-base-300 px-2 py-1 outline-none"
          >
            <option value={100}>100 líneas</option>
            <option value={300}>300 líneas</option>
            <option value={1000}>1000 líneas</option>
          </select>
        </div>
      )}

      <pre className="px-4 py-3 text-[11px] font-mono text-base-300 overflow-x-auto max-h-[560px] overflow-y-auto whitespace-pre-wrap">
        {loading || searching ? (
          "Cargando..."
        ) : error ? (
          <span className="text-signal-coral">{error}</span>
        ) : (
          logs
        )}
      </pre>
    </Card>
  );
}

function StoragePathPanel({ path, onPathChanged }) {
  const [editing, setEditing] = useState(false);
  const [newPath, setNewPath] = useState(path ?? "");
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  function startEditing() {
    setNewPath(path ?? "");
    setFeedback(null);
    setEditing(true);
  }

  async function handleSave() {
    if (!newPath.trim()) return;
    setSaving(true);
    setFeedback(null);
    try {
      const response = await gnbApi.setCustomPresetsPath(newPath.trim());
      setFeedback({ ok: true, detail: response.data.detail });
      setEditing(false);
      onPathChanged();
    } catch (err) {
      setFeedback({
        ok: false,
        detail: err.response?.data?.detail ?? "Error al contactar con el backend.",
      });
    } finally {
      setSaving(false);
    }
  }

  function handleKeyDown(e) {
    // Sin <form> propio (ver más abajo, evita el problema de formularios
    // anidados dentro del <form> principal del gNB, que provocaba un
    // envío nativo de página completa en vez de ser interceptado por
    // React) -- se maneja Intro a mano para conservar la misma experiencia.
    if (e.key === "Enter") {
      e.preventDefault();
      handleSave();
    }
  }

  return (
    <div className="rounded-md border border-base-700 bg-base-900/50 px-3 py-2.5">
      <div className="flex items-center gap-2 text-xs text-base-300">
        <FolderCog size={13} className="shrink-0 text-base-400" />
        {editing ? (
          // Deliberadamente NO es un <form>: este componente se usa dentro
          // del <form> principal de la página (el de "Guardar y reiniciar
          // gNB"), y el HTML no admite formularios anidados -- el
          // navegador puede acabar disparando un envío nativo de página
          // completa en vez de dejar que React lo intercepte.
          <div className="flex-1 flex items-center gap-2">
            <input
              type="text"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="/ruta/absoluta/a/tu/fichero.json"
              className="flex-1 rounded-md border border-base-600 bg-base-950 px-2 py-1 font-mono text-[11px] text-base-100 outline-none focus-visible:border-signal-cyan"
              autoFocus
            />
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !newPath.trim()}
              className="text-[11px] font-medium text-signal-cyan disabled:opacity-40"
            >
              Guardar ruta
            </button>
            <button
              type="button"
              onClick={() => setEditing(false)}
              className="text-base-500 hover:text-signal-coral transition"
            >
              <X size={13} />
            </button>
          </div>
        ) : (
          <>
            <span className="font-mono break-all flex-1">{path}</span>
            <button
              type="button"
              onClick={startEditing}
              className="shrink-0 text-[11px] font-medium text-base-400 hover:text-signal-cyan transition"
            >
              Cambiar
            </button>
          </>
        )}
      </div>
      {feedback && (
        <p
          className={`mt-2 text-[11px] font-mono ${
            feedback.ok ? "text-signal-cyan" : "text-signal-coral"
          }`}
        >
          {feedback.detail}
        </p>
      )}
    </div>
  );
}

export default function GnbConfig() {
  const [form, setForm] = useState(null);
  const [presets, setPresets] = useState([]);
  const [customPresets, setCustomPresets] = useState([]);
  const [storagePath, setStoragePath] = useState(null);
  const [mode, setMode] = useState("preset"); // "preset" | "custom"
  const [selectedPresetId, setSelectedPresetId] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [result, setResult] = useState(null);
  const [stopping, setStopping] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [savingPreset, setSavingPreset] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [configRes, presetsRes, customRes] = await Promise.all([
        gnbApi.getConfig(),
        gnbApi.getPresets(),
        gnbApi.getCustomPresets(),
      ]);
      setForm(configRes.data);
      setPresets(presetsRes.data.presets);
      setCustomPresets(customRes.data.presets);
      setStoragePath(customRes.data.storage_path);

      const match = presetsRes.data.presets.find((p) => matchesPreset(configRes.data, p));
      if (match) {
        setMode("preset");
        setSelectedPresetId(match.id);
      } else {
        setMode("custom");
      }
    } catch {
      setLoadError(
        "No se pudo leer la configuración o los presets del gNB. Comprueba que el fichero exista y que el backend tenga permiso de lectura."
      );
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  function handleSelectPreset(preset) {
    setSelectedPresetId(preset.id);
    setForm((f) => ({ ...f, ...preset }));
  }

  function handleLoadCustomPreset(preset) {
    setMode("custom");
    setSelectedPresetId(null);
    setForm(preset.config);
  }

  async function handleDeleteCustomPreset(name) {
    await gnbApi.deleteCustomPreset(name);
    setCustomPresets((list) => list.filter((p) => p.name !== name));
  }

  async function handleSaveCustomPreset(e) {
    e.preventDefault();
    if (!newPresetName.trim()) return;
    setSavingPreset(true);
    try {
      await gnbApi.saveCustomPreset(newPresetName.trim(), form);
      const { data } = await gnbApi.getCustomPresets();
      setCustomPresets(data.presets);
      setNewPresetName("");
    } finally {
      setSavingPreset(false);
    }
  }

  function handleCustomFieldChange(key, value) {
    setForm((f) => ({ ...f, [key]: Number(value) }));
  }

  function handleGainChange(key, value) {
    setForm((f) => ({ ...f, [key]: Number(value) }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    setResult(null);
    try {
      const response = await gnbApi.updateConfig(form);
      setResult({ ok: response.data.success, detail: response.data.detail });
    } catch (err) {
      setResult({
        ok: false,
        detail:
          err.response?.data?.detail?.[0]?.msg ??
          err.response?.data?.detail ??
          "Error al contactar con el backend.",
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleStop() {
    setStopping(true);
    setResult(null);
    try {
      const response = await gnbApi.stop();
      setResult({ ok: response.data.success, detail: response.data.detail || "gNB detenido." });
    } catch (err) {
      setResult({
        ok: false,
        detail: err.response?.data?.detail ?? "Error al contactar con el backend.",
      });
    } finally {
      setStopping(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Radio"
        title="Configuración del gNB"
        description="Cambiar cualquier valor reinicia el proceso del gNB con la nueva configuración, interrumpiendo el servicio de radio brevemente."
      />

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_520px] gap-6 items-start">
        <div>
          <HardwarePanel />

          {loadError && (
            <Card className="px-5 py-4 mb-6 border-signal-coral/40 flex items-start gap-2 text-sm text-signal-coral">
              <AlertTriangle size={16} className="mt-0.5 shrink-0" />
              {loadError}
            </Card>
          )}

          {form && (
            <Card className="px-6 py-6">
              <form onSubmit={handleSubmit}>
                <div className="flex items-center gap-2 mb-5 text-xs">
                  <button
                    type="button"
                    onClick={() => setMode("preset")}
                    className={`px-3 py-1.5 rounded-md border transition ${
                      mode === "preset"
                        ? "border-signal-cyan text-signal-cyan"
                        : "border-base-600 text-base-400 hover:text-base-200"
                    }`}
                  >
                    Preset validado
                  </button>
                  <button
                    type="button"
                    onClick={() => setMode("custom")}
                    className={`px-3 py-1.5 rounded-md border transition ${
                      mode === "custom"
                        ? "border-signal-amber text-signal-amber"
                        : "border-base-600 text-base-400 hover:text-base-200"
                    }`}
                  >
                    Personalizado (avanzado)
                  </button>
                </div>

                {mode === "preset" && (
                  <div className="space-y-4 mb-6">
                    <div className="space-y-2">
                      {presets.map((preset) => (
                        <label
                          key={preset.id}
                          className={`flex items-start gap-3 rounded-md border px-4 py-3 cursor-pointer transition ${
                            selectedPresetId === preset.id
                              ? "border-signal-cyan bg-signal-cyan/5"
                              : "border-base-600 hover:border-base-500"
                          }`}
                        >
                          <input
                            type="radio"
                            name="preset"
                            checked={selectedPresetId === preset.id}
                            onChange={() => handleSelectPreset(preset)}
                            className="mt-1 accent-[var(--color-signal-cyan)]"
                          />
                          <div>
                            <p className="text-sm font-medium text-base-100">{preset.label}</p>
                            <p className="text-[11px] font-mono text-base-500 mt-0.5">
                              ARFCN {preset.dl_arfcn} · SCS {preset.common_scs} kHz · srate{" "}
                              {preset.srate} MSps
                            </p>
                            {preset.note && (
                              <p className="text-[11px] text-base-500 mt-1">{preset.note}</p>
                            )}
                          </div>
                        </label>
                      ))}
                    </div>

                    <div>
                      <p className="text-[11px] font-medium uppercase tracking-wide text-base-500 mb-2">
                        Tus configuraciones guardadas
                      </p>
                      {storagePath && (
                        <div className="mb-3">
                          <StoragePathPanel path={storagePath} onPathChanged={loadAll} />
                        </div>
                      )}
                      {customPresets.length === 0 ? (
                        <p className="text-xs text-base-500">
                          Aún no has guardado ninguna. Ve a "Personalizado", ajusta los valores
                          que quieras, y usa el botón "Guardar" de esa pestaña.
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {customPresets.map((preset) => (
                            <div
                              key={preset.name}
                              className="flex items-center justify-between gap-3 rounded-md border border-base-600 hover:border-base-500 px-4 py-3 transition"
                            >
                              <div className="flex-1">
                                <p className="text-sm font-medium text-base-100">{preset.name}</p>
                                <p className="text-[11px] font-mono text-base-500 mt-0.5">
                                  ARFCN {preset.config.dl_arfcn} ·{" "}
                                  {preset.config.channel_bandwidth_mhz} MHz · TX{" "}
                                  {preset.config.tx_gain} dB
                                </p>
                              </div>
                              <button
                                type="button"
                                onClick={() => handleLoadCustomPreset(preset)}
                                className="flex items-center gap-1.5 rounded-md border border-base-600 text-[11px] font-medium text-base-300 px-2.5 py-1.5 hover:border-signal-cyan hover:text-signal-cyan transition"
                              >
                                <Upload size={12} />
                                Cargar
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteCustomPreset(preset.name)}
                                className="text-base-500 hover:text-signal-coral transition"
                                aria-label={`Eliminar ${preset.name}`}
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {mode === "custom" && (
                  <>
                    <div className="flex items-start gap-2 rounded-md border border-signal-amber/40 bg-signal-amber/10 px-3 py-2.5 mb-4 text-[11px] text-signal-amber">
                      <ShieldAlert size={14} className="mt-[1px] shrink-0" />
                      <span>
                        Estos campos no son independientes entre sí: una combinación de banda,
                        ancho de banda, SCS y tasa de muestreo incompatible puede impedir que el
                        gNB arranque (ya ocurrió durante el desarrollo de este proyecto, con un
                        error de formato PRACH). Si no estás seguro, usa un preset validado.
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-x-5 gap-y-4 mb-4">
                      {CUSTOM_FIELDS.map((field) => (
                        <div key={field.key}>
                          <label className="block text-xs font-medium text-base-300 mb-1.5">
                            {field.label}
                          </label>
                          <div className="relative">
                            <input
                              type={field.type}
                              step={field.step}
                              value={form[field.key]}
                              onChange={(e) => handleCustomFieldChange(field.key, e.target.value)}
                              className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-amber"
                            />
                            {field.suffix && (
                              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-base-500">
                                {field.suffix}
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="mb-2">
                      <label className="block text-xs font-medium text-base-300 mb-1.5">
                        Guardar esta configuración con un nombre
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={newPresetName}
                          onChange={(e) => setNewPresetName(e.target.value)}
                          placeholder="p. ej. 'Prueba interior 15 MHz'"
                          className="flex-1 rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm text-base-100 outline-none focus-visible:border-signal-cyan"
                        />
                        <button
                          type="button"
                          onClick={handleSaveCustomPreset}
                          disabled={savingPreset || !newPresetName.trim()}
                          className="flex items-center gap-1.5 rounded-md border border-base-600 text-xs font-medium text-base-300 px-3 py-2 hover:border-signal-cyan hover:text-signal-cyan transition disabled:opacity-40"
                        >
                          <Save size={13} />
                          Guardar
                        </button>
                      </div>
                      {storagePath && (
                        <p className="text-[11px] font-mono text-base-400 mt-1.5 break-all">
                          Se guardará en: {storagePath}{" "}
                          <span className="text-base-500">
                            (cambiar la ubicación: pestaña "Preset validado")
                          </span>
                        </p>
                      )}
                    </div>
                  </>
                )}

                <div className="grid grid-cols-2 gap-x-5 gap-y-4 mb-6 pt-4 border-t border-base-700">
                  <div>
                    <label className="block text-xs font-medium text-base-300 mb-1.5">
                      Ganancia TX
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        min={0}
                        max={89.8}
                        step={0.1}
                        value={form.tx_gain}
                        onChange={(e) => handleGainChange("tx_gain", e.target.value)}
                        className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-cyan"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-base-500">
                        dB
                      </span>
                    </div>
                    <p className="text-[11px] text-base-500 mt-1">Rango real B210: 0 – 89.8 dB</p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-base-300 mb-1.5">
                      Ganancia RX
                    </label>
                    <div className="relative">
                      <input
                        type="number"
                        min={0}
                        max={76}
                        step={0.1}
                        value={form.rx_gain}
                        onChange={(e) => handleGainChange("rx_gain", e.target.value)}
                        className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-cyan"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-base-500">
                        dB
                      </span>
                    </div>
                    <p className="text-[11px] text-base-500 mt-1">Rango real B210: 0 – 76 dB</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <button
                    type="submit"
                    disabled={saving || (mode === "preset" && !selectedPresetId)}
                    className="flex items-center gap-2 rounded-md bg-signal-cyan text-base-950 text-sm font-medium px-4 py-2.5 hover:brightness-110 transition disabled:opacity-50"
                  >
                    <RadioTower size={15} />
                    {saving ? "Aplicando y reiniciando..." : "Guardar y reiniciar gNB"}
                  </button>

                  <button
                    type="button"
                    onClick={handleStop}
                    disabled={stopping}
                    className="flex items-center gap-2 rounded-md border border-base-600 text-base-300 text-sm font-medium px-4 py-2.5 hover:border-signal-coral hover:text-signal-coral transition disabled:opacity-50"
                  >
                    <Power size={15} />
                    {stopping ? "Deteniendo..." : "Detener gNB"}
                  </button>
                </div>
              </form>

              {result && (
                <div
                  className={`mt-5 rounded-md border px-4 py-3 text-sm font-mono whitespace-pre-line ${
                    result.ok
                      ? "border-signal-cyan/40 bg-signal-cyan/10 text-signal-cyan"
                      : "border-signal-coral/40 bg-signal-coral/10 text-signal-coral"
                  }`}
                >
                  {result.detail}
                </div>
              )}
            </Card>
          )}
        </div>

        <GnbLogsPanel />
      </div>
    </div>
  );
}
