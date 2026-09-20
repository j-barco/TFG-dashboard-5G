"""
Pruebas del cliente de MongoDB, usando mongomock (una base de datos en
memoria compatible con la API de pymongo) en lugar de un Mongo real, para
poder verificar el esquema del documento sin depender de infraestructura
externa durante el desarrollo.
"""
import mongomock
import pytest

from app.models.management import SubscriberCreate
from app.services import mongo_client


@pytest.fixture(autouse=True)
def fake_mongo(monkeypatch):
    """Sustituye el cliente real de Mongo por uno en memoria para cada test."""
    fake_client = mongomock.MongoClient()
    monkeypatch.setattr(mongo_client, "_client", fake_client)
    yield fake_client


def test_create_subscriber_builds_correct_open5gs_schema():
    data = SubscriberCreate(
        imsi="901700000000001",
        k="465b5ce8b199b49faa5f0a2ee238a6bc",  # en minúsculas a propósito
        opc="e8ed289deba952e4283b54e88e6183ca",
        amf="8000",
        dnn="internet",
        sst=1,
    )
    mongo_client.create_subscriber(data)

    doc = mongo_client._get_collection().find_one({"imsi": "901700000000001"})
    assert doc is not None
    assert doc["security"]["k"] == "465B5CE8B199B49FAA5F0A2EE238A6BC"  # normalizado a mayúsculas
    assert doc["security"]["opc"] == "E8ED289DEBA952E4283B54E88E6183CA"
    assert doc["security"]["amf"] == "8000"
    assert doc["security"]["op"] is None
    assert doc["slice"][0]["sst"] == 1
    assert doc["slice"][0]["session"][0]["name"] == "internet"
    assert doc["slice"][0]["session"][0]["type"] == 1  # IPv4 puro


def test_create_subscriber_rejects_duplicate_imsi():
    data = SubscriberCreate(
        imsi="901700000000001",
        k="465B5CE8B199B49FAA5F0A2EE238A6BC",
        opc="E8ED289DEBA952E4283B54E88E6183CA",
    )
    mongo_client.create_subscriber(data)

    with pytest.raises(ValueError, match="Ya existe"):
        mongo_client.create_subscriber(data)


def test_delete_subscriber():
    data = SubscriberCreate(
        imsi="901700000000001",
        k="465B5CE8B199B49FAA5F0A2EE238A6BC",
        opc="E8ED289DEBA952E4283B54E88E6183CA",
    )
    mongo_client.create_subscriber(data)

    assert mongo_client.delete_subscriber("901700000000001") is True
    assert mongo_client.delete_subscriber("901700000000001") is False  # ya no existe


def test_list_subscribers():
    mongo_client.create_subscriber(
        SubscriberCreate(
            imsi="901700000000001",
            k="465B5CE8B199B49FAA5F0A2EE238A6BC",
            opc="E8ED289DEBA952E4283B54E88E6183CA",
        )
    )
    mongo_client.create_subscriber(
        SubscriberCreate(
            imsi="901700000000002",
            k="465B5CE8B199B49FAA5F0A2EE238A6BC",
            opc="E8ED289DEBA952E4283B54E88E6183CA",
            dnn="ims",
            sst=2,
        )
    )

    subs = mongo_client.list_subscribers()
    assert len(subs) == 2
    imsis = {s.imsi for s in subs}
    assert imsis == {"901700000000001", "901700000000002"}


def test_subscriber_create_validates_imsi_format():
    with pytest.raises(ValueError):
        SubscriberCreate(imsi="123", k="465B5CE8B199B49FAA5F0A2EE238A6BC", opc="465B5CE8B199B49FAA5F0A2EE238A6BC")


def test_subscriber_create_validates_key_format():
    with pytest.raises(ValueError):
        SubscriberCreate(imsi="901700000000001", k="no-es-hexadecimal", opc="465B5CE8B199B49FAA5F0A2EE238A6BC")
