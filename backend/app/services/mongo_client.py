"""
CRUD de suscriptores contra la colección 'subscribers' de MongoDB, con el
mismo esquema de documento que emplea el propio Open5GS (WebUI y la
herramienta oficial open5gs-dbctl), para que un suscriptor creado desde
aquí sea indistinguible de uno creado por las vías oficiales.

Referencia del esquema: open5gs/misc/db/open5gs-dbctl (script oficial) y
ejemplos de documentos reales documentados en el propio repositorio de
Open5GS.
"""
from pymongo import MongoClient
from pymongo.collection import Collection

from app.config import settings
from app.models.management import SubscriberCreate, SubscriberSummary

_client: MongoClient | None = None


def _get_collection() -> Collection:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
    return _client[settings.mongo_db]["subscribers"]


def _build_subscriber_document(data: SubscriberCreate) -> dict:
    """Construye el documento con el esquema exacto de Open5GS."""
    return {
        "schema_version": 1,
        "imsi": data.imsi,
        "msisdn": [],
        "imeisv": [],
        "mme_host": [],
        "mme_realm": [],
        "purge_flag": [],
        "security": {
            "k": data.k,
            "op": None,
            "opc": data.opc,
            "amf": data.amf,
            "sqn": 0,
        },
        "ambr": {
            "downlink": {"value": 1, "unit": 3},
            "uplink": {"value": 1, "unit": 3},
        },
        "slice": [
            {
                "sst": data.sst,
                "default_indicator": True,
                "session": [
                    {
                        "name": data.dnn,
                        # type=1 -> IPv4 puro (no IPv4v6, ver Anexo B del
                        # trabajo predecesor sobre problemas con el tipo mixto)
                        "type": 1,
                        "pcc_rule": [],
                        "ambr": {
                            "downlink": {"value": 1, "unit": 3},
                            "uplink": {"value": 1, "unit": 3},
                        },
                        "qos": {
                            "index": 9,
                            "arp": {
                                "priority_level": 8,
                                "pre_emption_capability": 1,
                                "pre_emption_vulnerability": 1,
                            },
                        },
                    }
                ],
            }
        ],
        "access_restriction_data": 32,
        "subscriber_status": 0,
        "network_access_mode": 0,
        "subscribed_rau_tau_timer": 12,
        "__v": 0,
    }


def create_subscriber(data: SubscriberCreate) -> None:
    collection = _get_collection()
    if collection.find_one({"imsi": data.imsi}) is not None:
        raise ValueError(f"Ya existe un suscriptor con IMSI {data.imsi}")
    collection.insert_one(_build_subscriber_document(data))


def delete_subscriber(imsi: str) -> bool:
    """Devuelve True si se eliminó algún documento, False si no existía."""
    collection = _get_collection()
    result = collection.delete_one({"imsi": imsi})
    return result.deleted_count > 0


def list_subscribers() -> list[SubscriberSummary]:
    collection = _get_collection()
    summaries: list[SubscriberSummary] = []
    for doc in collection.find({}):
        slices = doc.get("slice", [])
        sst = slices[0].get("sst", 0) if slices else 0
        sessions = slices[0].get("session", []) if slices else []
        dnn = sessions[0].get("name", "") if sessions else ""
        summaries.append(SubscriberSummary(imsi=doc.get("imsi", ""), dnn=dnn, sst=sst))
    return summaries
