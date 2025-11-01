from fastapi import FastAPI, Request
import routes.get_routes
import routes.post_routes
import uvicorn
import os
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from limiter_inst import limiter

app = FastAPI(title="This is an API")
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.include_router(routes.get_routes.router)
app.include_router(routes.post_routes.router)


@app.get("/health")
def main():
    return {"Server": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", 8000)))
