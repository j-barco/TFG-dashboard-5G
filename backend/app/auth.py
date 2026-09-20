"""
Autenticación mediante token JWT.

Diseño (ver Metodología, Sección "Seguridad: privilegio mínimo y
autenticación configurable" del TFG):

- La autenticación está ACTIVADA por defecto (fail-safe defaults, Saltzer
  y Schroeder 1975). Se desactiva explícitamente con AUTH_ENABLED=false.
- Cuando está desactivada, se emite un aviso visible en el log de arranque
  (ver app/main.py), para que la circunstancia quede documentada.
- El esquema de usuario es intencionadamente simple (un único administrador,
  sin roles): es proporcionado al alcance de un panel de laboratorio de un
  solo TFG. Una ampliación futura razonable sería pasar a una colección de
  usuarios en MongoDB si el proyecto creciera más allá de este alcance.
"""
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger("dashboard.auth")

# Usado solo para que FastAPI genere el formulario de login en /docs;
# la ruta real de login vive en app/routers/auth.py
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))


def authenticate_user(username: str, password: str) -> bool:
    """Comprueba usuario/contraseña contra las credenciales configuradas."""
    if username != settings.admin_username:
        return False
    return verify_password(password, settings.admin_password_hash)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception


credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o token expirado",
    headers={"WWW-Authenticate": "Bearer"},
)


async def require_auth(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependencia de FastAPI a usar en cualquier endpoint que MODIFIQUE el
    estado del sistema (POST/PUT/DELETE sobre gNB, core o suscriptores).

    Si AUTH_ENABLED=false, se salta la comprobación (devuelve un usuario
    "anónimo" ficticio) -- ver el aviso emitido en el arranque, en main.py.
    """
    if not settings.auth_enabled:
        return "anonymous (auth disabled)"

    if token is None:
        raise credentials_exception

    return _decode_token(token)
