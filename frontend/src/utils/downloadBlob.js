/**
 * Convierte la respuesta de un endpoint de descarga (responseType: "blob")
 * en una descarga real de fichero en el navegador, sin necesitar que el
 * endpoint sea públicamente accesible por URL directa (el token de
 * autenticación va en la propia petición, no expuesto en ningún enlace).
 */
export function triggerBlobDownload(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
