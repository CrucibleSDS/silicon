import asyncio
import logging
from typing import Callable

from aiobotocore.session import get_session
import httpx
from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from silicon.constants import (
    DATABASE_URL,
    DEBUG,
    MEILI_API_KEY,
    MEILI_INDEX_NAME,
    MEILI_SYNC_ON_START,
    MEILI_URL,
    S3_ACCESS_KEY,
    S3_SECRET_KEY,
    S3_URL,
    LogConfig
)
from silicon.models import SafetyDataSheet
from silicon.routes import routers
from silicon.utils.cover.templater import Templater

logging.config.dictConfig(LogConfig().dict())
log = logging.getLogger("silicon")

app = FastAPI(
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
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
    """Sets up the database connection, S3 client, HTTP client, and templater."""
    app.state.engine = create_async_engine(DATABASE_URL, echo=True)
    app.state.async_session = sessionmaker(
        app.state.engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    app.state.meili = httpx.AsyncClient(
        base_url=MEILI_URL,
        headers={"Authorization": f"Bearer {MEILI_API_KEY}"}
    )

    app.state.http = httpx.AsyncClient()

    app.state.templater = Templater()

    boto_session = get_session()

    def s3():
        return boto_session.create_client(
            "s3",
            endpoint_url=S3_URL,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
        )

    app.state.s3 = s3

    async def meili_sync():
        async with app.state.async_session() as session:
            async with session.begin():
                stmt = select([
                    SafetyDataSheet.id,
                    SafetyDataSheet.product_name,
                    SafetyDataSheet.product_number,
                    SafetyDataSheet.product_brand,
                    SafetyDataSheet.cas_number,
                ])

                async for sds in await session.stream(stmt):
                    await app.state.meili.post(
                        f"indexes/{MEILI_INDEX_NAME}/documents",
                        json=dict(sds),
                    )

    if MEILI_SYNC_ON_START:
        asyncio.create_task(meili_sync())


@app.on_event("shutdown")
async def shutdown() -> None:
    """Closes the database connections and HTTP client."""
    await app.state.engine.dispose()
    await app.state.meili.aclose()


@app.middleware("http")
async def setup_request(request: Request, callnext: Callable) -> Response:
    """Gets the database connection, S3 client, HTTP client, and templater for each request."""
    request.state.meili = app.state.meili
    request.state.http = app.state.http
    request.state.s3 = app.state.s3
    request.state.templater = app.state.templater

    async with app.state.async_session() as session:
        request.state.db = session
        response = await callnext(request)

    request.state.db = None
    return response
