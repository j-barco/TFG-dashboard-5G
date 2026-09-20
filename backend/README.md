# Backend del panel de monitorización y gestión — TFG Juan Barco Gil

Segundo incremento (Fase 7): además de la monitorización (primer
incremento), se añaden los *endpoints* de **gestión**: configuración del
gNB, arranque/parada individual de las NFs del core (vía Docker), y
alta/baja de suscriptores.

## Instalación

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # incluye pytest y mongomock
```

## Configuración

```bash
cp .env.example .env
nano .env   # ajustar rutas y credenciales
```

**Importante**: la contraseña por defecto del `.env.example` es `admin` —
cámbiala antes de cualquier uso real, generando un hash nuevo con:
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'tu_contraseña', bcrypt.gensalt()).decode())"
```

## Configurar el privilegio mínimo para el control del gNB y del core

Tanto `scripts/gnb_ctl.sh` como `scripts/docker_ctl.sh` son los únicos
puntos por los que el backend puede actuar sobre el gNB y sobre el core en
Docker respectivamente (ambos requieren privilegios elevados, ver
Metodología del TFG). **El backend NUNCA debe correr como root, con `sudo`
genérico, ni pertenecer al grupo `docker`** (pertenecer a ese grupo
equivale en la práctica a privilegios de root sobre todo el sistema) — en
su lugar, se concede una regla `sudoers` acotada a cada script:

```bash
sudo cp scripts/gnb_ctl.sh scripts/docker_ctl.sh scripts/deployment.conf.example /home/<usuario>/Scripts/
sudo chmod +x /home/<usuario>/Scripts/gnb_ctl.sh /home/<usuario>/Scripts/docker_ctl.sh
cp /home/<usuario>/Scripts/deployment.conf.example /home/<usuario>/Scripts/deployment.conf
nano /home/<usuario>/Scripts/deployment.conf   # ajustar rutas si no coinciden
sudo visudo -f /etc/sudoers.d/dashboard
```
Y añade (sustituyendo `<usuario>` por el usuario real con el que corre el backend):
```
<usuario> ALL=(ALL) NOPASSWD: /home/<usuario>/Scripts/gnb_ctl.sh
<usuario> ALL=(ALL) NOPASSWD: /home/<usuario>/Scripts/docker_ctl.sh
```

Verifica que ambas reglas funcionan sin pedir contraseña:
```bash
sudo -n /home/<usuario>/Scripts/gnb_ctl.sh status
sudo -n /home/<usuario>/Scripts/docker_ctl.sh start amf
```

## Portabilidad: mover el proyecto a otra máquina

El proyecto está pensado para que **solo dos ficheros, ninguno de ellos
versionado, contengan valores específicos de la máquina en la que se
ejecuta** -- todo lo demás (código Python, scripts *bash*, plantillas) es
igual en cualquier sitio:

| Fichero | Dónde vive | Qué contiene |
|---|---|---|
| `.env` | Junto al backend | Credenciales, `AUTH_ENABLED`, rutas de scripts/config del gNB |
| `deployment.conf` | Junto a `gnb_ctl.sh`/`docker_ctl.sh` (p. ej. `/home/<usuario>/Scripts/`) | Ruta del binario del gNB, de la UHD compilada a mano, y del `docker-compose.yaml`/`.env` de Docker |

Al mover el proyecto a otra máquina (por ejemplo, al laboratorio del
tutor, o el día de la defensa), basta con:
1. Copiar `.env.example` → `.env` y `deployment.conf.example` →
   `deployment.conf`, ajustando las rutas de esa máquina concreta.
2. Repetir la configuración de `sudoers` (Sección anterior).
3. No haría falta tocar ningún fichero `.py` ni `.sh`.

Adicionalmente, las 10 funciones de red del core en Docker tienen su IP
interna **fijada explícitamente** en `docker-compose.yaml` (en vez de
asignarse dinámicamente por orden de arranque), lo que las hace estables
tanto entre reinicios como entre máquinas distintas -- ver
`docker-open5gs/compose-files/basic/docker-compose.yaml`.

**Limitación conocida, no resuelta por este mecanismo**: la variable
`DOCKER_HOST_IP` del despliegue Docker (dirección de la red local del
equipo, necesaria únicamente para que un UE físico real alcance el UPF)
sí es inherentemente específica de cada red, y debe ajustarse manualmente
en el `.env` de `docker-open5gs/` en cada máquina.

