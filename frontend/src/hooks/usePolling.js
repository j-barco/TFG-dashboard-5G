import { useEffect, useRef, useState, useCallback } from "react";

/**
 * Sondea periódicamente una función que devuelve una promesa (típicamente
 * una llamada a la API), manteniendo el último resultado válido en
 * pantalla si una consulta puntual falla, en vez de vaciar la interfaz --
 * ver Metodología del TFG, criterio de "degradación controlada" ya
 * aplicado en el propio backend.
 */
export function usePolling(fetchFn, intervalMs = 5000) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const fetchFnRef = useRef(fetchFn);
  fetchFnRef.current = fetchFn;

  const refresh = useCallback(async () => {
    try {
      const result = await fetchFnRef.current();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, intervalMs);
    return () => clearInterval(id);
  }, [refresh, intervalMs]);

  return { data, error, loading, refresh };
}
