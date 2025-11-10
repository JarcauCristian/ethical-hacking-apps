from fastapi import FastAPI, Request
from fastapi.security import HTTPBearer
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware
import uvicorn

import os

import routes.auth
import routes.post
import routes.get
from middlewares.logging import RequestLoggerMiddleware
from middlewares.headers import SecurityHeadersMiddleware
from database import init_db
from state import limiter

app = FastAPI(
    title="This is an API",
    description="API with JWT Bearer Token Authentication",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
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

app.include_router(routes.get.router)
app.include_router(routes.post.router)
app.include_router(routes.auth.router, prefix="/auth",tags=["auth"])


@app.get("/health")
def main():
    return {"Server": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", 8000)))
