"""
Configuración central del backend, leída de variables de entorno.

Todas las variables tienen un valor por defecto seguro para desarrollo local;
en un despliegue real se recomienda fijarlas explícitamente (sobre todo
JWT_SECRET_KEY y las credenciales de administrador).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignora variables presentes en el .env que ya no correspondan a
        # ningún campo declarado aquí, en vez de fallar al arrancar. Evita
        # que un .env con restos de una configuración anterior (por
        # ejemplo, tras quitar una variable del código) tumbe la app.
        extra="ignore",
    )

    # --- Autenticación ---
    # Activada por defecto (fail-safe defaults, ver Metodología del TFG).
    # Para desactivarla explícitamente: AUTH_ENABLED=false en el .env
    auth_enabled: bool = True
    jwt_secret_key: str = "CAMBIAR_ESTA_CLAVE_EN_PRODUCCION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Credenciales del único usuario administrador (esquema simple,
    # suficiente para el alcance de este TFG; ver nota en auth.py sobre
    # posibles ampliaciones hacia varios usuarios/roles).
    admin_username: str = "admin"
    # Hash bcrypt de la contraseña por defecto "admin" -- CAMBIAR en cualquier
    # despliegue real. Generar uno nuevo con:
    #   python3 -c "import bcrypt; print(bcrypt.hashpw(b'tu_contraseña', bcrypt.gensalt()).decode())"
    admin_password_hash: str = "$2b$12$9mp6BL2wDk4NiqKyAkuqz.pu4Z0pAd0eXEtcb49YX7Iy4VivHdHxO"

    # --- Open5GS (Docker, ver Capítulo de Implementación) ---
    # Puerto de /metrics de cada función de red que soporta la métrica
    # 'ues_active' específicamente. Open5GS no implementa esta métrica en
    # todas las NFs -- su documentación oficial indica que solo AMF, MME
    # y SMF la soportan "por ahora"; se comprobó empíricamente que PCF y
    # UPF también responden en la versión 2.7.7 de este trabajo.
    # El estado de actividad/registro de TODAS las NFs (incluidas las que
    # no aparecen aquí) se obtiene por una vía distinta: el registro del
    # propio NRF (ver nrf_sbi_url y Sección "Todas las NFs monitorizables"
    # del Capítulo de Implementación y Desarrollo).
    nf_metrics_ports: dict[str, int] = {
        "amf": 9090,
        "smf": 9091,
        "pcf": 9096,
        "upf": 9099,
    }
    # Resto de NFs desplegadas, sin la métrica 'ues_active' pero sí
    # monitorizables por su registro en el NRF.
    nf_without_metrics: list[str] = ["nrf", "ausf", "udm", "udr", "nssf", "bsf"]
    open5gs_host: str = "localhost"

    # --- Registro del NRF (Nnrf_NFManagement), para el estado de TODAS
    #     las NFs, incluidas las que no exponen /metrics. Se consulta
    #     directamente contra la IP interna fija del NRF en la red de
    #     Docker (ver Implementación y Desarrollo, IPs internas fijas),
    #     ya que su puerto SBI no está publicado hacia el host. Requiere
    #     HTTP/2 sin negociación previa ("prior knowledge"), tal como
    #     exige la interfaz SBI de Open5GS.
    nrf_sbi_url: str = "http://10.33.33.3:80"

    # --- MongoDB (para gestión de suscriptores) ---
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "open5gs"

    # --- Control del gNB (script acotado, ver Metodología) ---
    gnb_ctl_script: str = "/path/to/dashboard-backend/scripts/gnb_ctl.sh"
    gnb_config_path: str = (
        "/path/to/srsRAN_Project/build/apps/gnb/gnb_config.yml"
    )
    # Debe coincidir con LOG_FILE dentro de gnb_ctl.sh (ver scripts/gnb_ctl.sh)
    # -- captura solo la salida estándar del arranque, no el detalle de
    # ejecución del gNB (ver gnb_log_path para eso).
    gnb_ctl_log_path: str = "/tmp/gnb_ctl.log"
    # Debe coincidir con 'log.filename' dentro del propio YAML del gNB --
    # el log real y detallado (con el nivel configurado ahí, p. ej.
    # 'warning'), a diferencia de gnb_ctl_log_path (solo el arranque). Es
    # un fichero de texto plano, legible sin privilegios especiales -- se
    # lee directamente desde Python, sin pasar por gnb_ctl.sh.
    gnb_log_path: str = "/tmp/gnb.log"
    # Configuraciones del gNB guardadas por el propio usuario desde el
    # panel (ver app/services/gnb_custom_presets.py) -- distinto de los
    # 'presets' fijos y verificados de gnb_control.KNOWN_GOOD_PRESETS.
    # Ruta POR DEFECTO -- el usuario puede cambiarla desde el propio panel
    # (ver gnb_custom_presets.set_path); en ese caso, la ruta realmente
    # usada se recuerda en gnb_custom_presets_pointer_path, no aquí.
    gnb_custom_presets_path: str = (
        "/path/to/dashboard-backend/data/gnb_custom_presets.json"
    )
    # Fichero interno, no visible en la interfaz, que recuerda si el
    # usuario cambió la ruta de guardado desde el panel -- para que la
    # elección persista entre reinicios del backend sin tener que
    # modificar el propio .env desde la aplicación.
    gnb_custom_presets_pointer_path: str = (
        "/path/to/dashboard-backend/data/.presets_path_override"
    )

    # --- Control del core en Docker (ver Implementación y Desarrollo) ---
    # La ruta del docker-compose.yaml/.env vive dentro del propio script
    # (igual que GNB_BIN en gnb_ctl.sh), no aquí -- el backend solo necesita
    # saber qué script invocar.
    docker_ctl_script: str = "/path/to/dashboard-backend/scripts/docker_ctl.sh"
    # Todas las NFs controlables individualmente desde el dashboard (coincide
    # con la unión de nf_metrics_ports y nf_unmonitored, más "db").
    core_services: list[str] = [
        "amf", "smf", "pcf", "upf", "nrf", "ausf", "udm", "udr", "nssf", "bsf",
    ]

    # --- CORS ---
    # Orígenes desde los que el navegador puede llamar a esta API (el
    # frontend corre en un puerto distinto al backend -- 5173 frente a
    # 8000 -- por lo que, sin esto, el navegador bloquea las respuestas
    # aunque el servidor las procese correctamente).
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- Histórico de tráfico N3 (ver Implementación y Desarrollo) ---
    # Muestreo en segundo plano, independiente de que alguien tenga el
    # panel abierto -- para que el histórico exista igualmente al volver.
    throughput_sample_interval_s: float = 5.0
    # Ventana conservada en memoria: 720 muestras a 5s = 1 hora.
    throughput_history_maxlen: int = 720


settings = Settings()
