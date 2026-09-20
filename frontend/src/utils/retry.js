/**
 * Reintenta una petición SOLO si falló a nivel de red (sin respuesta del
 * servidor en absoluto -- p. ej. una interrupción breve de conexión),
 * nunca si el backend respondió con un error real (401, 400, 500...),
 * que debe mostrarse tal cual, no enmascararse con un reintento.
 *
 * Pensado para acciones idempotentes o seguras de repetir (arrancar/parar
 * el core o una NF, reiniciar el gNB...): si la operación ya se completó
 * de verdad en el primer intento (aunque la respuesta no llegara al
 * navegador), un segundo intento simplemente confirma que no hay nada
 * más que hacer y responde al instante, sin ningún efecto no deseado.
 */
export async function withRetryOnNetworkError(requestFn, retries = 1, delayMs = 1000) {
  try {
    return await requestFn();
  } catch (err) {
    const isNetworkLevelFailure = !err.response; // sin respuesta HTTP en absoluto
    if (isNetworkLevelFailure && retries > 0) {
      await new Promise((resolve) => setTimeout(resolve, delayMs));
      return withRetryOnNetworkError(requestFn, retries - 1, delayMs);
    }
    throw err;
  }
}
