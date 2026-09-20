"""
Modelos de datos de monitorización: son el "contrato" entre backend y
frontend. FastAPI valida automáticamente que cada respuesta cumpla estos
tipos, y genera con ellos la documentación interactiva en /docs.
"""
from typing import Literal

from pydantic import BaseModel, Field


class NfStatus(BaseModel):
    name: str = Field(description="Nombre corto de la función de red, p. ej. 'amf'")
    monitored: bool = Field(
        description="False únicamente si el propio NRF no respondió a la "
        "consulta de su registro (no se puede saber el estado de ninguna "
        "NF por esta vía en ese instante). Con el NRF disponible, las 10 "
        "NFs desplegadas son monitorizables."
    )
    reachable: bool | None = Field(
        default=None,
        description="Según el registro del NRF: True si nfStatus='REGISTERED', "
        "False si aparece con otro estado o no aparece; None si no se pudo "
        "consultar el NRF en absoluto.",
    )
    ues_active: int | None = Field(
        default=None,
        description="Solo disponible para AMF (no expone esta métrica), "
        "SMF, PCF y UPF -- ver nf_metrics_ports en la configuración.",
    )


class CoreStatusResponse(BaseModel):
    functions: list[NfStatus]


class GnbSummary(BaseModel):
    gnb_count: int


class PduSession(BaseModel):
    psi: int
    dnn: str
    ipv4: str | None = None
    pdu_state: str


class UeEntry(BaseModel):
    supi: str = Field(description="IMSI con prefijo 'imsi-', tal como lo da el infoAPI")
    ue_activity: Literal["idle", "connected"] | str
    sessions: list[PduSession] = []


class UeListResponse(BaseModel):
    ues: list[UeEntry]
    count: int


class ThroughputSample(BaseModel):
    timestamp: float = Field(description="Segundos desde epoch (time.time())")
    uplink_pkts_per_sec: float = Field(
        description="Tráfico de SUBIDA del UE (único sentido con contador "
        "real verificado -- ver 'note' de ThroughputHistoryResponse)"
    )
    uplink_bytes_per_sec: float


class ThroughputHistoryResponse(BaseModel):
    samples: list[ThroughputSample]
    note: str = (
        "Solo se mide la subida (tráfico del UE hacia la red externa), vía "
        "el contador de la regla MASQUERADE de iptables en el UPF -- "
        "confirmado en funcionamiento con tráfico real. Las métricas GTP "
        "nativas de Open5GS para N3 (fivegs_ep_n3_gtp_in/outdatapktn3upf) "
        "están deliberadamente deshabilitadas por el propio proyecto por "
        "motivos de rendimiento del plano de datos, y permanecen siempre "
        "en 0 con independencia del tráfico real. No existe, de momento, "
        "un contador de bajada igual de verificado."
    )
