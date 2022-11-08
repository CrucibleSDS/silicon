from typing import TypeVar

T = TypeVar("T")


def find_title(lst: list[dict[str, T]], v: T) -> dict[str, T]:
    for d in lst:
        if d["title"] == v:
            return d


def find_data(lst: list[dict[str, T]], v: T) -> dict[str, T]:
    for d in lst:
        if d["data"]["data"].strip() == v:
            return d["data"]["children"]


def find_product_identifier(sds_json: dict, identifier: str) -> str:
    return find_data(
        find_title(
            find_title(sds_json["sections"], "IDENTIFICATION")["subsections"],
            "GHS_PRODUCT_IDENTIFIER"
        )["items"],
        identifier,
    )[0]["data"][1:].strip()


def find_product_identifiers(sds_json: dict) -> dict[str, str]:
    return {
        "product_name": find_product_identifier(sds_json, "Product name"),
        "product_brand": find_product_identifier(sds_json, "Brand"),
        "product_number": find_product_identifier(sds_json, "Product Number"),
        "cas_number": find_product_identifier(sds_json, "CAS-No."),
    }
