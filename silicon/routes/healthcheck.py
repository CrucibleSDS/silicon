from fastapi import APIRouter, Response

router = APIRouter()


@router.get("/healthcheck")
async def healthcheck() -> Response:
    return {"status": "ok"}
