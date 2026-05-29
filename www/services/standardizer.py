# =============================================================================
# standardizer.py  —  Phase 2: TRANSFORM – RENAME (Integration with format_functions)
# =============================================================================

from __future__ import annotations
import pandas as pd
from typing import Any

# Importiamo le funzioni di formattazione dal file fornito
from . import format_functions as ff

# -----------------------------------------------------------------------------
# 1.  CONTRATTI DI TIPO E DEFAULT
# -----------------------------------------------------------------------------
COLUMN_TYPE_CONTRACTS: dict[str, type] = {
    "DB":   str, "UT":   str, "DI":   str, "PMID": str,
    "TI":   str, "SO":   str, "JI":   str, "PY":   str,
    "DT":   str, "LA":   str, "RP":   str, "AB":   str,
    "VL":   str, "IS":   str, "BP":   str, "EP":   str,
    "SR":   str, "TC":   int,
    "AU":   list, "AF":   list, "C1":   list,
    "CR":   list, "DE":   list, "ID":   list,
}

_TYPE_DEFAULTS: dict[type, Any] = {str: "", int: 0, list: []}
CSV_DELIMITER: str = ";"

def _get_default_value(expected_type: type) -> Any:
    if expected_type is list:
        return []
    return _TYPE_DEFAULTS.get(expected_type, "")

def _cast_scalar(value: Any, expected_type: type) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return _get_default_value(expected_type)

    if expected_type is int:
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0
    elif expected_type is list:
        return value if isinstance(value, list) else [str(value)]

    return str(value).strip()

# -----------------------------------------------------------------------------
# 2.  INTEGRAZIONE CON FORMAT_FUNCTIONS (Il Bridge)
# -----------------------------------------------------------------------------
# Mappa dei tag WoS alle specifiche funzioni di format_functions.py
FORMAT_FUNCTIONS_MAP = {
    'AB': ff.format_ab_column,
    'AF': ff.format_af_column,
    'AU': ff.format_au_column,
    'BP': ff.format_bp_column,
    'C1': ff.format_c1_column,
    'CR': ff.format_cr_column,
    'DE': ff.format_de_column,
    'DI': ff.format_di_column,
    'DT': ff.format_dt_column,
    'EP': ff.format_ep_column,
    'IS': ff.format_is_column,
    'JI': ff.format_ji_column,
    'ID': ff.format_id_column,
    'LA': ff.format_la_column,
    'PMID': ff.format_pmid_column,
    'PY': ff.format_py_column,
    'RP': ff.format_rp_column,
    'SO': ff.format_so_column,
    'TC': ff.format_tc_column,
    'TI': ff.format_ti_column,
    'UT': ff.format_ut_column,
    'VL': ff.format_vl_column,
    'SR': ff.format_sr_column
}

# Mappatura dei nomi dei DB da uppercase a quelli attesi da format_functions
SOURCE_NAME_MAP = {
    "WEB_OF_SCIENCE": "Web_of_Science",
    "SCOPUS": "Scopus",
    "PUBMED": "PubMed",
    "DIMENSIONS": "Dimensions",
    "LENS": "The_Lens",
    "COCHRANE": "Cochrane"
}

