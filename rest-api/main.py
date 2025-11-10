import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import bullshit
import get_routes
from middlewares.logging import RequestLoggerMiddleware
from middlewares.headers import SecurityHeadersMiddleware
import post_routes

app = FastAPI(title="This is an API")

origins = ["ethapp.sedimark.work"] # We should change it to our domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True, 
    allow_methods=["GET", "POST"], 
    allow_headers=["*"], 
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggerMiddleware)

app.include_router(post_routes.router)
app.include_router(get_routes.router)

try:
    bullshit.stupid_test()
except Exception:
    pass

@app.get("/health")
def main():
    return {"Server": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", 8000)))
