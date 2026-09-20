"""
Pruebas del parseo de las tres fuentes de datos de Open5GS, usando
fragmentos/estructuras reales capturados durante el desarrollo del TFG
(ver Capítulo de Implementación y Desarrollo), no datos inventados.
"""
from unittest.mock import patch

import pytest
import respx
from httpx import ConnectError, Response

from app.config import settings
from app.services import open5gs_client
from app.services.open5gs_client import (
    _extract_gnb_count,
    _extract_n3_packet_counters,
    _extract_ues_active,
    _fetch_nrf_registry,
    fetch_upf_n3_packet_counters,
    get_core_status,
    get_gnb_count,
    get_ue_list,
)


@pytest.fixture(autouse=True)
def reset_shared_http_clients():
    """
    Fuerza la recreación del cliente HTTP compartido antes y después de
    cada prueba de este fichero. Necesario porque pytest-asyncio arranca
    un bucle de eventos nuevo por cada función de prueba (por defecto), y
    un cliente httpx creado en un bucle ya cerrado no es reutilizable en
    otro -- ver docstring de open5gs_client._reset_clients_for_tests().
    """
    open5gs_client._reset_clients_for_tests()
    yield
    open5gs_client._reset_clients_for_tests()


REAL_PROMETHEUS_METRICS = """
# HELP gnb gNodeBs
# TYPE gnb gauge
gnb 1
# HELP amf_session AMF Sessions
# TYPE amf_session gauge
amf_session 0
# HELP ues_active Active User Equipments
# TYPE ues_active gauge
ues_active 3
# HELP ran_ue RAN UEs
# TYPE ran_ue gauge
ran_ue 0
"""

UE_INFO_SAMPLE = {
    "items": [{"supi": "imsi-901700000000001", "ue_activity": "connected", "gnb_id": 1}],
    "pager": {"page": 0, "page_size": 100, "count": 1},
}

PDU_INFO_SAMPLE = {
    "items": [
        {
            "supi": "imsi-901700000000001",
            "pdu": [{"psi": 1, "dnn": "internet", "ipv4": "10.45.0.11", "pdu_state": "active"}],
        }
    ]
}

# Estructura real, capturada de un despliegue de este trabajo
# (GET /nnrf-nfm/v1/nf-instances contra el NRF vía HTTP/2 prior knowledge).
NRF_LIST_RESPONSE = {
    "_links": {
        "item": [
            {"href": "http://nrf.open5gs.org/nnrf-nfm/v1/nf-instances/uuid-nrf"},
            {"href": "http://nrf.open5gs.org/nnrf-nfm/v1/nf-instances/uuid-amf"},
            {"href": "http://nrf.open5gs.org/nnrf-nfm/v1/nf-instances/uuid-udr"},
        ],
        "self": {"href": "http://nrf.open5gs.org/nnrf-nfm/v1/nf-instances"},
        "totalItemCount": 3,
    }
}

# Detalle real de una instancia (campos capturados directamente; los datos
# de nfServiceList se omiten aquí por brevedad, no se usan en el parseo).
NRF_DETAIL_NRF = {
    "nfInstanceId": "uuid-nrf",
    "nfType": "NRF",
    "nfStatus": "REGISTERED",
    "plmnList": [{"mcc": "901", "mnc": "70"}],
    "fqdn": "nrf.open5gs.org",
    "ipv4Addresses": ["10.33.33.3"],
}
NRF_DETAIL_AMF = {**NRF_DETAIL_NRF, "nfInstanceId": "uuid-amf", "nfType": "AMF"}
NRF_DETAIL_UDR = {**NRF_DETAIL_NRF, "nfInstanceId": "uuid-udr", "nfType": "UDR"}


def test_extract_ues_active_from_real_prometheus_text():
    assert _extract_ues_active(REAL_PROMETHEUS_METRICS) == 3


def test_extract_ues_active_missing_metric_returns_none():
    assert _extract_ues_active("# HELP algo_distinto\nalgo_distinto 1\n") is None


def test_extract_gnb_count_from_real_prometheus_text():
    assert _extract_gnb_count(REAL_PROMETHEUS_METRICS) == 1


# Captura real del /metrics del UPF de este trabajo (ver Implementación y
# Desarrollo, "Gráficas de tráfico N3") -- todo a 0 porque, en el momento
# de la captura, no había ningún UE pasando tráfico real por N3.
REAL_UPF_METRICS = """
# HELP fivegs_ep_n3_gtp_indatapktn3upf Number of incoming GTP data packets on the N3 interface
# TYPE fivegs_ep_n3_gtp_indatapktn3upf counter
fivegs_ep_n3_gtp_indatapktn3upf 0
# HELP fivegs_ep_n3_gtp_outdatapktn3upf Number of outgoing GTP data packets on the N3 interface
# TYPE fivegs_ep_n3_gtp_outdatapktn3upf counter
fivegs_ep_n3_gtp_outdatapktn3upf 0
# HELP fivegs_upffunction_upf_sessionnbr Active Sessions
# TYPE fivegs_upffunction_upf_sessionnbr gauge
fivegs_upffunction_upf_sessionnbr 0
# HELP pfcp_peers_active Active PFCP peers
# TYPE pfcp_peers_active gauge
pfcp_peers_active 1
"""


def test_extract_n3_packet_counters_from_real_metrics():
    assert _extract_n3_packet_counters(REAL_UPF_METRICS) == (0, 0)


def test_extract_n3_packet_counters_missing_returns_none():
    assert _extract_n3_packet_counters("# HELP algo_distinto\nalgo_distinto 1\n") is None


@pytest.mark.asyncio
async def test_fetch_upf_n3_packet_counters_returns_none_if_unreachable():
    with patch("app.services.open5gs_client._fetch_text", return_value=None):
        assert await fetch_upf_n3_packet_counters() is None


