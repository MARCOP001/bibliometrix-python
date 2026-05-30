"""Extract raw bibliographic records from files before standardization."""

from __future__ import annotations

import os
import tempfile
import zipfile

import pandas as pd
from bibtexparser.bparser import BibTexParser

from .parsers import parse_cochrane_data, parse_pubmed_medline_text, parse_wos_data


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".txt", ".ciw", ".bib"}


def _annotate_records(records: list[dict], file_extension: str, source: str) -> list[dict]:
    """Attach source metadata used by the transformation dispatcher."""
    for record in records:
        record["_bibliometrix_file_type"] = file_extension
        record["_bibliometrix_source"] = source
    return records


def _read_tabular_file(file_path: str, file_extension: str, source_upper: str) -> list[dict]:
    skiprows = 1 if source_upper == "DIMENSIONS" else 0

    if file_extension == ".csv":
        df = pd.read_csv(
            file_path,
            dtype=str,
            skiprows=skiprows,
            on_bad_lines="skip",
            encoding="utf-8",
        )
    else:
        df = pd.read_excel(file_path, dtype=str, skiprows=skiprows)

    return df.fillna("").to_dict(orient="records")


def _read_bibtex_file(file_path: str) -> list[dict]:
    with open(file_path, "r", encoding="utf-8") as file:
        parser = BibTexParser()
        return parser.parse_file(file).entries


def _extract_zip_file(file_path: str, source_upper: str) -> list[dict]:
    all_records: list[dict] = []
    with zipfile.ZipFile(file_path, "r") as archive:
        with tempfile.TemporaryDirectory() as tmp_dir:
            archive.extractall(tmp_dir)
            for root, _, files in os.walk(tmp_dir):
                for filename in files:
                    nested_path = os.path.join(root, filename)
                    nested_ext = os.path.splitext(filename)[1].lower()
                    if nested_ext in SUPPORTED_EXTENSIONS:
                        all_records.extend(extract_from_file(nested_path, source_upper))
    return all_records


def extract_from_file(file_path: str, source: str) -> list[dict]:
    """Read one raw bibliographic export and return a list of record dicts.

    The function is intentionally limited to the extraction phase: it never
    renames columns or enforces the WoS schema.  That work is delegated to
    ``standardizer.convert2df``.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Il file '{file_path}' non esiste.")

    source_upper = source.upper().strip()
    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == ".zip":
        return _extract_zip_file(file_path, source_upper)

    if file_extension == ".bib":
        print(f"[{source_upper}] Lettura file BibTeX: {file_path}")
        records = _read_bibtex_file(file_path)
        return _annotate_records(records, file_extension, source_upper)

    if file_extension in {".txt", ".ciw"}:
        print(f"[{source_upper}] Lettura file testuale: {file_path}")

        if source_upper == "PUBMED":
            with open(file_path, "r", encoding="utf-8") as file:
                records = parse_pubmed_medline_text(file.read())
        elif source_upper == "WEB_OF_SCIENCE":
            records = parse_wos_data(file_path)
        elif source_upper == "COCHRANE":
            records = parse_cochrane_data(file_path)
        else:
            raise ValueError(
                "I file .txt/.ciw sono supportati solo per PUBMED, "
                f"WEB_OF_SCIENCE e COCHRANE. Ricevuto: {source_upper}"
            )

        return _annotate_records(records, file_extension, source_upper)

    if file_extension in {".csv", ".xlsx", ".xls"}:
        print(f"[{source_upper}] Lettura file tabellare {file_extension}: {file_path}")
        try:
            records = _read_tabular_file(file_path, file_extension, source_upper)
        except pd.errors.EmptyDataError:
            print(f"[ERRORE] Il file '{file_path}' e' vuoto.")
            return []
        except Exception as exc:
            print(f"[ERRORE] Impossibile leggere il file tabellare: {exc}")
            return []

        return _annotate_records(records, file_extension, source_upper)

    raise ValueError(
        f"Formato file non supportato: {file_extension}. "
        "Formati accettati: .csv, .xlsx, .xls, .txt, .ciw, .bib, .zip"
    )
