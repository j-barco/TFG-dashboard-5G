#!/bin/bash
#
# docker_ctl.sh - Arranca/para/reinicia una función de red concreta del
# core en Docker, consulta su log reciente, o lee el contador de tráfico
# de subida real del UE (regla MASQUERADE del UPF), de forma controlada.
#
# Igual que gnb_ctl.sh, pensado para ser invocado por el backend del panel
# mediante una regla sudoers ACOTADA a este script concreto (ver
# Metodología del TFG, Sección "Seguridad: privilegio mínimo y
# autenticación configurable") -- el backend nunca debe pertenecer al
# grupo 'docker' ni tener acceso genérico a sudo.
#
# Ejemplo de línea a añadir con 'sudo visudo -f /etc/sudoers.d/dashboard':
#   <usuario> ALL=(ALL) NOPASSWD: /ruta/a/docker_ctl.sh
#
# Uso:
#   ./docker_ctl.sh start <nf_name>
#   ./docker_ctl.sh stop <nf_name>
#   ./docker_ctl.sh restart <nf_name>
#   ./docker_ctl.sh logs <nf_name> [num_lineas]
#   ./docker_ctl.sh nat-stats
#   ./docker_ctl.sh core-up
#   ./docker_ctl.sh core-down
#
# Configuración específica de esta máquina: ver deployment.conf.

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

if [ -z "${DOCKER_COMPOSE_FILE:-}" ] || [ -z "${DOCKER_COMPOSE_ENV_FILE:-}" ]; then
  echo "ERROR: DOCKER_COMPOSE_FILE/DOCKER_COMPOSE_ENV_FILE no están definidos en $CONFIG_FILE_PATH"
  exit 1
fi

# Lista blanca de NFs gestionables -- coincide con settings.core_services
# del backend. Segunda barrera de seguridad independiente de la validación
# que ya hace el backend antes de invocar este script.
VALID_SERVICES="amf smf pcf upf nrf ausf udm udr nssf bsf"

USAGE="Uso: $0 {start|stop|restart} <nf_name>  |  $0 logs <nf_name> [num_lineas]  |  $0 logs-full <nf_name>  |  $0 logs-search <nf_name> <texto>  |  $0 nat-stats  |  $0 core-up  |  $0 core-down"

action="${1:-}"

# 'nat-stats', 'core-up' y 'core-down' no reciben NF -- son comandos fijos,
# sin ningún parámetro que venga del backend, por el mismo motivo de
# seguridad que 'nat-stats' (ver más abajo).
if [ "$action" = "nat-stats" ]; then
  docker exec upf iptables -t nat -L POSTROUTING -n -v -x
  exit $?
fi

if [ "$action" = "core-up" ]; then
  docker compose -f "$DOCKER_COMPOSE_FILE" --env-file "$DOCKER_COMPOSE_ENV_FILE" up -d
  exit $?
fi

if [ "$action" = "core-down" ]; then
  docker compose -f "$DOCKER_COMPOSE_FILE" --env-file "$DOCKER_COMPOSE_ENV_FILE" down
  exit $?
fi

nf="${2:-}"

if [ -z "$action" ] || [ -z "$nf" ]; then
  echo "$USAGE"
  exit 1
fi

valid=false
for s in $VALID_SERVICES; do
  if [ "$s" = "$nf" ]; then
    valid=true
    break
  fi
done
if [ "$valid" = false ]; then
  echo "ERROR: '$nf' no es una función de red gestionada por este script"
  exit 1
fi

case "$action" in
  start|stop|restart)
    docker compose -f "$DOCKER_COMPOSE_FILE" --env-file "$DOCKER_COMPOSE_ENV_FILE" "$action" "$nf"
    ;;
  logs)
    tail_lines="${3:-100}"
    if ! [[ "$tail_lines" =~ ^[0-9]+$ ]] || [ "$tail_lines" -lt 1 ] || [ "$tail_lines" -gt 1000 ]; then
      echo "ERROR: el número de líneas debe ser un entero entre 1 y 1000"
      exit 1
    fi
    docker compose -f "$DOCKER_COMPOSE_FILE" --env-file "$DOCKER_COMPOSE_ENV_FILE" \
      logs --no-color --tail "$tail_lines" "$nf"
    ;;
  logs-full)
    # Sin límite de líneas -- pensado para descarga, no para mostrar en
    # pantalla directamente (puede ser grande en contenedores de larga duración).
    docker compose -f "$DOCKER_COMPOSE_FILE" --env-file "$DOCKER_COMPOSE_ENV_FILE" \
      logs --no-color "$nf"
    ;;
  logs-search)
    # El término de búsqueda se pasa como argumento separado a 'grep', no
    # concatenado dentro de una cadena de shell -- así los metacaracteres
    # que pudiera contener nunca se interpretan como código. '-F' fuerza
    # búsqueda de cadena literal (no expresión regular, evita ataques de
    # tipo ReDoS con patrones maliciosos); '--' evita que un término que
    # empiece por '-' se interprete como una opción de grep.
    search_term="${3:-}"
    if [ -z "$search_term" ]; then
      echo "ERROR: falta el término de búsqueda"
      exit 1
    fi
    docker compose -f "$DOCKER_COMPOSE_FILE" --env-file "$DOCKER_COMPOSE_ENV_FILE" \
      logs --no-color "$nf" | grep -F -i -- "$search_term"
    ;;
  *)
    echo "$USAGE"
    exit 1
    ;;
esac
