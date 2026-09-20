"""
Verifica que los endpoints de GESTIÓN (a diferencia de los de
monitorización) exigen autenticación, y que respetan el interruptor
AUTH_ENABLED tal como se diseñó en la Metodología del TFG.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def test_gnb_config_requires_auth_when_enabled():
    assert settings.auth_enabled is True  # valor por defecto, ver Metodología
    r = client.get("/gnb/config")
    assert r.status_code == 401


def test_core_service_action_requires_auth_when_enabled():
    r = client.post("/core/services/amf/start")
    assert r.status_code == 401


def test_subscribers_list_requires_auth_when_enabled():
    r = client.get("/subscribers")
    assert r.status_code == 401


def test_subscriber_create_requires_auth_when_enabled():
    r = client.post(
        "/subscribers",
        json={
            "imsi": "901700000000001",
            "k": "465B5CE8B199B49FAA5F0A2EE238A6BC",
            "opc": "E8ED289DEBA952E4283B54E88E6183CA",
        },
    )
    assert r.status_code == 401


def test_endpoints_accessible_with_valid_token():
    login = client.post("/auth/login", data={"username": "admin", "password": "admin"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.docker_control._run_ctl_script", return_value=(True, "ok")):
        r = client.post("/core/services/amf/start", headers=headers)
    assert r.status_code == 200


def test_endpoints_accessible_without_token_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", False)
    with patch("app.services.docker_control._run_ctl_script", return_value=(True, "ok")):
        r = client.post("/core/services/amf/start")
    assert r.status_code == 200
