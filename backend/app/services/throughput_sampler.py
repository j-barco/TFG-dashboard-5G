"""
Muestreo periódico, en segundo plano, del tráfico de SUBIDA real del
equipo de usuario (UE), leído del contador de la regla `MASQUERADE` de
`iptables` dentro del contenedor del UPF (subred `10.45.0.0/16` -> resto
de interfaces), en vez de las métricas GTP nativas de Open5GS para la
interfaz N3.

Motivo del cambio (ver Implementación y Desarrollo): se confirmó, contra
el propio código fuente de Open5GS, que las métricas
`fivegs_ep_n3_gtp_in/outdatapktn3upf` están deliberadamente deshabilitadas
(bloque `#if 0`) por motivos de rendimiento del plano de datos del UPF, y
por tanto permanecen siempre en 0 con independencia de si existe tráfico
real -- se comprobó empíricamente con tráfico real generado por un UE
conectado (incidencia de la Sección "Resolución de la incidencia de
conexión del equipo de usuario").

Limitación conocida y deliberadamente asumida: la regla `MASQUERADE`
consultada solo contabiliza el tráfico que SALE de la subred del UE hacia
el exterior (subida). No existe, de momento, un contador de bajada
igualmente verificado -- se prefiere mostrar una única dirección real y
confirmada antes que inventar una segunda que no se ha comprobado.

Se ejecuta como tarea de fondo de la propia aplicación (arrancada en
app/main.py vía el gestor de ciclo de vida de FastAPI), independiente de
que el frontend consulte el panel en un momento dado. La lectura en sí
delega en `docker_control.get_nat_stats()`, que ejecuta un `subprocess`
bloqueante (vía el script acotado por sudoers) -- se envuelve con
`asyncio.to_thread` para no bloquear el bucle de eventos asíncrono
mientras dura esa llamada.
"""
import asyncio
import logging
import re
import time
from collections import deque

from app.config import settings
from app.models.monitoring import ThroughputSample
from app.services import docker_control

logger = logging.getLogger("dashboard.throughput_sampler")

# Histórico en memoria (no persiste entre reinicios del backend -- ver
# limitación equivalente ya asumida para el resto del estado del panel).
_history: deque[ThroughputSample] = deque(maxlen=settings.throughput_history_maxlen)
_last_counters: tuple[int, int] | None = None
_last_timestamp: float | None = None
_task: asyncio.Task | None = None

# Busca la línea de la regla MASQUERADE sobre la subred de sesiones de
# datos de Open5GS, en la salida de 'iptables -t nat -L POSTROUTING -n -v -x'
# (con -x, los contadores se muestran en su valor exacto, sin abreviar a K/M).
_MASQUERADE_LINE_RE = re.compile(
    r"^\s*(\d+)\s+(\d+)\s+MASQUERADE\s+.*10\.45\.0\.0/16", re.MULTILINE
)


def parse_nat_masquerade_counters(iptables_output: str) -> tuple[int, int] | None:
    """
    Extrae (paquetes, bytes) acumulados de la regla MASQUERADE que actúa
    sobre la subred 10.45.0.0/16, a partir de la salida en bruto de
    'iptables -t nat -L POSTROUTING -n -v -x'. Función pura, separada de
    la E/S, para poder probarla de forma aislada con datos reales
    capturados durante el desarrollo.
    """
    match = _MASQUERADE_LINE_RE.search(iptables_output)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def compute_rate(
    prev_counters: tuple[int, int],
    prev_timestamp: float,
    new_counters: tuple[int, int],
    new_timestamp: float,
) -> tuple[float, float]:
    """
    Calcula (paquetes/s, bytes/s) de subida a partir de dos lecturas
    consecutivas de los contadores acumulativos de la regla MASQUERADE.

    Devuelve (0.0, 0.0) si el intervalo es nulo o negativo, y trata un
    contador que retrocede (p. ej. tras recrear el contenedor del UPF,
    cuyas reglas de iptables se reinician) como "sin dato fiable para
    este intervalo" en lugar de devolver una tasa negativa sin sentido.
    """
    elapsed = new_timestamp - prev_timestamp
    if elapsed <= 0:
        return 0.0, 0.0

    pkts_delta = new_counters[0] - prev_counters[0]
    bytes_delta = new_counters[1] - prev_counters[1]

    pkts_rate = max(pkts_delta, 0) / elapsed
    bytes_rate = max(bytes_delta, 0) / elapsed
    return pkts_rate, bytes_rate


async def _sample_once() -> None:
    global _last_counters, _last_timestamp

    # docker_control.get_nat_stats() ya es 'async' y delega su propia
    # llamada bloqueante a subprocess.run en un hilo aparte internamente
    # (ver docker_control._run_ctl_script) -- no hay que envolverla aquí
    # también, bastaría con 'await' directamente.
    success, output = await docker_control.get_nat_stats()
    now = time.time()

    if not success:
        logger.warning("No se pudo consultar el contador NAT del UPF en este ciclo: %s", output)
        return

    counters = parse_nat_masquerade_counters(output)
    if counters is None:
        logger.warning(
            "No se encontró la regla MASQUERADE esperada en la salida de iptables"
        )
        return

    if _last_counters is not None and _last_timestamp is not None:
        pkts_rate, bytes_rate = compute_rate(_last_counters, _last_timestamp, counters, now)
        _history.append(
            ThroughputSample(
                timestamp=now, uplink_pkts_per_sec=pkts_rate, uplink_bytes_per_sec=bytes_rate
            )
        )

    _last_counters = counters
    _last_timestamp = now


async def _sampler_loop() -> None:
    logger.info(
        "Muestreador de tráfico de subida (NAT) iniciado (intervalo=%ss, ventana=%s muestras)",
        settings.throughput_sample_interval_s,
        settings.throughput_history_maxlen,
    )
    while True:
        try:
            await _sample_once()
        except Exception:
            # Un fallo puntual de un ciclo no debe tumbar el muestreador
            # completo -- se reintenta en el siguiente ciclo.
            logger.exception("Error inesperado en un ciclo del muestreador de tráfico")
        await asyncio.sleep(settings.throughput_sample_interval_s)


def start() -> None:
    """Arranca la tarea de fondo. Se invoca una sola vez, al arrancar la
    aplicación (ver app/main.py)."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_sampler_loop())


async def stop() -> None:
    """Detiene la tarea de fondo de forma ordenada. Se invoca al apagar
    la aplicación (ver app/main.py)."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None


def get_history() -> list[ThroughputSample]:
    return list(_history)


def _reset_for_tests() -> None:
    """Vacía el estado del módulo -- solo para aislar pruebas entre sí,
    dado que el histórico vive en una variable de módulo compartida."""
    global _last_counters, _last_timestamp
    _history.clear()
    _last_counters = None
    _last_timestamp = None
