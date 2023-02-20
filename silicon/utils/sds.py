from tungsten import SdsQueryFieldName, SigmaAldrichFieldMapper


def get_sds_identifiers(sds_json: dict) -> dict[str, str | list[str]]:
    field_mapper = SigmaAldrichFieldMapper()
    return {
        "product_name": field_mapper.getField(SdsQueryFieldName.PRODUCT_NAME, sds_json),
        "product_brand": field_mapper.getField(SdsQueryFieldName.PRODUCT_BRAND, sds_json),
        "product_number": field_mapper.getField(SdsQueryFieldName.PRODUCT_NUMBER, sds_json),
        "cas_number": field_mapper.getField(SdsQueryFieldName.CAS_NUMBER, sds_json),
        "hazards": field_mapper.getField(SdsQueryFieldName.PICTOGRAM, sds_json),
    }
