"""
Modelos de datos de los endpoints de GESTIÓN (a diferencia de los de
monitorización, estos requieren autenticación -- ver Metodología).
"""
import re

from pydantic import BaseModel, Field, field_validator

# --- gNB ---


class GnbConfig(BaseModel):
    band: int = Field(description="Banda NR, p. ej. 78")
    dl_arfcn: int = Field(description="ARFCN del downlink")
    channel_bandwidth_mhz: int = Field(description="Ancho de banda de canal en MHz")
    common_scs: int = Field(description="Subcarrier spacing común, en kHz")
    srate: float = Field(
        description="Tasa de muestreo (MSps). Debe ser coherente con "
        "band/channel_bandwidth_mhz/common_scs -- ver Implementación y "
        "Desarrollo, incidencia de configuración inválida de PRACH."
    )
    # Límites reales del hardware (USRP B210), confirmados en la
    # documentación oficial de Ettus -- nunca negativos en esta tarjeta,
    # a diferencia de la bladeRF (rango 'dsa' con valores negativos).
    tx_gain: float = Field(ge=0, le=89.8, description="Ganancia TX en dB (rango real B210: 0-89.8)")
    rx_gain: float = Field(ge=0, le=76, description="Ganancia RX en dB (rango real B210: 0-76)")


class GnbPreset(BaseModel):
    """
    Combinación de parámetros de radio verificada realmente en este
    trabajo (ver Implementación y Desarrollo) -- a diferencia de dejar
    banda/ARFCN/ancho de banda/SCS/srate como campos libres independientes,
    que ya causó una configuración inválida real durante el desarrollo
    (incompatibilidad entre srate y el formato PRACH).
    """
    id: str
    label: str
    band: int
    dl_arfcn: int
    channel_bandwidth_mhz: int
    common_scs: int
    srate: float
    note: str = ""


class GnbPresetListResponse(BaseModel):
    presets: list[GnbPreset]


class SavedGnbConfig(BaseModel):
    """
    Configuración completa del gNB guardada por el propio usuario con un
    nombre elegido por él, a diferencia de GnbPreset (fijos, verificados
    por este trabajo, no editables desde el panel). Incluye también las
    ganancias, ya que forman parte de lo que el usuario quiere recordar
    tal cual lo dejó.
    """
    name: str = Field(min_length=1, max_length=60)
    config: GnbConfig


class SavedGnbConfigListResponse(BaseModel):
    presets: list[SavedGnbConfig]
    storage_path: str = Field(
        description="Ruta del fichero donde se guardan estas configuraciones "
        "en esta máquina -- informativo, para que quede claro dónde viven "
        "los datos (no es una base de datos ni MongoDB)."
    )


class SetPresetsPathRequest(BaseModel):
    path: str = Field(min_length=1, description="Ruta absoluta del nuevo fichero de guardado")


class GnbActionResult(BaseModel):
    action: str
    success: bool
    detail: str


class GnbHardwareStatus(BaseModel):
    running: bool
    detected_device: str | None = Field(
        default=None,
        description="Nombre del SDR detectado en el último arranque (leído "
        "del log de arranque, no del YAML de configuración). None si el "
        "gNB no ha arrancado nunca en esta máquina o si el controlador "
        "empleado no imprime esta línea concreta.",
    )


class GnbLogsResponse(BaseModel):
    success: bool
    logs: str


# --- Core (arranque/parada de NFs individuales) ---


class NfActionResult(BaseModel):
    nf: str
    action: str
    success: bool
    detail: str


class CoreActionResult(BaseModel):
    action: str
    success: bool
    detail: str


class NfLogsResponse(BaseModel):
    nf: str
    success: bool
    logs: str


# --- Suscriptores ---
# Esquema real de Open5GS en MongoDB, confirmado contra la herramienta
# oficial open5gs-dbctl y ejemplos reales de despliegues -- no es un
# esquema inventado, para que un suscriptor creado desde aquí sea
# indistinguible de uno creado desde el WebUI oficial.

_IMSI_RE = re.compile(r"^\d{15}$")
_HEX32_RE = re.compile(r"^[0-9A-Fa-f]{32}$")


class SubscriberCreate(BaseModel):
    imsi: str = Field(description="15 dígitos, debe empezar por el PLMN del proyecto (90170)")
    k: str = Field(description="Clave K, 32 caracteres hexadecimales")
    opc: str = Field(description="OPc, 32 caracteres hexadecimales")
    amf: str = Field(default="8000", description="Campo AMF de la clave de autenticación")
    dnn: str = Field(default="internet", description="APN/DNN de la sesión por defecto")
    sst: int = Field(default=1, description="Slice/Service Type")

    @field_validator("imsi")
    @classmethod
    def validate_imsi(cls, v: str) -> str:
        if not _IMSI_RE.match(v):
            raise ValueError("El IMSI debe tener exactamente 15 dígitos")
        return v

    @field_validator("k", "opc")
    @classmethod
    def validate_hex32(cls, v: str) -> str:
        if not _HEX32_RE.match(v):
            raise ValueError("Debe ser una cadena hexadecimal de 32 caracteres")
        return v.upper()


class SubscriberSummary(BaseModel):
    imsi: str
    dnn: str
    sst: int


class SubscriberListResponse(BaseModel):
    subscribers: list[SubscriberSummary]
    count: int
