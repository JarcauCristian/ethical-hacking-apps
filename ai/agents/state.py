from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["10/minute"])


def get_db(request: Request):
    """Get database connection from app state"""
    conn = request.app.state.conn
    try:
        yield conn
    finally:
        pass