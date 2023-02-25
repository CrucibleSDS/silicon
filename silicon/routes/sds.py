import asyncio
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial
from io import BytesIO

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile
)
from pydantic import BaseModel
from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from tungsten import SigmaAldrichSdsParser

from silicon.constants import DEBUG, MEILI_INDEX_NAME, S3_BUCKET_NAME, S3_URL
from silicon.models import SafetyDataSheet
from silicon.utils.sds import get_sds_identifiers

router = APIRouter(prefix="/sds")


class CheckoutItem(BaseModel):
    sds_id: int
    weight: float  # grams


def parse_sds(content):
    sds_parser = SigmaAldrichSdsParser()
    parsed_sds = sds_parser.parse_to_ghs_sds(BytesIO(content))
    return json.loads(parsed_sds.dumps())


@router.post("/")
async def upload_sds(request: Request, file: UploadFile) -> Response:
    db = request.state.db
    minio = request.state.minio
    meili = request.state.meili
    loop = asyncio.get_running_loop()

    content = await file.read()

    with ProcessPoolExecutor() as pool:
        run_in_executor = partial(loop.run_in_executor, pool)

        sds_json = await run_in_executor(parse_sds, content)
        product_identifiers = await run_in_executor(get_sds_identifiers, sds_json)

    filename = (
        f"Sigma_Aldrich_{product_identifiers['product_brand']}"
        f"_{product_identifiers['product_number']}.pdf"
    )

    with ThreadPoolExecutor() as pool:
        run_in_executor = partial(loop.run_in_executor, pool)
        await run_in_executor(
            partial(
                minio.put_object,
                S3_BUCKET_NAME,
                filename,
                BytesIO(content),
                length=-1,
                part_size=10 * 1024 * 1024
            )
        )

    pdf_download_url = f"http{'' if DEBUG else 's'}://{S3_URL}/{S3_BUCKET_NAME}/{filename}"
    async with db.begin():
        stmt = insert(SafetyDataSheet) \
            .values(
            data=sds_json,
            pdf_download_url=pdf_download_url,
            **product_identifiers,
        ) \
            .on_conflict_do_update(
            index_elements=[
                SafetyDataSheet.product_name,
                SafetyDataSheet.product_brand,
                SafetyDataSheet.product_number,
                SafetyDataSheet.cas_number,
            ],
            set_={
                "data": sds_json,
                "pdf_download_url": pdf_download_url,
                "signal_word": product_identifiers["signal_word"],
                "hazards": product_identifiers["hazards"],
            },
        ) \
            .returning(literal_column("*"))

        result = await db.execute(stmt)

    sds = result.fetchone()
    await meili.post(
        f"indexes/{MEILI_INDEX_NAME}/documents",
        json={
            "id": sds.id,
            **product_identifiers,
        },
    )

    return dict(sds)


@router.get("/batch")
async def get_batch_sds(request: Request, sds_ids: list[int] = Query()) -> Response:
    db = request.state.db

    async with db.begin():
        stmt = select(SafetyDataSheet).where(SafetyDataSheet.id == func.any(sds_ids))
        result = await db.execute(stmt)

    return [sds["SafetyDataSheet"] for sds in result.fetchall()]


@router.get("/{sds_id}")
async def get_sds(request: Request, sds_id: int) -> Response:
    db = request.state.db

    async with db.begin():
        stmt = select(SafetyDataSheet).where(SafetyDataSheet.id == sds_id)
        result = (await db.execute(stmt)).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="SDS not found")

    return dict(result)
