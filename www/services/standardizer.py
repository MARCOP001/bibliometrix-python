"""Central transformation step for the Bibliometrix ETL pipeline.

The goal of this module is intentionally simple:
1. receive raw records from ``file_extractor`` or ``api_retriever``;
2. map them to the internal WoS-like schema used by the app;
3. enforce predictable types and null handling;
4. return a DataFrame ready for the dashboard.
"""

from __future__ import annotations

import ast
import re
from typing import Any

import pandas as pd

from . import format_functions as ff
from .validation import validate_dataframe_contract, validate_record_contract


# -----------------------------------------------------------------------------
# 1. Target schema and type contracts
# -----------------------------------------------------------------------------

COLUMN_TYPE_CONTRACTS: dict[str, type] = {
    "DB": str,
    "UT": str,
    "DI": str,
    "PMID": str,
    "TI": str,
    "SO": str,
    "JI": str,
    "PY": str,
    "DT": str,
    "LA": str,
    "RP": str,
    "AB": str,
    "VL": str,
    "IS": str,
    "BP": str,
    "EP": str,
    "SR": str,
    "TC": int,
    "AU": list,
    "AF": list,
    "C1": list,
    "CR": list,
    "DE": list,
    "ID": list,
}

LIST_COLUMNS = {"AU", "AF", "C1", "CR", "DE", "ID"}
CSV_DELIMITER = ";"
NULL_STRINGS = {"", "nan", "none", "null", "na", "n/a"}
INTERNAL_KEYS = {"_bibliometrix_file_type", "_bibliometrix_source"}


def _default(expected_type: type) -> Any:
    """Return a safe default for the requested contract type."""
    if expected_type is list:
        return []
    if expected_type is int:
        return 0
    return ""


def _is_null(value: Any) -> bool:
    """Detect null-like values without breaking on lists or arrays."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in NULL_STRINGS
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_string(value: Any) -> str:
    if _is_null(value):
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _parse_literal_list(value: str) -> list[Any] | None:
    """Parse strings saved by Excel/CSV as "['a', 'b']" when present."""
    stripped = value.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return None
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def _as_list(value: Any) -> list[str]:
    """Convert multi-value fields to list[str], splitting serialized strings."""
    if _is_null(value):
        return []

    if isinstance(value, str):
        parsed = _parse_literal_list(value)
        if parsed is not None:
            return _as_list(parsed)

        text = _clean_string(value)
        if not text:
            return []

        separator = CSV_DELIMITER if CSV_DELIMITER in text else None
        parts = text.split(separator) if separator else [text]
        return [part.strip() for part in parts if part.strip().lower() not in NULL_STRINGS]

    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_as_list(item))
        return values

    text = _clean_string(value)
    return [text] if text else []


def _as_int(value: Any) -> int:
    if isinstance(value, (list, tuple, set)):
        value = next((item for item in value if not _is_null(item)), 0)
    if _is_null(value):
        return 0
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _as_year(value: Any) -> str:
    match = re.search(r"\d{4}", _clean_string(value))
    return match.group(0) if match else ""


def _cast(tag: str, value: Any) -> Any:
    """Cast one value according to the target schema."""
    expected_type = COLUMN_TYPE_CONTRACTS[tag]
    if expected_type is list:
        return _as_list(value)
    if expected_type is int:
        return _as_int(value)
    if tag == "PY":
        return _as_year(value)
    return _clean_string(value)


def _empty_record(db: str) -> dict[str, Any]:
    record = {tag: _default(contract) for tag, contract in COLUMN_TYPE_CONTRACTS.items()}
    record["DB"] = db
    return record


# -----------------------------------------------------------------------------
# 2. Bridge to the existing format_functions.py
# -----------------------------------------------------------------------------

FORMAT_FUNCTIONS_MAP = {
    "AB": ff.format_ab_column,
    "AF": ff.format_af_column,
    "AU": ff.format_au_column,
    "BP": ff.format_bp_column,
    "C1": ff.format_c1_column,
    "CR": ff.format_cr_column,
    "DE": ff.format_de_column,
    "DI": ff.format_di_column,
    "DT": ff.format_dt_column,
    "EP": ff.format_ep_column,
    "IS": ff.format_is_column,
    "JI": ff.format_ji_column,
    "ID": ff.format_id_column,
    "LA": ff.format_la_column,
    "PMID": ff.format_pmid_column,
    "PY": ff.format_py_column,
    "RP": ff.format_rp_column,
    "SO": ff.format_so_column,
    "TC": ff.format_tc_column,
    "TI": ff.format_ti_column,
    "UT": ff.format_ut_column,
    "VL": ff.format_vl_column,
    "SR": ff.format_sr_column,
}

SOURCE_NAME_MAP = {
    "WEB_OF_SCIENCE": "Web_of_Science",
    "SCOPUS": "Scopus",
    "PUBMED": "PubMed",
    "DIMENSIONS": "Dimensions",
    "LENS": "The_Lens",
    "THE_LENS": "The_Lens",
    "COCHRANE": "Cochrane",
}


def _effective_file_type(raw_record: dict[str, Any], source: str, file_type: str) -> str:
    """Prefer file metadata added by file_extractor, then normalize extensions."""
    effective = str(raw_record.get("_bibliometrix_file_type") or file_type or "").lower().strip()
    if effective and effective != "api" and not effective.startswith("."):
        effective = f".{effective}"

    # PubMed API records are parsed into Medline-like keys, so the text formatter works.
    if source == "PUBMED" and effective in {"api", ".xml", "xml", ""}:
        return ".txt"
    return effective


def _prepare_for_formatters(raw_record: dict[str, Any], source: str) -> dict[str, Any]:
    """Small adapter for the older format_functions expectations."""
    prepared = {k: v for k, v in raw_record.items() if k not in INTERNAL_KEYS}

    if source == "PUBMED":
        for key, value in list(prepared.items()):
            if isinstance(value, (list, tuple, set)):
                prepared[key] = CSV_DELIMITER.join(_as_list(value))
        if "MH" not in prepared and "OT" in prepared:
            prepared["MH"] = prepared["OT"]

    return prepared


def _build_sr(record: dict[str, Any]) -> str:
    """Fallback short reference: FirstAuthor, Year, Source."""
    first_author = record["AU"][0] if record["AU"] else ""
    return ", ".join(part for part in [first_author, record["PY"], record["SO"]] if part)


def _finalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Apply common derived/cleanup fields after source-specific mapping."""
    if record["SO"]:
        record["SO"] = record["SO"].upper()
    if not record["JI"] and record["SO"]:
        record["JI"] = record["SO"]
    if not record["SR"]:
        record["SR"] = _build_sr(record)
    return record