def transform_via_format_functions(raw_record: dict, source_upper: str, file_type: str) -> dict:
    """
    Funzione universale che delega l'estrazione dei campi a format_functions.py 
    e assicura il rispetto dei Type Contracts di standardizer.
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = source_upper
    ff_source_name = SOURCE_NAME_MAP.get(source_upper, source_upper)

    for tag, extract_func in FORMAT_FUNCTIONS_MAP.items():
        try:
            # Invoca la funzione specifica del campo passando i tre parametri richiesti
            raw_value = extract_func(raw_record, ff_source_name, file_type)
        except Exception as e:
            raw_value = None  # Fallback sicuro in caso di KeyError interni
        
        # Cast al tipo atteso (int, str, list) per evitare disallineamenti
        standardized[tag] = _cast_scalar(raw_value, COLUMN_TYPE_CONTRACTS[tag])
    
    # Pulizia standard su Nome Rivista (SO)
    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# 3.  LOGICHE RESIDUE (Solo per OpenAlex, non presente in format_functions)
# -----------------------------------------------------------------------------
def clean_scalar_fields_oa(raw_record: dict, mapping_dict: dict) -> dict:
    res = {}
    for oa_key, wos_tag in mapping_dict.items():
        val = raw_record.get(oa_key)
        res[wos_tag] = _cast_scalar(val, COLUMN_TYPE_CONTRACTS[wos_tag])
    return res

def transform_openalex_record(raw_record: dict, file_type: str = "") -> dict:
    # (Mantieni qui la logica di base per OpenAlex JSON originale)
    standardized = {t: _get_default_value(c) for t, c in COLUMN_TYPE_CONTRACTS.items()}
    standardized["DB"] = "OPENALEX"
    
    mapping = {"id": "UT", "doi": "DI", "title": "TI", "publication_year": "PY", "type": "DT", "cited_by_count": "TC"}
    standardized.update(clean_scalar_fields_oa(raw_record, mapping))
    
    # Autori (estrazione semplificata)
    authorships = raw_record.get("authorships", [])
    if authorships:
        standardized["AU"] = [str(a.get("author", {}).get("display_name", "")) for a in authorships]
        standardized["AF"] = standardized["AU"]
        standardized["C1"] = [inst.get("display_name", "") for auth in authorships for inst in auth.get("institutions", [])]
    return standardized

def transform_openalex_csv_record(raw_record: dict, file_type: str = "") -> dict:
    # (Mantieni qui la logica di base per OpenAlex CSV originale)
    standardized = {t: _get_default_value(c) for t, c in COLUMN_TYPE_CONTRACTS.items()}
    standardized["DB"] = "OPENALEX"
    
    mapping = {"id": "UT", "doi": "DI", "title": "TI", "publication_year": "PY", "type": "DT", "cited_by_count": "TC", "host_venue": "SO"}
    standardized.update(clean_scalar_fields_oa(raw_record, mapping))
    
    authors_str = str(raw_record.get("authors", raw_record.get("author_display_names", "")))
    if authors_str:
        sep = ";" if ";" in authors_str else ","
        standardized["AU"] = [a.strip() for a in authors_str.split(sep) if a.strip()]
        standardized["AF"] = standardized["AU"]
    return standardized

# -----------------------------------------------------------------------------
# 4.  VALIDAZIONE E SERIALIZZAZIONE
# -----------------------------------------------------------------------------
class ValidationError(Exception): pass

def validate_record(record: dict) -> None:
    errors = []
    for tag, expected_type in COLUMN_TYPE_CONTRACTS.items():
        if tag not in record:
            errors.append(f"[MISSING_COLUMN] Tag '{tag}' assente.")
            continue
        val = record[tag]
        if not isinstance(val, expected_type):
            errors.append(f"[TYPE_ERROR] Tag '{tag}': atteso {expected_type.__name__}, trovato {type(val).__name__}.")
    if errors:
        raise ValidationError("\n".join(errors))

def serialize_for_csv(record: dict) -> dict:
    return {tag: (CSV_DELIMITER.join(str(i) for i in val) if isinstance(val, list) else val) for tag, val in record.items()}

# -----------------------------------------------------------------------------
# 5.  ENTRY POINT PRINCIPALE
# -----------------------------------------------------------------------------
def convert2df(
    raw_records: list[dict],
    source: str = "OPENALEX",
    file_type: str = ".csv", # Aggiunto parametro per format_functions
    validate: bool = True,
    for_csv_export: bool = False,
) -> pd.DataFrame:
    """
    Trasforma una lista di record grezzi in un DataFrame standardizzato.
    """
    # --- SONDE DI DEBUG (da rimuovere una volta risolto) ---
    print("\n" + "="*40)
    print("🎯 DEBUG CONVERT2DF CHIAMATO!")
    print(f"🔹 Source ricevuta: '{source}'")
    print(f"🔹 File type ricevuto: '{file_type}'")
    print(f"🔹 Tipo di raw_records: {type(raw_records)}")
    
    if isinstance(raw_records, list):
        print(f"🔹 Numero di record: {len(raw_records)}")
        if len(raw_records) > 0:
            print(f"🔹 Chiavi del primo record: {list(raw_records[0].keys())[:5]}...")
    else:
        print("⚠️ ERRORE: raw_records NON è una lista!")
    print("="*40 + "\n")
    # -------------------------------------------------------
    
    source_upper = source.upper()

    # Routing dinamico per OpenAlex vs Format Functions
    if source_upper == "OPENALEX" and raw_records:
        first_record = raw_records[0]
        if "authorships" not in first_record and ("author_display_names" in first_record or "publication_year" in first_record):
            source_upper = "OPENALEX_CSV"

    standardized_records: list[dict] = []
    
    for idx, raw in enumerate(raw_records):
        try:
            # Logica di Routing
            if source_upper == "OPENALEX":
                record = transform_openalex_record(raw, file_type)
            elif source_upper == "OPENALEX_CSV":
                record = transform_openalex_csv_record(raw, file_type)
            else:
                # Per Scopus, WoS, PubMed, Dimensions, Cochrane e Lens usa il Bridge
                record = transform_via_format_functions(raw, source_upper, file_type)
        except Exception as exc:
            print(f"[ERROR] Trasformazione fallita per il record {idx}: {exc}")
            continue

        if validate:
            try:
                validate_record(record)
            except ValidationError as ve:
                print(f"[WARN] Validazione fallita per il record {idx}:\n{ve}")

        if for_csv_export:
            record = serialize_for_csv(record)

        standardized_records.append(record)

    column_order = list(COLUMN_TYPE_CONTRACTS.keys())
    if not standardized_records:
        return pd.DataFrame(columns=column_order)

    df = pd.DataFrame(standardized_records)

    # Assicuriamo che tutte le colonne siano presenti
    for col in column_order:
        if col not in df.columns:
            if for_csv_export:
                df[col] = ""
            else:
                default_val = _TYPE_DEFAULTS[COLUMN_TYPE_CONTRACTS[col]]
                df[col] = [[] for _ in range(len(df))] if isinstance(default_val, list) else default_val

    return df[column_order]