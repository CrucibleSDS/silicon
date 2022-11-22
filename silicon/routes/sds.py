import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
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
from sqlalchemy import func, insert, literal_column, select
from sqlalchemy.exc import IntegrityError
from tungsten import SigmaAldrichSdsParser

from silicon.constants import DEBUG, MEILI_INDEX_NAME, S3_BUCKET_NAME, S3_URL
from silicon.models import SafetyDataSheet
from silicon.utils.sds import find_product_identifiers

router = APIRouter(prefix="/sds")


@router.post("/")
async def upload_sds(request: Request, file: UploadFile) -> Response:
    db = request.state.db
    minio = request.state.minio
    meili = request.state.meili
    loop = asyncio.get_running_loop()

    sds_parser = SigmaAldrichSdsParser()
    content = await file.read()

    with ThreadPoolExecutor() as pool:
        execute = partial(loop.run_in_executor, pool)

        parsed_sds = await execute(sds_parser.parse_to_ghs_sds, BytesIO(content))
        sds_json = json.loads(await execute(parsed_sds.dumps))
        product_identifiers = await execute(find_product_identifiers, sds_json)

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

            try:
                result = await db.execute(stmt)
            except IntegrityError as e:
                if "UniqueViolationError" in str(e):
                    raise HTTPException(status_code=409, detail="SDS document already exists")
                else:
                    raise

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
