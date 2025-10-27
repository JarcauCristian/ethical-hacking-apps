from fastapi.routing import APIRouter
from fastapi import Query, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from file_operations import validate
import base64
import aiofiles
import json
from typing import Optional

router = APIRouter()

def _read_b64_sync(path: str):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

async def _read_b64_async(path: str):
    async with aiofiles.open(path, "rb") as fp:
        bytes = await fp.read()
        return base64.b64encode(bytes).decode()

async def _get_file(path: str = Query(...), mode: Optional[str] = Query("base64")):
    if path is None or str(path).strip() == "":
        raise HTTPException(status_code=400, detail="Path should not be None or empty.")

    try:
        validated_path = validate(path)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to validate path.")

    if (not validated_path.exists()) or (not validated_path.is_file()):
        raise HTTPException(status_code=404, detail="File does not exist or is not a file.")

    m = (mode or "base64").lower()
    if m == "download":
        return FileResponse(path=validated_path.as_posix(), media_type="application/octet-stream", filename=validated_path.name)

    try:
        b64 = await _read_b64_async(str(validated_path))
    except Exception:
        b64 = _read_b64_sync(str(validated_path))

    response = {"path": validated_path.relative_to(validated_path.parent).as_posix(), "content": b64}

    return PlainTextResponse(json.dumps(response), media_type="application/json")

router.get("/file")(_get_file)
