from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import models  # noqa: F401  (регистрирует таблицы)
from .db import Base, engine
from .keitaro import KeitaroError
from .routers import router
from .services.errors import ServiceError

Base.metadata.create_all(engine)

app = FastAPI(title="Keitaro wrapper")
app.include_router(router)


@app.exception_handler(ServiceError)
def service_error(_: Request, exc: ServiceError):
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)


@app.exception_handler(KeitaroError)
def keitaro_error(_: Request, exc: KeitaroError):
    return JSONResponse({"detail": exc.message}, status_code=502)
