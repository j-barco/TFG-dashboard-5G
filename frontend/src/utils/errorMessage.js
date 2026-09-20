/**
 * Formatea el mensaje de error de una llamada a la API, distinguiendo dos
 * situaciones muy distintas que antes compartían el mismo texto genérico:
 *
 * - El backend SÍ respondió, pero con un error (err.response existe):
 *   se muestra el detalle que el propio backend ya explica.
 * - El backend NO llegó a responder en absoluto (err.response es
 *   undefined -- conexión rechazada, backend caído a mitad de una
 *   operación, etc.): en este caso concreto, la acción solicitada puede
 *   haberse completado igualmente en segundo plano (p. ej. si el backend
 *   se cerró mientras 'docker compose down' seguía en curso, este último
 *   no depende del propio proceso del backend para completarse) -- así
 *   que el mensaje no debe dar a entender que la acción "no funcionó",
 *   solo que no se pudo confirmar el resultado desde aquí.
 */
export function getErrorMessage(err) {
  if (err.response?.data?.detail) {
    return err.response.data.detail;
  }
  return (
    "No se recibió respuesta del backend (puede haberse detenido a mitad de la " +
    "operación). Puede que la acción se completara igualmente -- comprueba el " +
    "estado actual antes de repetirla."
  );
}
