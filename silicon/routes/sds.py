import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from sqlalchemy import insert, literal_column, select
from tungsten import SigmaAldrichSdsParser

from silicon.constants import DEBUG, S3_BUCKET_NAME, S3_BUCKET_POLICY, S3_URL
from silicon.models import SafetyDataSheet
from silicon.utils.sds import find_product_identifiers

router = APIRouter(prefix="/sds")


@router.post("/")
async def upload_sds(request: Request, file: UploadFile) -> Response:
    db = request.state.db
    minio = request.state.minio
    loop = asyncio.get_running_loop()

    sds_parser = SigmaAldrichSdsParser()
    content = await file.read()

    with ThreadPoolExecutor() as pool:
        execute = partial(loop.run_in_executor, pool)

        parsed_sds = await execute(sds_parser.parse_to_ghs_sds, BytesIO(content))
        sds_json = json.loads(await execute(parsed_sds.dumps))
        product_identifiers = await execute(find_product_identifiers, sds_json)

        if not await execute(minio.bucket_exists, S3_BUCKET_NAME):
            await execute(minio.make_bucket, S3_BUCKET_NAME)
            await execute(minio.set_bucket_policy, S3_BUCKET_NAME, json.dumps(S3_BUCKET_POLICY))

        filename = (
            f"Sigma_Aldrich_{product_identifiers['product_brand']}"
            f"_{product_identifiers['product_number']}.pdf"
        )
        await execute(
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
                .returning(literal_column("*"))

            result = await db.execute(stmt)

        return dict(result.fetchone())


@router.get("/search")
async def search_sds(
    request: Request,
    product_name: Optional[str] = None,
    product_number: Optional[str] = None,
    cas_number: Optional[str] = None,
) -> Response:
    db = request.state.db

    if product_name:
        stmt = select(SafetyDataSheet) \
            .where(SafetyDataSheet.product_name.ilike(f"{product_name}%"))
    elif product_number:
        stmt = select(SafetyDataSheet) \
            .where(SafetyDataSheet.product_number.ilike(f"{product_number}%"))
    elif cas_number:
        stmt = select(SafetyDataSheet) \
            .where(SafetyDataSheet.cas_number.startswith(f"{cas_number}%"))
    else:
        raise HTTPException(status_code=422, detail="Missing search query")

    async with db.begin():
        result = (await db.execute(stmt)).fetchall()

    return list(sds["SafetyDataSheet"] for sds in result)


@router.get("/{sds_id}")
async def get_sds(request: Request, sds_id: int) -> Response:
    db = request.state.db

    async with db.begin():
        stmt = select(SafetyDataSheet).where(SafetyDataSheet.id == sds_id)
        result = (await db.execute(stmt)).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="SDS not found")

    return dict(result)
