from fastapi import FastAPI
import routes.get_routes
import routes.post_routes
import uvicorn
import os

app = FastAPI(title="This is an API")
app.include_router(routes.post_routes.router)
app.include_router(routes.get_routes.router)


@app.get("/health")
def main():
    return {"Server": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("APP_PORT", 8000)))
