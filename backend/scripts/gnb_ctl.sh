#!/bin/bash
#
# gnb_ctl.sh - Arranca/para/reinicia el proceso del gNB de forma controlada.
#
# Pensado para ser invocado por el backend del panel de monitorización
# mediante una regla sudoers ACOTADA a este script concreto (ver Metodología
# del TFG, Sección "Seguridad: privilegio mínimo y autenticación
# configurable") -- el backend nunca debe tener acceso genérico a sudo.
#
# Ejemplo de línea a añadir con 'sudo visudo -f /etc/sudoers.d/dashboard':
#   <usuario> ALL=(ALL) NOPASSWD: /ruta/a/gnb_ctl.sh
#
# Uso:
#   ./gnb_ctl.sh start <fichero.yml>
#   ./gnb_ctl.sh stop
#   ./gnb_ctl.sh restart <fichero.yml>
#   ./gnb_ctl.sh status
#
# Configuración específica de esta máquina: ver deployment.conf (no las
# rutas dentro de este script -- eso es justo lo que se quiere evitar
# para poder mover el proyecto a otra máquina sin editar código).

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE_PATH="$SCRIPT_DIR/deployment.conf"

if [ ! -f "$CONFIG_FILE_PATH" ]; then
  echo "ERROR: no se encuentra $CONFIG_FILE_PATH"
  echo "Copia deployment.conf.example como deployment.conf en esta misma carpeta y ajusta sus valores."
  exit 1
fi
# shellcheck source=deployment.conf
source "$CONFIG_FILE_PATH"

if [ -z "${GNB_BIN:-}" ]; then
  echo "ERROR: GNB_BIN no está definido en $CONFIG_FILE_PATH"
  exit 1
fi

GNB_DIR="$(dirname "$GNB_BIN")"
LOG_FILE="/tmp/gnb_ctl.log"
PID_FILE="/tmp/gnb_ctl.pid"

# Variables necesarias para que el binario enlace con una UHD compilada a
# mano en vez de la del sistema (ver Implementación y Desarrollo -- Sección
# "Prueba de control con una USRP B210"). 'sudo' arranca con un entorno
# mínimo, así que hay que fijarlas explícitamente aquí. Si UHD_LIB_DIR
# está vacío en deployment.conf (se usa la UHD del sistema), no se tocan.
if [ -n "${UHD_LIB_DIR:-}" ]; then
  export LD_LIBRARY_PATH="${UHD_LIB_DIR}:${LD_LIBRARY_PATH:-}"
fi
if [ -n "${UHD_IMAGES_DIR:-}" ]; then
  export UHD_IMAGES_DIR="${UHD_IMAGES_DIR}"
fi

start_gnb() {
  config_file="${1:-}"
  if [ -z "$config_file" ]; then
    echo "ERROR: falta la ruta al fichero de configuración del gNB"
    exit 1
  fi
  if [ ! -f "$config_file" ]; then
    echo "ERROR: no existe el fichero $config_file"
    exit 1
  fi
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "El gNB ya está en marcha (PID $(cat "$PID_FILE"))"
    return 0
  fi

  cd "$GNB_DIR" || exit 1
  nohup "$GNB_BIN" -c "$config_file" > "$LOG_FILE" 2>&1 &
  echo $! > "$PID_FILE"

  # Pequeña espera para detectar fallos de arranque inmediatos (p. ej.
  # configuración inválida) antes de devolver éxito.
  sleep 2
  if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "gNB arrancado correctamente (PID $(cat "$PID_FILE"))"
  else
    echo "ERROR: el gNB terminó inmediatamente tras arrancar. Log:"
    tail -20 "$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
  fi
}

stop_gnb() {
  if [ ! -f "$PID_FILE" ]; then
    echo "El gNB no parece estar en marcha (no hay PID registrado)"
    return 0
  fi
  pid="$(cat "$PID_FILE")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    sleep 1
    echo "gNB detenido (PID $pid)"
  else
    echo "El proceso (PID $pid) ya no existía"
  fi
  rm -f "$PID_FILE"
}

status_gnb() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "activo (PID $(cat "$PID_FILE"))"
  else
    echo "parado"
  fi
}

case "${1:-}" in
  start)
    start_gnb "${2:-}"
    ;;
  stop)
    stop_gnb
    ;;
  restart)
    stop_gnb
    sleep 1
    start_gnb "${2:-}"
    ;;
  status)
    status_gnb
    ;;
  *)
    echo "Uso: $0 {start <config.yml>|stop|restart <config.yml>|status}"
    exit 1
    ;;
esac
