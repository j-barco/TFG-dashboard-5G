from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_auth
from app.models.management import SubscriberCreate, SubscriberListResponse
from app.services import mongo_client

router = APIRouter(prefix="/subscribers", tags=["gestión: suscriptores"])


@router.get("", response_model=SubscriberListResponse)
async def list_subscribers(_: str = Depends(require_auth)):
    subs = mongo_client.list_subscribers()
    return SubscriberListResponse(subscribers=subs, count=len(subs))


@router.post("", status_code=201)
async def create_subscriber(data: SubscriberCreate, _: str = Depends(require_auth)):
    try:
        mongo_client.create_subscriber(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"detail": f"Suscriptor {data.imsi} creado correctamente"}


@router.delete("/{imsi}")
async def delete_subscriber(imsi: str, _: str = Depends(require_auth)):
    deleted = mongo_client.delete_subscriber(imsi)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No existe ningún suscriptor con IMSI {imsi}")
    return {"detail": f"Suscriptor {imsi} eliminado correctamente"}