def transform_with_format_functions(
    raw_record: dict[str, Any], source: str, file_type: str
) -> dict[str, Any]:
    """Map records supported by the existing format_functions module."""
    record = _empty_record(source)
    formatter_source = SOURCE_NAME_MAP.get(source, source)
    prepared = _prepare_for_formatters(raw_record, source)

    for tag, formatter in FORMAT_FUNCTIONS_MAP.items():
        try:
            value = formatter(prepared, formatter_source, file_type)
        except Exception:
            value = None
        record[tag] = _cast(tag, value)

    return _finalize_record(record)


# -----------------------------------------------------------------------------
# 3. OpenAlex mapping, because it is not covered by format_functions.py
# -----------------------------------------------------------------------------

def _openalex_source(raw_record: dict[str, Any]) -> str:
    location = raw_record.get("primary_location") or {}
    source = location.get("source") or raw_record.get("host_venue") or {}
    if isinstance(source, dict):
        return _clean_string(source.get("display_name"))
    return _clean_string(source)


def _openalex_authors_and_affiliations(raw_record: dict[str, Any]) -> tuple[list[str], list[str]]:
    authors: list[str] = []
    affiliations: list[str] = []

    for authorship in raw_record.get("authorships", []) or []:
        author_name = _clean_string((authorship.get("author") or {}).get("display_name"))
        if author_name:
            authors.append(author_name)

        for institution in authorship.get("institutions", []) or []:
            name = _clean_string(institution.get("display_name"))
            if name and name not in affiliations:
                affiliations.append(name)

    return authors, affiliations


def _openalex_abstract(raw_record: dict[str, Any]) -> str:
    inverted_index = raw_record.get("abstract_inverted_index")
    if not isinstance(inverted_index, dict):
        return ""

    words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for position in positions or []:
            words.append((int(position), str(word)))
    return " ".join(word for _, word in sorted(words))


