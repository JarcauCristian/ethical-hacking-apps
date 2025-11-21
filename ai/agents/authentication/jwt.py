import os
import time
from jose import jwt, JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Depends, Header, HTTPException, Request


_SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123")
_ALGORITHM = "HS256"

security = HTTPBearer()

def create_token(data: dict, expires_in: int):
    payload = data.copy()
    payload["exp"] = int(time.time()) + expires_in
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def _get_user_id_from_token(token: str) -> str:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token format")
        return str(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
def _get_admin_from_token(token: str) -> bool:
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
        admin = payload.get("admin")
        if admin is None:
            raise HTTPException(status_code=401, detail="Invalid token format")
        return admin
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    FastAPI dependency that extracts and validates the bearer token.
    Returns the user UUID as a string.
    """
    return _get_user_id_from_token(credentials.credentials)


def get_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """
    FastAPI dependency that extracts and validates the bearer token.
    Returns the admin True or False.
    """
    if not _get_admin_from_token(credentials.credentials):
        raise HTTPException(status_code=403, detail="You are not allowed here.")
    return True


def get_user_from_header(authorization: str = Header(None)) -> str:
    """
    Alternative dependency that extracts token from Authorization header.
    Returns the user UUID as a string.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    elif authorization.startswith("bearer "):
        token = authorization[7:]
    
    return _get_user_id_from_token(token)


def user_key(request: Request):
    token = request.headers.get("Authorization", "")
    if token.lower().startswith("bearer "):
        token = token[7:]

    try:
        user_id = _get_user_id_from_token(token)
        return f"user:{user_id}"
    except Exception:
        return "anonymous"
