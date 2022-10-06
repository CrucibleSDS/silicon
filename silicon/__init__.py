import logging
from typing import Callable

import asyncpg
from fastapi import APIRouter, FastAPI, Request, Response

from silicon.constants import DATABASE_URL, LogConfig
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
    """Sets up the database connection."""
    app.state.pool = await asyncpg.create_pool(DATABASE_URL)


@app.on_event("shutdown")
async def shutdown() -> None:
    """Closes the database connection."""
    await app.state.pool.close()


@app.middleware("http")
async def setup_request(request: Request, callnext: Callable) -> Response:
    """Gets the database connection for each request."""
    async with app.state.pool.acquire() as conn:
        request.state.conn = conn
        response = await callnext(request)

    request.state.conn = None
    return response
