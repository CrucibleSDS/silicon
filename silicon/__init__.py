import logging
from typing import Callable

from fastapi import APIRouter, FastAPI, Request, Response
from minio import Minio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from silicon.constants import (
    DATABASE_URL,
    DEBUG,
    S3_ACCESS_KEY,
    S3_SECRET_KEY,
    S3_URL,
    LogConfig,
)
from silicon.routes import routers

logging.config.dictConfig(LogConfig().dict())
log = logging.getLogger("silicon")

app = FastAPI(
    docs_url=None,
    redoc_url=None,
)
app_router = APIRouter(prefix="/v1")

for router in routers:
    app_router.include_router(router)

app.include_router(app_router)


@app.on_event("startup")
async def start() -> None:
    """Sets up the database connection and minio client."""
    app.state.engine = create_async_engine(DATABASE_URL, echo=True)
    app.state.async_session = sessionmaker(app.state.engine, expire_on_commit=False, class_=AsyncSession)

    app.state.minio = Minio(
        S3_URL,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        secure=not DEBUG,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    """Closes the database connections."""
    await app.state.engine.dispose()


@app.middleware("http")
async def setup_request(request: Request, callnext: Callable) -> Response:
    """Gets the database connection for each request."""
    request.state.minio = app.state.minio

    async with app.state.async_session() as session:
        request.state.db = session
        response = await callnext(request)

    request.state.db = None
    return response
