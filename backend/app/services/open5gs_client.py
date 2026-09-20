"""
Cliente que consulta tres fuentes de datos de Open5GS, cada una validada
en el Capítulo de Implementación y Desarrollo del TFG:
  - El registro del propio NRF (Nnrf_NFManagement, /nnrf-nfm/v1/nf-instances),
    para saber si CADA UNA de las 10 NFs desplegadas está activa -- a
    diferencia de /metrics, disponible en todas, no solo en AMF/SMF/PCF/UPF.
  - /metrics (formato Prometheus) en las NFs que sí lo soportan, para datos
    adicionales (número de UEs activos, de gNBs registrados).
  - /ue-info y /pdu-info (infoAPI, JSON) en AMF y SMF, para el detalle de UEs.

Gestión del cliente HTTP: se reutiliza una única instancia de larga
duración de httpx.AsyncClient (una para HTTP/1.1, otra para el HTTP/2 sin
negociación previa que exige el NRF -- ver _fetch_nrf_registry), en vez de
crear y destruir un cliente por cada consulta. httpx desaconseja
explícitamente el patrón "un cliente por petición" para aplicaciones de
larga duración: cada creación/destrucción dispara un nuevo grupo de
conexiones (y su handshake TLS si lo hubiera) y deja sockets en estado de
cierre pendiente, que se acumulan a un ritmo de sondeo cada 5 segundos
durante horas seguidas -- se aplica esta corrección como medida preventiva
de fiabilidad de cara a sesiones largas (ver Implementación y Desarrollo).
"""
import asyncio
import logging

import httpx
from prometheus_client.parser import text_string_to_metric_families

from app.config import settings
from app.models.monitoring import NfStatus, PduSession, UeEntry

logger = logging.getLogger("dashboard.open5gs_client")

_HTTP_TIMEOUT = httpx.Timeout(3.0)  # el dashboard no debe congelarse si una NF no responde

# Clientes compartidos y de larga duración, creados de forma perezosa (en
# el primer uso, no al importar el módulo) para que cada uno quede atado
# al bucle de eventos asíncrono realmente en marcha en ese momento.
_client: httpx.AsyncClient | None = None
_nrf_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT)
    return _client


def _get_nrf_client() -> httpx.AsyncClient:
    """Cliente HTTP/2 sin negociación previa, exigido por la interfaz SBI
    del NRF (ver _fetch_nrf_registry) -- deliberadamente distinto del
    cliente HTTP/1.1 empleado para /metrics e infoAPI."""
    global _nrf_client
    if _nrf_client is None:
        _nrf_client = httpx.AsyncClient(http1=False, http2=True, timeout=_HTTP_TIMEOUT)
    return _nrf_client


async def close_clients() -> None:
    """Cierra ambos clientes de forma ordenada. Se invoca al apagar la
    aplicación (ver app/main.py)."""
    global _client, _nrf_client
    if _client is not None:
        await _client.aclose()
        _client = None
    if _nrf_client is not None:
        await _nrf_client.aclose()
        _nrf_client = None


def _reset_clients_for_tests() -> None:
    """Solo para pruebas: descarta el cliente compartido sin cerrarlo de
    forma asíncrona, forzando su recreación en el siguiente uso. Necesario
    porque cada prueba con pytest-asyncio puede correr en un bucle de
    eventos distinto (uno nuevo por función, por defecto), y un cliente
    httpx creado en un bucle ya cerrado no puede reutilizarse en otro."""
    global _client, _nrf_client
    _client = None
    _nrf_client = None


def _nf_base_url(nf_name: str) -> str:
    port = settings.nf_metrics_ports[nf_name]
    return f"http://{settings.open5gs_host}:{port}"


async def _fetch_text(url: str) -> str | None:
    try:
        response = await _get_client().get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        logger.warning("No se pudo contactar con %s: %s", url, exc)
        return None


async def _fetch_json(url: str) -> dict | None:
    try:
        response = await _get_client().get(url)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        logger.warning("No se pudo contactar con %s: %s", url, exc)
        return None


def _extract_metric_value(metrics_text: str, metric_name: str) -> float | None:
    """Busca una métrica concreta (gauge o counter, sin etiquetas) dentro
    de un texto Prometheus, devolviendo su valor. None si no aparece."""
    for family in text_string_to_metric_families(metrics_text):
        if family.name == metric_name:
            for sample in family.samples:
                return sample.value
    return None


