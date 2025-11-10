from fastapi.routing import APIRouter
from fastapi import UploadFile, File, HTTPException
import aiofiles
import time
from file_operations import safe_file_name, destination, max_size, change, validate

router = APIRouter()
_READ_SIZE = (1 << 16)


@router.post("/file")
async def _save_file(file: UploadFile = File(...)):
    file_name = getattr(file, "filename", None)

    try:
        safe = safe_file_name(file_name)
    except Exception as ex:
        raise HTTPException(status_code=400, detail=ex)

    try:
        dst = validate(safe)
    except ValueError as ex:
        raise HTTPException(status_code=400, detail=ex)

    if dst.exists(): # If destination already exists create a new file with the current time
        stem = dst.stem
        suffix = dst.suffix
        safe = ("%s_%d%s") % (stem, int(time.time()), suffix)
        dst = destination() / safe

    size = 0
    try:
        async with aiofiles.open(dst, "wb") as o:
            while True:
                bytes_read = await file.read(_READ_SIZE)
                if not bytes_read:
                    break

                size += len(bytes_read)
                if size > max_size():
                    try:
                        await o.close()
                    except Exception:
                        pass

                    try:
                        dst.unlink(missing_ok=True)
                    except Exception:
                        pass

                    raise HTTPException(status_code=413, detail="File size is to large.")

                await o.write(bytes_read)
    finally:
        try:
            await file.close()
        except Exception:
            pass

    relative = dst.relative_to(destination()).as_posix()
    return {
        "response": "ok",
        "path": relative,
        "size": size,
        "stripped_path": change(relative)
    }
