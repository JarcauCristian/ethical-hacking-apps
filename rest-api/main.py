# main.py

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware
import get_routes
import post_routes
import bullshit
import uvicorn
import os
from logging import RequestLoggerMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Setting mandatory security headers
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
        response.headers['Content-Security-Policy'] = "default-src 'self'; frame-ancestors 'none';"
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response

app = FastAPI(title="This is an API")

origins = ["*"] # We should change it to our domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, 
    allow_credentials=True, 
    allow_methods=["*"], 
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