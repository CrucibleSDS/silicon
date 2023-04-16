import asyncio
import json
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from functools import partial
from io import BytesIO
from typing import List, Literal
from urllib.parse import urljoin

from botocore.handlers import validate_bucket_name
from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile
)
from httpx import AsyncClient
from pydantic import BaseModel, validator
from pylatexenc.latexencode import unicode_to_latex
from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from starlette.responses import StreamingResponse
from tungsten import SigmaAldrichSdsParser
from types_aiobotocore_s3.client import S3Client

from silicon.constants import MEILI_INDEX_NAME, S3_BUCKET_NAME, S3_URL
from silicon.models import SafetyDataSheet
from silicon.utils.cover.templater import (
    HazardStatementOverview,
    PaperType,
    merge_pdf
)
from silicon.utils.sds import get_sds_identifiers

router = APIRouter(prefix="/sds")


class CheckoutItem(BaseModel):
    sds_id: int
    percentage: float

    @classmethod
    @validator('percentage')
    def validate_percentage(cls, percentage):
        if percentage <= 0:
            raise ValueError("Item percentage cannot be less than or equal to 0%")
        if percentage > 100:
            raise ValueError("Item percentage cannot be greater than 100%")
        return percentage


class Checkout(BaseModel):
    product_name: str
    destination: str
    measurement_type: Literal["volume", "weight"]
    certification_date: date
    sensitivity: Literal["sensitive", "confidential", "proprietary", "public"]
    items: List[CheckoutItem]

    @classmethod
    @validator('items')
    def validate_items(cls, items):
        if not len(items):
            raise ValueError("Must submit at least 1 SDS item")
        return items


def parse_sds(content):
    sds_parser = SigmaAldrichSdsParser()
    parsed_sds = sds_parser.parse_to_ghs_sds(BytesIO(content))
    return json.loads(parsed_sds.dumps())


@router.post("/")
async def upload_sds(request: Request, file: UploadFile) -> Response:
    db = request.state.db
    s3: S3Client = request.state.s3
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

    async with s3() as client:
        client: S3Client

        # Disable bucket name validation to support Ceph RGW tenancy
        client.meta.events.unregister("before-parameter-build.s3", validate_bucket_name)

        await client.put_object(
            ACL="public-read",
            Bucket=S3_BUCKET_NAME,
            Body=content,
            Key=filename,
        )

    pdf_download_url = urljoin(S3_URL, f"{S3_BUCKET_NAME}/{filename}")
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
                "statements": product_identifiers["statements"]
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


@router.post("/checkout")
async def post_checkout_sds(request: Request, req_payload: Checkout) -> Response:
    db = request.state.db

    async with db.begin():
        stmt = select(SafetyDataSheet) \
            .where(SafetyDataSheet.id == func.any([item.sds_id for item in req_payload.items]))
        result = await db.execute(stmt)

    db_data: list[SafetyDataSheet] = [sds['SafetyDataSheet'] for sds in result.fetchall()]
    entries: list[dict] = []

    signal_words: set[str] = {sds.signal_word for sds in db_data}

    cent_map = {item.sds_id: item.percentage for item in req_payload.items}
    for sds in db_data:
        entries.append({
            'sds': sds,
            'percentage': cent_map[sds.id],
        })

    all_pictograms: list[str] = [*{hazard for sds in db_data for hazard in sds.hazards}]
    all_statements: list[str] = [overview.name for overview in {
        *HazardStatementOverview.get_statements([*{statement
                                                   for sds in db_data
                                                   for statement in sds.statements}])}]

    templater = request.state.templater

    front_page = templater.generate_pdf({
        'paper': PaperType.A4_PAPER.value,
        'cover_title': "Cover Sheet — U.S. Origin Shipments",
        'sensitivity': req_payload.sensitivity.strip().lower().capitalize(),
        'product_name': req_payload.product_name,
        'destination_country': req_payload.destination,
        'columns': 'L|l|l',
        'headers': [
            "Product Name",
            "CAS No.",
            f"{req_payload.measurement_type.capitalize()} \\%"
        ],
        'signal_word': "DANGER" if "Danger" in signal_words
        else "WARNING" if "Warning" in signal_words else None,
        'rows': [
            [
                unicode_to_latex(entry['sds'].product_name),
                unicode_to_latex(entry['sds'].cas_number),
                f'{entry["percentage"]}\\%',
            ] for entry in entries
        ],
        'pictograms': all_pictograms,
        'hazard_statement_overview': all_statements,
        'signature_date': req_payload.certification_date.strftime('%B %d, %Y'),
    })

    http: AsyncClient = request.state.http
    files = [front_page]
    for sds in db_data:
        response = await http.get(url=sds.pdf_download_url)
        files.append(BytesIO(response.content))
    merged = merge_pdf(files)

    merged.seek(0)

    return StreamingResponse(content=merged, media_type='application/pdf')


@router.get("/{sds_id}")
async def get_sds(request: Request, sds_id: int) -> Response:
    db = request.state.db

    async with db.begin():
        stmt = select(SafetyDataSheet).where(SafetyDataSheet.id == sds_id)
        result = (await db.execute(stmt)).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="SDS not found")

    return dict(result)
