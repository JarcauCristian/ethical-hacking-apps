import os

from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.security.api_key import APIKeyHeader
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
import uvicorn

import routes.auth
import routes.post
import routes.get
from middlewares.logging import RequestLoggerMiddleware
from middlewares.headers import SecurityHeadersMiddleware
from database import init_db
from state import limiter

API_KEY = os.getenv("SECRET_KEY", "supersecretkey123")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden: invalid API key")
    return api_key

app = FastAPI(
    title="This is an API",
    description="API with JWT Bearer Token Authentication",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json"
)

@app.on_event("startup")
def startup_event():
    app.state.conn = init_db()
    app.state.limiter = limiter

@app.on_event("shutdown")
def shutdown_event():
    app.state.conn.close()

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["ethapp.sedimark.work"], 
    allow_credentials=True, 
    allow_methods=["GET", "POST"], 
    allow_headers=["*"], 
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggerMiddleware)

app.include_router(routes.post.router)
app.include_router(routes.get.router)
app.include_router(routes.auth.router, prefix="/auth",tags=["auth"])

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
