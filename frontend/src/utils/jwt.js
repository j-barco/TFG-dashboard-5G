/**
 * Comprueba si un token JWT ha caducado, leyendo su propio campo "exp"
 * (segundos desde epoch) -- sin depender de ninguna librería, ya que un
 * JWT no es más que JSON codificado en base64url en tres partes separadas
 * por puntos.
 *
 * Se usa para no dar por "autenticado" un token simplemente porque
 * exista en localStorage de una sesión anterior ya caducada (60 minutos)
 * -- sin esto, una pestaña sin endpoints protegidos (como Resumen) nunca
 * detecta la caducidad, mientras que otra que sí los usa (como gNB) la
 * detecta de golpe al recibir un 401, dando la sensación de un
 * comportamiento inconsistente entre pestañas.
 */
export function isTokenExpired(token) {
  if (!token) return true;
  try {
    const payloadBase64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(payloadBase64));
    if (!payload.exp) return false; // sin campo exp -- se asume válido
    return Date.now() >= payload.exp * 1000;
  } catch {
    return true; // token malformado -- se trata como inválido, no como error
  }
}