def transform_openalex_record(raw_record: dict[str, Any]) -> dict[str, Any]:
    """Map one OpenAlex API/JSON record to the target schema."""
    record = _empty_record("OPENALEX")
    biblio = raw_record.get("biblio") or {}
    ids = raw_record.get("ids") or {}
    authors, affiliations = _openalex_authors_and_affiliations(raw_record)
    source_name = _openalex_source(raw_record)
    concepts = raw_record.get("concepts") or raw_record.get("keywords") or []
    keywords = [
        _clean_string(item.get("display_name") or item.get("keyword"))
        for item in concepts
        if isinstance(item, dict)
    ]

    values = {
        "UT": raw_record.get("id"),
        "DI": raw_record.get("doi"),
        "PMID": ids.get("pmid"),
        "TI": raw_record.get("display_name") or raw_record.get("title"),
        "SO": source_name,
        "JI": source_name,
        "PY": raw_record.get("publication_year"),
        "DT": raw_record.get("type"),
        "LA": raw_record.get("language"),
        "TC": raw_record.get("cited_by_count"),
        "AB": _openalex_abstract(raw_record),
        "VL": biblio.get("volume"),
        "IS": biblio.get("issue"),
        "BP": biblio.get("first_page"),
        "EP": biblio.get("last_page"),
        "AU": authors,
        "AF": authors,
        "C1": affiliations,
        "CR": raw_record.get("referenced_works"),
        "DE": keywords,
        "ID": keywords,
    }

    for tag, value in values.items():
        record[tag] = _cast(tag, value)

    return _finalize_record(record)


# -----------------------------------------------------------------------------
# 4. Already standardized XLSX/CSV rows
# -----------------------------------------------------------------------------

def _looks_standardized(raw_record: dict[str, Any]) -> bool:
    target_columns = set(COLUMN_TYPE_CONTRACTS)
    return "SR" in raw_record and len(target_columns.intersection(raw_record)) >= 10


def transform_standardized_record(raw_record: dict[str, Any], default_db: str) -> dict[str, Any]:
    """Re-load rows previously exported from this standardized schema."""
    record = _empty_record(default_db)
    for tag in COLUMN_TYPE_CONTRACTS:
        record[tag] = _cast(tag, raw_record.get(tag, record[tag]))
    return _finalize_record(record)


def serialize_for_csv(record: dict[str, Any]) -> dict[str, Any]:
    """Flatten list columns using the internal semicolon delimiter."""
    return {
        tag: CSV_DELIMITER.join(value) if isinstance(value, list) else value
        for tag, value in record.items()
    }


# -----------------------------------------------------------------------------
# 5. Public entry point
# -----------------------------------------------------------------------------

def convert2df(
    raw_records: list[dict[str, Any]],
    source: str = "OPENALEX",
    file_type: str = ".csv",
    validate: bool = True,
    for_csv_export: bool = False,
) -> pd.DataFrame:
    """Convert raw records into the standardized Bibliometrix DataFrame."""
    source = source.upper().strip()
    records: list[dict[str, Any]] = []

    for raw_record in raw_records or []:
        if not isinstance(raw_record, dict):
            continue

        record_source = str(raw_record.get("_bibliometrix_source", source)).upper().strip()
        effective_file_type = _effective_file_type(raw_record, record_source, file_type)

        if _looks_standardized(raw_record):
            record = transform_standardized_record(raw_record, default_db=record_source)
        elif record_source == "OPENALEX":
            record = transform_openalex_record(raw_record)
        else:
            record = transform_with_format_functions(raw_record, record_source, effective_file_type)

        if validate:
            validate_record_contract(record, COLUMN_TYPE_CONTRACTS)

        records.append(serialize_for_csv(record) if for_csv_export else record)

    column_order = list(COLUMN_TYPE_CONTRACTS)
    if not records:
        return pd.DataFrame(columns=column_order)

    df = pd.DataFrame(records)
    for tag, expected_type in COLUMN_TYPE_CONTRACTS.items():
        if tag not in df.columns:
            default_value = _default(expected_type)
            df[tag] = [[] for _ in range(len(df))] if expected_type is list else default_value

    df = df[column_order]
    if validate and not for_csv_export:
        validate_dataframe_contract(df, COLUMN_TYPE_CONTRACTS)

    return df