def _extract_ues_active(metrics_text: str) -> int | None:
    """Busca la métrica 'ues_active' dentro del texto Prometheus.

    Verificado empíricamente en este despliegue (v2.7.7): solo el SMF
    expone esta métrica; el AMF, pese a estar documentado genéricamente
    junto al SMF como fuente de esta información, no la incluye en su
    /metrics. La función devuelve None con normalidad en ambos casos
    (NF sin la métrica o AMF sin soporte), no es un error."""
    value = _extract_metric_value(metrics_text, "ues_active")
    return int(value) if value is not None else None


def _extract_gnb_count(metrics_text: str) -> int | None:
    """Busca la métrica 'gnb' (gauge) dentro del texto Prometheus del AMF --
    el número de gNBs registrados en un instante dado, expuesto directamente
    por el propio AMF, sin necesidad de aproximarlo a través de /ue-info."""
    value = _extract_metric_value(metrics_text, "gnb")
    return int(value) if value is not None else None


def _extract_n3_packet_counters(metrics_text: str) -> tuple[int, int] | None:
    """
    Extrae los contadores acumulativos de paquetes GTP del UPF en la
    interfaz N3 (fivegs_ep_n3_gtp_in/outdatapktn3upf). Se mantiene esta
    extracción por completitud y como referencia histórica, pero se
    confirmó (ver Implementación y Desarrollo) que Open5GS deshabilita
    deliberadamente su actualización en el UPF por motivos de rendimiento
    -- el histórico de tráfico del panel usa en su lugar
    app.services.throughput_sampler, basado en el contador real de la
    regla MASQUERADE de iptables.

    Devuelve (paquetes_entrantes, paquetes_salientes) acumulados desde el
    arranque del UPF, o None si no se encuentran.
    """
    in_pkts = _extract_metric_value(metrics_text, "fivegs_ep_n3_gtp_indatapktn3upf")
    out_pkts = _extract_metric_value(metrics_text, "fivegs_ep_n3_gtp_outdatapktn3upf")
    if in_pkts is None or out_pkts is None:
        return None
    return int(in_pkts), int(out_pkts)


