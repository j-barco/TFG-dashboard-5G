import { useState } from "react";
import { Plus, Trash2, X } from "lucide-react";
import { PageHeader, Card } from "../components/Card";
import { usePolling } from "../hooks/usePolling";
import { subscribers as subscribersApi } from "../api/endpoints";

const EMPTY_FORM = { imsi: "", k: "", opc: "", amf: "8000", dnn: "internet", sst: 1 };

export default function Subscribers() {
  const list = usePolling(() => subscribersApi.list().then((r) => r.data), 8000);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [deletingImsi, setDeletingImsi] = useState(null);

  function updateField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleCreate(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await subscribersApi.create({ ...form, sst: Number(form.sst) });
      setForm(EMPTY_FORM);
      setShowForm(false);
      list.refresh();
    } catch (err) {
      setError(err.response?.data?.detail ?? "No se pudo dar de alta el suscriptor.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(imsi) {
    setDeletingImsi(imsi);
    try {
      await subscribersApi.remove(imsi);
      list.refresh();
    } finally {
      setDeletingImsi(null);
    }
  }

  const items = list.data?.subscribers ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Suscriptores"
        title="Suscriptores del PLMN 001/01"
        action={
          <button
            onClick={() => setShowForm((s) => !s)}
            className="flex items-center gap-2 rounded-md bg-signal-cyan text-base-950 text-sm font-medium px-3.5 py-2 hover:brightness-110 transition"
          >
            {showForm ? <X size={15} /> : <Plus size={15} />}
            {showForm ? "Cancelar" : "Nuevo suscriptor"}
          </button>
        }
      />

      {showForm && (
        <Card className="px-6 py-6 mb-6 max-w-lg">
          <form onSubmit={handleCreate}>
            <div className="grid grid-cols-2 gap-x-4 gap-y-4 mb-5">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-base-300 mb-1.5">
                  IMSI (15 dígitos)
                </label>
                <input
                  required
                  value={form.imsi}
                  onChange={(e) => updateField("imsi", e.target.value)}
                  placeholder="001010000000001"
                  className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-cyan"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-base-300 mb-1.5">
                  K (32 hex)
                </label>
                <input
                  required
                  value={form.k}
                  onChange={(e) => updateField("k", e.target.value)}
                  className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-cyan"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-base-300 mb-1.5">
                  OPc (32 hex)
                </label>
                <input
                  required
                  value={form.opc}
                  onChange={(e) => updateField("opc", e.target.value)}
                  className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-cyan"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-base-300 mb-1.5">DNN</label>
                <input
                  value={form.dnn}
                  onChange={(e) => updateField("dnn", e.target.value)}
                  className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-cyan"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-base-300 mb-1.5">SST</label>
                <input
                  type="number"
                  value={form.sst}
                  onChange={(e) => updateField("sst", e.target.value)}
                  className="w-full rounded-md border border-base-600 bg-base-900 px-3 py-2 text-sm font-mono text-base-100 outline-none focus-visible:border-signal-cyan"
                />
              </div>
            </div>

            {error && <p className="mb-4 text-sm text-signal-coral">{error}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-signal-cyan text-base-950 text-sm font-medium px-4 py-2.5 hover:brightness-110 transition disabled:opacity-50"
            >
              {submitting ? "Creando..." : "Dar de alta"}
            </button>
          </form>
        </Card>
      )}

      <Card>
        {items.length === 0 && (
          <p className="px-5 py-6 text-sm text-base-400">
            {list.loading ? "Cargando..." : "No hay ningún suscriptor dado de alta."}
          </p>
        )}
        {items.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-base-700 text-left text-xs text-base-400 uppercase tracking-wide">
                <th className="px-5 py-3 font-medium">IMSI</th>
                <th className="px-5 py-3 font-medium">DNN</th>
                <th className="px-5 py-3 font-medium">SST</th>
                <th className="px-5 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-base-700">
              {items.map((s) => (
                <tr key={s.imsi}>
                  <td className="px-5 py-3 font-mono text-base-100">{s.imsi}</td>
                  <td className="px-5 py-3 font-mono text-base-300">{s.dnn}</td>
                  <td className="px-5 py-3 font-mono text-base-300">{s.sst}</td>
                  <td className="px-5 py-3 text-right">
                    <button
                      onClick={() => handleDelete(s.imsi)}
                      disabled={deletingImsi === s.imsi}
                      className="text-base-500 hover:text-signal-coral transition disabled:opacity-40"
                      aria-label={`Eliminar suscriptor ${s.imsi}`}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
