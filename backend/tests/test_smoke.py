"""
Pruebas de humo del backend: no dependen de que Open5GS esté corriendo
(deben pasar incluso "en frío"), y verifican que el sistema degrada de
forma correcta cuando las NFs no responden, en vez de fallar.

Dos de ellas (marcadas más abajo) hacen peticiones reales de red, no
mockeadas -- si se ejecutan en una máquina con el despliegue Docker o el
gNB realmente activos, su resultado "en frío" ya no aplica. En vez de
fallar en ese caso, se SALTAN explícitamente con el motivo, para no dar
una falsa alarma cuando en realidad el sistema está funcionando.

Ejecutar con:
    python3 -m pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_auth_status_reflects_current_setting():
    r = client.get("/auth/status")
    assert r.status_code == 200
    assert r.json() == {"auth_enabled": True}  # valor por defecto, ver Metodología


def test_auth_status_does_not_require_a_token():
    # Sin ningún header Authorization -- debe responder igualmente 200,
    # es intencionadamente público (ver docstring del endpoint).
    r = client.get("/auth/status", headers={})
    assert r.status_code == 200


def test_login_correct_credentials():
    r = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_credentials():
    r = client.post("/auth/login", data={"username": "admin", "password": "incorrecta"})
    assert r.status_code == 401


def test_core_status_degrades_gracefully_without_open5gs():
    r = client.get("/status/core")
    assert r.status_code == 200
    functions = r.json()["functions"]
    assert len(functions) == 10  # 10 NFs desplegadas en total

    if any(nf["monitored"] for nf in functions):
        pytest.skip(
            "Se detecta infraestructura real activa (el NRF respondió) en "
            "esta máquina -- esta prueba solo verifica el escenario 'en "
            "frío', sin ningún despliegue levantado."
        )

    # Sin Open5GS levantado, ni el NRF responde -- las 10 NFs quedan como
    # "no verificable en este instante" (monitored=False, reachable=None),
    # no como "caídas" (ver Implementación y Desarrollo, registro del NRF).
    assert all(nf["monitored"] is False for nf in functions)
    assert all(nf["reachable"] is None for nf in functions)


def test_ue_status_empty_without_open5gs():
    r = client.get("/status/ues")
    assert r.status_code == 200
    assert r.json() == {"ues": [], "count": 0}


def test_gnb_status_zero_without_open5gs():
    r = client.get("/status/gnb")
    assert r.status_code == 200
    count = r.json()["gnb_count"]

    if count != 0:
        pytest.skip(
            f"Se detecta un gNB realmente registrado en el AMF de esta "
            f"máquina (gnb_count={count}) -- esta prueba solo verifica el "
            f"escenario 'en frío', sin ningún gNB conectado."
        )

    assert count == 0
