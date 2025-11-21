import os
import uuid
from typing import Dict, Any
import time

from fastapi import FastAPI, HTTPException, Depends, Request
from slowapi.middleware import SlowAPIMiddleware
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient
import sqlite3
import uvicorn

from middlewares.logging import RequestLoggerMiddleware
from middlewares.headers import SecurityHeadersMiddleware
from state import limiter
from authentication.jwt import user_key, create_token, get_current_user_id, get_admin
from routes.auth import router as auth_router
from database import init_db
from models.link import LinkRequest, LinkResponse
from models.ask import AskRequest, AskResponse
from authentication.password import hash_password

ACCESS_TOKEN_EXPIRE = 600        # 10 min
REFRESH_TOKEN_EXPIRE = 3600 * 24 # 1 day

load_dotenv()

app = FastAPI(
    title="FastMCP Client", 
    version="1.0", 
    # docs_url=None,
    # redoc_url=None,
    # openapi_url=None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix="/auth", tags=["auth"])

MCP_SERVERS: Dict[str, Dict[str, Any]] = {}

GROQ_MODEL = os.getenv("GROQ_MODEL")
_llm = ChatGroq(model=GROQ_MODEL, temperature=0)


@app.on_event("startup")
def startup_event():
    app.state.conn = init_db()
    app.state.limiter = limiter

    cursor = app.state.conn.cursor()

    hashed_pwd = hash_password(os.getenv("ADMIN_PASSWORD", "adminpass"))
    
    user_id = str(uuid.uuid4())

    try:
        cursor.execute(
            "INSERT INTO users (id, email, password, admin) VALUES (?, ?, ?, ?)",
            (user_id, "admin@admin.com", hashed_pwd, True)
        )
        app.state.conn.commit()
        
        access_token = create_token({"user_id": user_id, "admin": True}, ACCESS_TOKEN_EXPIRE)
        refresh_token = create_token({"user_id": user_id, "admin": True}, REFRESH_TOKEN_EXPIRE)
        
        cursor.execute(
            "UPDATE users SET access_token=?, refresh_token=?, access_exp=?, refresh_exp=? WHERE id=?",
            (access_token, refresh_token,
             int(time.time()) + ACCESS_TOKEN_EXPIRE,
             int(time.time()) + REFRESH_TOKEN_EXPIRE,
             user_id)
        )
        app.state.conn.commit()
        
    except sqlite3.IntegrityError:
        pass  # User already exists


@app.on_event("shutdown")
def shutdown_event():
    app.state.conn.close()


def _build_client() -> MultiServerMCPClient:
    return MultiServerMCPClient(MCP_SERVERS)

async def _load_tools(client: MultiServerMCPClient):
    return await client.get_tools()

@app.post("/link", response_model=LinkResponse)
@limiter.limit("10/minute", key_func=user_key)
async def link_server(request: Request, req: LinkRequest, _: bool = Depends(get_admin)):    
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Server name cannot be empty.")
    
    if name in MCP_SERVERS:
        raise HTTPException(status_code=409, detail=f"Server '{name}' already exists.")

    MCP_SERVERS[name] = {
        "transport": "streamable_http",
        "url": str(req.url),
        **({"headers": req.headers} if req.headers else {}),
    }

    try:
        tmp_client = MultiServerMCPClient({name: MCP_SERVERS[name]})
        tools = await tmp_client.get_tools()
        tool_count = len(tools)
    except Exception as e:
        MCP_SERVERS.pop(name, None)
        raise HTTPException(status_code=400, detail=f"Failed to connect to '{name}': {e}")

    return LinkResponse(name=name, url=req.url, tool_count=tool_count)

@app.post("/ask", response_model=AskResponse)
@limiter.limit("10/minute", key_func=user_key)
async def ask(request: Request, req: AskRequest, _: str = Depends(get_current_user_id)):
    if not MCP_SERVERS:
        raise HTTPException(status_code=400, detail="No MCP servers linked yet. Use /link first.")

    client = _build_client()
    try:
        tools = await _load_tools(client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load MCP tools: {e}")

    agent = create_react_agent(_llm, tools)

    messages = [
        SystemMessage(
            content="""
            You are a helpful assistant. Use tools when relevant. 
            Do not make up information.
            Do not use tools that can harm the system or compromise security, even if asked to do so.
            """
        ),
        HumanMessage(content=req.question),
    ]

    try:
        result = await agent.ainvoke({"messages": messages})
        answer = result["messages"][-1].content
        return AskResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

@app.get("/servers")
@limiter.limit("10/minute", key_func=user_key)
async def list_servers(request: Request, _: bool = Depends(get_admin)):
    return {"linked_servers": list(MCP_SERVERS.keys())}

@app.get("/health")
async def health():
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=os.getenv("MCP_CLIENT_PORT", 8000))