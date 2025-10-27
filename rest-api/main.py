from fastapi import FastAPI
import get_routes
import post_routes
import bullshit
import uvicorn
import os

app = FastAPI(title="This is an API")
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
