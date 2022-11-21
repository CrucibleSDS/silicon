import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Callable

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from minio import Minio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from silicon.constants import (
    DATABASE_URL,
    DEBUG,
    S3_ACCESS_KEY,
    S3_BUCKET_NAME,
    S3_BUCKET_POLICY,
    S3_SECRET_KEY,
    S3_URL,
    LogConfig
)
from silicon.routes import routers

logging.config.dictConfig(LogConfig().dict())
log = logging.getLogger("silicon")

app = FastAPI(
    docs_url=None,
    redoc_url=None,
)
app_router = APIRouter(prefix="/api/v1")

if DEBUG:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

for router in routers:
    app_router.include_router(router)

app.include_router(app_router)


@app.on_event("startup")
async def start() -> None:
    """Sets up the database connection and minio client."""
    app.state.engine = create_async_engine(DATABASE_URL, echo=True)
    app.state.async_session = sessionmaker(
        app.state.engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    minio = Minio(
        S3_URL,
        access_key=S3_ACCESS_KEY,
        secret_key=S3_SECRET_KEY,
        secure=not DEBUG,
    )
    app.state.minio = minio

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor() as pool:
        execute = partial(loop.run_in_executor, pool)

        if not await execute(minio.bucket_exists, S3_BUCKET_NAME):
            await execute(minio.make_bucket, S3_BUCKET_NAME)
            await execute(minio.set_bucket_policy, S3_BUCKET_NAME, json.dumps(S3_BUCKET_POLICY))


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
