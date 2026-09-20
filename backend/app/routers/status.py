"""
Endpoints de monitorización -- solo lectura, sin autenticación exigida
(ver Metodología: la autenticación se reserva a los endpoints que
modifican el estado del sistema).
"""
from fastapi import APIRouter

from app.models.monitoring import (
    CoreStatusResponse,
    GnbSummary,
    ThroughputHistoryResponse,
    UeListResponse,
)
from app.services import open5gs_client, throughput_sampler

router = APIRouter(prefix="/status", tags=["monitorización"])


@router.get("/core", response_model=CoreStatusResponse)
async def core_status():
    """Estado de cada función de red del core (activa/inactiva)."""
    functions = await open5gs_client.get_core_status()
    return CoreStatusResponse(functions=functions)


@router.get("/gnb", response_model=GnbSummary)
async def gnb_status():
    """Número de gNBs actualmente registrados en el core."""
    count = await open5gs_client.get_gnb_count()
    return GnbSummary(gnb_count=count)


@router.get("/ues", response_model=UeListResponse)
async def ue_status():
    """Listado de UEs conectados, con sus sesiones PDU."""
    ues = await open5gs_client.get_ue_list()
    return UeListResponse(ues=ues, count=len(ues))


@router.get("/throughput", response_model=ThroughputHistoryResponse)
async def throughput_history():
    """
    Histórico reciente de tráfico N3 (paquetes/s entrantes y salientes),
    calculado en segundo plano por el propio backend -- ver
    app/services/throughput_sampler.py.
    """
    return ThroughputHistoryResponse(samples=throughput_sampler.get_history())
