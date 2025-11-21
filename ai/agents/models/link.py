from pydantic import BaseModel, AnyHttpUrl
from typing import Dict, Optional

class LinkRequest(BaseModel):
    name: str
    url: AnyHttpUrl
    headers: Optional[Dict[str, str]] = None

class LinkResponse(BaseModel):
    name: str
    url: AnyHttpUrl
    tool_count: int
