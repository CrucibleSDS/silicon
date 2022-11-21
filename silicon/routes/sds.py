import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, insert, literal_column, select
from sqlalchemy.exc import IntegrityError
from tungsten import SigmaAldrichSdsParser

from silicon.constants import DEBUG, S3_BUCKET_NAME, S3_URL
from silicon.models import SafetyDataSheet
from silicon.utils.sds import find_product_identifiers

router = APIRouter(prefix="/sds")

CAS_NUMBER_RE = re.compile(r"^(\d{1,6}(?:-|(?:-\d{1,2}(?:-|(?:-\d))?)?))$")
PRODUCT_NUMBER_PARTIAL_RE = re.compile(r"^(\d+)$")


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

        return dict(result.fetchone())


@router.get("/search")
async def search_sds(request: Request, query: str) -> Response:
    db = request.state.db
    query = query.lower()

    if CAS_NUMBER_RE.fullmatch(query):
        if PRODUCT_NUMBER_PARTIAL_RE.fullmatch(query):
            stmt = select(SafetyDataSheet) \
                .where(
                    SafetyDataSheet.product_number.startswith(query)
                    | SafetyDataSheet.cas_number.startswith(query)
                )
        else:
            stmt = select(SafetyDataSheet) \
                .where(SafetyDataSheet.cas_number.startswith(query))
    elif " " in query:
        stmt = select(SafetyDataSheet) \
            .where(func.lower(SafetyDataSheet.product_name).contains(query))
    else:
        stmt = select(SafetyDataSheet) \
            .where(
                func.lower(SafetyDataSheet.product_name).contains(query)
                | func.lower(SafetyDataSheet.product_number).startswith(query)
            )

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