@pytest.mark.asyncio
async def test_get_gnb_count_reads_metric_even_without_connected_ues():
    """Caso real que motivó esta corrección: el gNB puede estar registrado
    en el AMF sin que haya ningún UE conectado (p. ej. antes de que se
    resuelva la incidencia de conexión del equipo de usuario, ver
    Implementación y Desarrollo) -- get_gnb_count debe reflejarlo
    correctamente en ese escenario, no solo cuando hay UEs."""
    with patch("app.services.open5gs_client._fetch_text", return_value=REAL_PROMETHEUS_METRICS):
        count = await get_gnb_count()
    assert count == 1


@pytest.mark.asyncio
async def test_get_ue_list_combines_ue_info_and_pdu_info():
    with patch("app.services.open5gs_client._fetch_json") as mock_fetch:
        mock_fetch.side_effect = [UE_INFO_SAMPLE, PDU_INFO_SAMPLE]
        ues = await get_ue_list()

    assert len(ues) == 1
    assert ues[0].supi == "imsi-901700000000001"
    assert ues[0].sessions[0].ipv4 == "10.45.0.11"
    assert ues[0].sessions[0].dnn == "internet"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_nrf_registry_parses_list_and_details():
    """Simula el registro con datos y estructura reales del NRF (ver
    Implementación y Desarrollo), incluyendo NFs SIN soporte de /metrics
    (UDR) -- es precisamente lo que esta vía viene a resolver."""
    base = settings.nrf_sbi_url
    respx.get(f"{base}/nnrf-nfm/v1/nf-instances").mock(
        return_value=Response(200, json=NRF_LIST_RESPONSE)
    )
    respx.get(f"{base}/nnrf-nfm/v1/nf-instances/uuid-nrf").mock(
        return_value=Response(200, json=NRF_DETAIL_NRF)
    )
    respx.get(f"{base}/nnrf-nfm/v1/nf-instances/uuid-amf").mock(
        return_value=Response(200, json=NRF_DETAIL_AMF)
    )
    respx.get(f"{base}/nnrf-nfm/v1/nf-instances/uuid-udr").mock(
        return_value=Response(200, json=NRF_DETAIL_UDR)
    )

    registry = await _fetch_nrf_registry()

    assert registry == {"nrf": "REGISTERED", "amf": "REGISTERED", "udr": "REGISTERED"}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_nrf_registry_returns_none_if_nrf_unreachable():
    base = settings.nrf_sbi_url
    respx.get(f"{base}/nnrf-nfm/v1/nf-instances").mock(side_effect=ConnectError("fallo simulado"))

    registry = await _fetch_nrf_registry()

    assert registry is None


@pytest.mark.asyncio
async def test_get_core_status_marks_all_ten_reachable_via_nrf_registry():
    """Con el NRF disponible y /metrics respondiendo, las 10 NFs son
    monitorizables y alcanzables -- incluidas las 6 sin /metrics (vía NRF)
    y el UPF (vía /metrics, ya que no se registra contra el NRF)."""
    all_names = list(settings.nf_metrics_ports) + list(settings.nf_without_metrics)
    fake_registry = {name: "REGISTERED" for name in all_names if name != "upf"}

    with patch(
        "app.services.open5gs_client._fetch_nrf_registry", return_value=fake_registry
    ), patch(
        "app.services.open5gs_client._fetch_text", return_value=REAL_PROMETHEUS_METRICS
    ):
        statuses = await get_core_status()

    assert len(statuses) == 10
    assert all(s.monitored for s in statuses)
    assert all(s.reachable is True for s in statuses)


@pytest.mark.asyncio
async def test_get_core_status_upf_uses_metrics_not_nrf_registry():
    """Caso real descubierto en este trabajo: el UPF no implementa
    interfaz SBI y por tanto NUNCA aparece en el registro del NRF, aunque
    esté perfectamente activo -- su ausencia del registro no debe
    interpretarse como 'sin servicio'. Se determina en su lugar por si
    responde a su propio /metrics."""
    all_names = list(settings.nf_metrics_ports) + list(settings.nf_without_metrics)
    # Registro real: el UPF nunca está aquí, con independencia de su estado.
    fake_registry = {name: "REGISTERED" for name in all_names if name != "upf"}

    async def fake_fetch_text(url: str):
        return REAL_PROMETHEUS_METRICS if "9099" in url else None  # 9099 = puerto del UPF

    with patch(
        "app.services.open5gs_client._fetch_nrf_registry", return_value=fake_registry
    ), patch("app.services.open5gs_client._fetch_text", side_effect=fake_fetch_text):
        statuses = await get_core_status()

    upf_status = next(s for s in statuses if s.name == "upf")
    assert upf_status.monitored is True
    assert upf_status.reachable is True  # activo según /metrics, pese a no estar en el NRF


@pytest.mark.asyncio
async def test_get_core_status_degrades_when_nrf_unreachable():
    with patch("app.services.open5gs_client._fetch_nrf_registry", return_value=None), patch(
        "app.services.open5gs_client._fetch_text", return_value=None
    ):
        statuses = await get_core_status()

    assert len(statuses) == 10

    upf_status = next(s for s in statuses if s.name == "upf")
    others = [s for s in statuses if s.name != "upf"]

    # El UPF no depende del NRF en absoluto (ver docstring de
    # get_core_status) -- sigue siendo monitorizable por /metrics, aunque
    # aquí no responda (metrics_text=None -> reachable=False, no None).
    assert upf_status.monitored is True
    assert upf_status.reachable is False

    # El resto de NFs sí dependen del NRF, que aquí no respondió.
    assert all(s.monitored is False for s in others)
    assert all(s.reachable is None for s in others)
