import logging
import time
from logging.handlers import TimedRotatingFileHandler
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

BASE_LOG_FILE = "api_requests.log"
logger = logging.getLogger("ethical_logger")
logger.setLevel(logging.INFO)

LOG_FORMAT = logging.Formatter(
    "|%(asctime)s|%(levelname)s|Method=%(method)s Path=%(path)s Status=%(status)s Time=%(time).4fs Client=%(client)s|"
)

file_handler = TimedRotatingFileHandler(BASE_LOG_FILE, when="D", interval=1, backupCount=7, encoding="utf-8")
file_handler.setFormatter(LOG_FORMAT)

if logger.hasHandlers():
    logger.handlers.clear()
logger.addHandler(file_handler)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response: Response = await call_next(request)
        process_time = time.time() - start_time

        extra = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "time": process_time,
            "client": request.client.host if request.client else "unknown",
        }

        if response.status_code >= 500:
            logger.error("Request failed (Server Error)", extra=extra)
        elif response.status_code >= 400:
            logger.warning("Request failed (Client Error)", extra=extra)
        else:
            logger.info("Request successful", extra=extra)

        return response