## Arrancar el servidor

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Documentación interactiva: **http://localhost:8000/docs**

## Ejecutar las pruebas

```bash
python3 -m pytest tests/ -v
```

Las pruebas **no requieren infraestructura real** (ni Open5GS, ni Docker,
ni MongoDB, ni el propio gNB):
- Los *endpoints* de monitorización se prueban verificando la degradación
  correcta cuando el core no responde.
- El CRUD de suscriptores se prueba con `mongomock` (MongoDB en memoria),
  verificando explícitamente que el documento generado coincide con el
  esquema real de Open5GS.
- El control del gNB se prueba con un YAML temporal (misma estructura que
  el fichero real del proyecto) para la lectura/escritura, y con
  `subprocess.run` simulado para el arranque/parada (que en la práctica
  requiere `sudo` y el propio hardware).
- Se verifica explícitamente que los *endpoints* de gestión exigen
  autenticación por defecto, y que respetan `AUTH_ENABLED=false`.

## Endpoints disponibles

### Monitorización (sin autenticación)
```
GET  /status/core    Estado de cada NF (10 desplegadas; monitorizadas vía registro del NRF, con UPF como caso especial vía /metrics)
GET  /status/gnb     Número de gNBs registrados
GET  /status/ues     Listado de UEs conectados con sus sesiones PDU
GET  /status/throughput  Histórico de tráfico de SUBIDA del UE (bytes/s), vía contador NAT del UPF -- ver Implementación y Desarrollo sobre por qué no las métricas GTP nativas de Open5GS
```

### Gestión (requieren token, salvo AUTH_ENABLED=false)
```
GET    /gnb/config              Configuración actual del gNB
GET    /gnb/hardware            Estado de ejecución y SDR detectado en el último arranque
GET    /gnb/presets              Presets fijos y verificados (n78/20MHz, n78/10MHz)
GET    /gnb/custom-presets       Configuraciones guardadas por el usuario
POST   /gnb/custom-presets       Guarda (o sustituye) una configuración con nombre
DELETE /gnb/custom-presets/{name} Elimina una configuración guardada
GET    /gnb/logs                Últimas líneas del log real y detallado del gNB (?tail=N)
PUT    /gnb/config              Cambia parámetros y reinicia el gNB
POST   /gnb/start               Arranca el gNB con la configuración actual (sin modificarla)
POST   /gnb/stop                Detiene el gNB

POST   /core/up                    Levanta las 10 NFs de una vez (docker compose up -d)
POST   /core/down                  Detiene y elimina las 10 NFs (docker compose down)
POST   /core/services/{nf}/start   Arranca una NF individual (Docker)
POST   /core/services/{nf}/stop    Detiene una NF individual (Docker)
POST   /core/services/{nf}/restart Reinicia una NF individual (Docker)
GET    /core/services/{nf}/logs    Últimas líneas de log de la NF (?tail=N, 1-1000)

GET    /subscribers             Lista de suscriptores
POST   /subscribers             Alta de un nuevo suscriptor
DELETE /subscribers/{imsi}      Baja de un suscriptor
```

## Probar el login

```bash
curl -X POST http://localhost:8000/auth/login \
  -d "username=admin&password=admin"
```

Y usar el token en las peticiones de gestión:
```bash
TOKEN="<pega aquí el access_token de la respuesta anterior>"
curl -X POST http://localhost:8000/core/services/amf/start \
  -H "Authorization: Bearer $TOKEN"
```

## Estructura del proyecto

```
app/
├── main.py
├── config.py
├── auth.py
├── models/
│   ├── monitoring.py
│   └── management.py          # Contrato de datos de gestión
├── routers/
│   ├── auth.py
│   ├── status.py
│   ├── gnb.py                  # Gestión del gNB
│   ├── core_management.py      # Arranque/parada de NFs
│   └── subscribers.py          # Alta/baja de suscriptores
└── services/
    ├── open5gs_client.py
    ├── mongo_client.py         # CRUD con el esquema real de Open5GS
    ├── gnb_control.py          # Lectura/escritura YAML + script acotado
    └── docker_control.py       # docker compose start/stop por NF
scripts/
└── gnb_ctl.sh                  # Script invocado con privilegios acotados
tests/
├── test_smoke.py
├── test_open5gs_client.py
├── test_mongo_client.py
├── test_gnb_control.py
├── test_docker_control.py
└── test_management_auth.py
```
