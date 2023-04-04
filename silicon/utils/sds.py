from tungsten import SdsQueryFieldName, SigmaAldrichFieldMapper


def get_sds_identifiers(sds_json: dict) -> dict[str, str | list[str]]:
    field_mapper = SigmaAldrichFieldMapper()
    return {
        "product_name": field_mapper.get_field(SdsQueryFieldName.PRODUCT_NAME, sds_json),
        "product_brand": field_mapper.get_field(SdsQueryFieldName.PRODUCT_BRAND, sds_json),
        "product_number": field_mapper.get_field(SdsQueryFieldName.PRODUCT_NUMBER, sds_json),
        "cas_number": field_mapper.get_field(SdsQueryFieldName.CAS_NUMBER, sds_json),
        "signal_word": field_mapper.get_field(SdsQueryFieldName.SIGNAL_WORD, sds_json),
        "hazards": field_mapper.get_field(SdsQueryFieldName.PICTOGRAM, sds_json),
        "statements": field_mapper.get_field(SdsQueryFieldName.STATEMENTS, sds_json),
    }
