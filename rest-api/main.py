from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
import get_routes
import post_routes
import bullshit
import uvicorn
import os
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from limiter_inst import limiter
import auth_routes

API_KEY = "secret"
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: invalid API key")
    return api_key

app = FastAPI(title="This is an API",docs_url=None,redoc_url=None,openapi_url="/openapi.json")

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.include_router(post_routes.router)
app.include_router(get_routes.router)
app.include_router(auth_routes.router, prefix="/auth",tags=["auth"])

try:
    bullshit.stupid_test()
except Exception:
    pass

@app.get("/health")
def main():
    return {"Server": "ok"}

@app.get("/docs", include_in_schema=False)
def custom_docs(_: str = Depends(require_api_key)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Protected Swagger UI"
    )

@app.get("/redoc", include_in_schema=False)
def custom_redoc(_: str = Depends(require_api_key)):
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="Protected ReDoc"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", 8000)))
