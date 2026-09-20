from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth import authenticate_user, create_access_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    auth_enabled: bool


class AuthStatusResponse(BaseModel):
    auth_enabled: bool


@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    """
    Endpoint público (sin autenticación) para que el frontend sepa, antes
    de mostrar nada, si la autenticación está activada en este backend --
    permite saltar la pantalla de login cuando AUTH_ENABLED=false, en vez
    de mostrarla igualmente y aceptar cualquier credencial (que era el
    comportamiento anterior, funcional pero confuso).
    """
    return AuthStatusResponse(auth_enabled=settings.auth_enabled)


@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Inicio de sesión. Si AUTH_ENABLED=false, sigue emitiendo un token válido
    (por comodidad de uso homogéneo del cliente), pero ningún endpoint lo
    exigirá realmente -- ver app/auth.py::require_auth.
    """
    if settings.auth_enabled and not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    token = create_access_token(subject=form_data.username)
    return TokenResponse(access_token=token, auth_enabled=settings.auth_enabled)
