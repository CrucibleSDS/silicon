import logging
from typing import Callable

import asyncpg
from fastapi import APIRouter, FastAPI, Request, Response
from minio import Minio

from silicon.constants import (DATABASE_URL, DEBUG, S3_ACCESS_KEY,
                               S3_SECRET_KEY, S3_URL, LogConfig)
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
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)
    app.state.minio = Minio(
        S3_URL,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        secure=not DEBUG,
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    """Closes the database connection."""
    await app.state.pool.close()


@app.middleware("http")
async def setup_request(request: Request, callnext: Callable) -> Response:
    """Gets the database connection for each request."""
    request.state.minio = app.state.minio

    async with app.state.pool.acquire() as conn:
        request.state.conn = conn
        response = await callnext(request)

    request.state.conn = None
    return response
