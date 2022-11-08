import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from io import BytesIO

from fastapi import APIRouter, Request, Response, UploadFile
from sqlalchemy import insert, literal_column
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