async def _fetch_nrf_registry() -> dict[str, str] | None:
    """
    Consulta el registro completo de NFs del NRF (servicio Nnrf_NFManagement,
    estándar 3GPP), devolviendo {tipo_de_nf_en_minúsculas: nfStatus}.

    A diferencia de /metrics, el registro del NRF cubre las 10 NFs
    desplegadas (toda NF se registra contra el NRF al arrancar, exponga o
    no /metrics), por lo que es la fuente empleada para saber si cada una
    está activa. Se consulta directamente contra la IP interna fija del
    NRF en la red de Docker, ya que su puerto SBI no está publicado hacia
    el host (ver Implementación y Desarrollo, IPs internas fijas).

    Requiere HTTP/2 sin negociación previa ("prior knowledge"), que es
    como Open5GS implementa su interfaz SBI en texto plano -- de ahí el
    cliente dedicado de _get_nrf_client(), distinto del empleado para
    /metrics e infoAPI (HTTP/1.1).
    """
    try:
        client = _get_nrf_client()
        list_response = await client.get(f"{settings.nrf_sbi_url}/nnrf-nfm/v1/nf-instances")
        list_response.raise_for_status()
        items = list_response.json().get("_links", {}).get("item", [])

        instance_ids = [
            item["href"].rstrip("/").rsplit("/", 1)[-1] for item in items if item.get("href")
        ]

        async def _fetch_detail(instance_id: str) -> dict | None:
            try:
                resp = await client.get(
                    f"{settings.nrf_sbi_url}/nnrf-nfm/v1/nf-instances/{instance_id}"
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                logger.warning(
                    "No se pudo consultar el detalle de la instancia %s en el NRF: %s",
                    instance_id,
                    exc,
                )
                return None

        details = await asyncio.gather(*(_fetch_detail(i) for i in instance_ids))

        registry: dict[str, str] = {}
        for detail in details:
            if detail is None:
                continue
            nf_type = detail.get("nfType", "").lower()
            nf_status = detail.get("nfStatus", "UNKNOWN")
            if nf_type:
                registry[nf_type] = nf_status
        return registry
    except httpx.HTTPError as exc:
        logger.warning("No se pudo consultar el registro del NRF: %s", exc)
        return None


async def get_core_status() -> list[NfStatus]:
    """
    Estado de las 10 NFs desplegadas, combinando dos fuentes:
      - El registro del NRF, para saber si cada una está activa
        (reachable) -- disponible para 9 de las 10.
      - /metrics, para las 4 NFs que lo soportan, tanto para el dato
        adicional de UEs activos (ues_active) como -- caso especial del
        UPF -- para determinar 'reachable' en sí.

    Caso especial: el UPF no implementa interfaz SBI y, por tanto, nunca
    se registra contra el NRF (confirmado por el propio equipo de
    desarrollo de Open5GS: es plano de usuario, se comunica con el SMF
    por PFCP, no por HTTP/SBI) -- su ausencia del registro del NRF es
    normal y no debe interpretarse como caída. Para el UPF se usa en su
    lugar la respuesta de su propio /metrics.
    """
    nrf_registry = await _fetch_nrf_registry()
    all_nf_names = list(settings.nf_metrics_ports) + list(settings.nf_without_metrics)

    statuses: list[NfStatus] = []
    for nf_name in all_nf_names:
        ues_active = None
        metrics_text = None
        if nf_name in settings.nf_metrics_ports:
            metrics_text = await _fetch_text(f"{_nf_base_url(nf_name)}/metrics")
            if metrics_text is not None:
                ues_active = _extract_ues_active(metrics_text)

        if nf_name == "upf":
            # El UPF no aparece en el registro del NRF por diseño (ver
            # docstring) -- se determina 'reachable' por /metrics.
            monitored = True
            reachable = metrics_text is not None
        elif nrf_registry is None:
            # El propio NRF no respondió -- no se puede saber el estado de
            # ninguna NF por esta vía (no se afirma "caída", se afirma
            # "no verificable en este instante").
            monitored, reachable = False, None
        else:
            monitored = True
            reachable = nrf_registry.get(nf_name) == "REGISTERED"

        statuses.append(
            NfStatus(name=nf_name, monitored=monitored, reachable=reachable, ues_active=ues_active)
        )

    return statuses


async def get_gnb_count() -> int:
    """
    Número de gNBs registrados, leído directamente de la métrica 'gnb'
    expuesta por el propio AMF. Se prefiere esta vía a aproximarlo a
    partir de /ue-info (contando gnb_id distintos entre los UEs
    conectados), ya que esa aproximación devuelve 0 siempre que no haya
    ningún UE conectado, aunque el gNB esté correctamente registrado.
    """
    text = await _fetch_text(f"{_nf_base_url('amf')}/metrics")
    if text is None:
        return 0
    return _extract_gnb_count(text) or 0


async def get_ue_list() -> list[UeEntry]:
    """Combina /ue-info (AMF) y /pdu-info (SMF) en una única lista por UE."""
    ue_data = await _fetch_json(f"{_nf_base_url('amf')}/ue-info")
    pdu_data = await _fetch_json(f"{_nf_base_url('smf')}/pdu-info")

    pdu_by_supi: dict[str, list[PduSession]] = {}
    if pdu_data:
        for item in pdu_data.get("items", []):
            supi = item.get("supi", "")
            sessions = [
                PduSession(
                    psi=pdu.get("psi", 0),
                    dnn=pdu.get("dnn", ""),
                    ipv4=pdu.get("ipv4"),
                    pdu_state=pdu.get("pdu_state", "unknown"),
                )
                for pdu in item.get("pdu", [])
            ]
            pdu_by_supi[supi] = sessions

    if not ue_data:
        return []

    ues: list[UeEntry] = []
    for item in ue_data.get("items", []):
        supi = item.get("supi", "")
        ues.append(
            UeEntry(
                supi=supi,
                ue_activity=item.get("ue_activity", "unknown"),
                sessions=pdu_by_supi.get(supi, []),
            )
        )
    return ues


async def fetch_upf_n3_packet_counters() -> tuple[int, int] | None:
    """Consulta el /metrics real del UPF y devuelve sus contadores
    acumulativos de paquetes N3 (entrantes, salientes). None si el UPF no
    respondió o si los contadores no aparecen en la respuesta."""
    text = await _fetch_text(f"{_nf_base_url('upf')}/metrics")
    if text is None:
        return None
    return _extract_n3_packet_counters(text)
