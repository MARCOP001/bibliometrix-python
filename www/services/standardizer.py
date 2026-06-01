"""
Fase di trasformazione per la pipeline ETL di Bibliometrix.

L'obiettivo di questo modulo è volutamente semplice:
1. ricevere record grezzi da "file_extractor" o "api_retriever";
2. mapparli allo schema interno simile a WoS utilizzato dall'applicazione;
3. imporre tipi prevedibili e gestione dei valori nulli;
4. restituire un DataFrame pronto per la dashboard.

"""

from __future__ import annotations
import ast
import re
from typing import Any
import pandas as pd
from . import format_functions as ff
from .validation import validate_dataframe_contract, validate_record_contract

# Schema Target e contratti di tipo
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
    """Restituisce il valore predefinito coerente con il contratto di tipo.

    Args:
        expected_type: Tipo Python atteso per una colonna dello schema standardizzato.

    Returns:
        Valore di fallback compatibile con "expected_type": lista vuota per "list", zero per "int" e stringa vuota per gli altri tipi scalari.

    Notes:
        La funzione non solleva eccezioni per tipi non previsti: ogni tipo non gestito esplicitamente viene trattato come campo testuale.
    """
    if expected_type is list:
        return []
    if expected_type is int:
        return 0
    return ""


def _is_null(value: Any) -> bool:
    """Verifica se un valore rappresenta un nullo nella pipeline ETL.

    Args:
        value: Valore grezzo da controllare, proveniente da API, file tabellari o parser testuali.

    Returns:
        "True" se il valore e' "None", una stringa equivalente a nullo o un valore riconosciuto come mancante da pandas; "False" altrimenti.

    Notes:
        Le eccezioni prodotte da "pd.isna" su oggetti non scalari vengono intercettate per evitare falsi errori durante la normalizzazione.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in NULL_STRINGS
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _clean_string(value: Any) -> str:
    """Normalizza un valore in una stringa pulita e priva di ritorni a capo.

    Args:
        value: Valore da convertire in stringa.

    Returns:
        Stringa senza spazi esterni e con caratteri di nuova riga sostituiti da spazi. Restituisce stringa vuota per valori null-like.

    Notes:
        La funzione conserva il contenuto testuale ma rende i campi sicuri per DataFrame, CSV e visualizzazione nel dashboard.
    """
    if _is_null(value):
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def _parse_literal_list(value: str) -> list[Any] | None:
    """Interpreta una lista serializzata come stringa Python, se presente.

    Args:
        value: Stringa da analizzare, tipicamente letta da CSV o Excel.

    Returns:
        Lista Python se "value" contiene una rappresentazione letterale valida di lista; "None" se il formato non e' una lista o se il parsing fallisce.

    Notes:
        Usa "ast.literal_eval" per evitare l'esecuzione di codice arbitrario. Errori di sintassi o valori non supportati vengono gestiti restituendo "None".
    """
    stripped = value.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return None
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, list) else None


def _as_list(value: Any) -> list[str]:
    """Converte campi multivalore in una lista di stringhe normalizzate.

    Args:
        value: Valore grezzo da convertire. Puo' essere nullo, stringa, lista, tupla, set o altro valore scalare.

    Returns:
        Lista di stringhe non vuote. Le stringhe serializzate come liste vengono deserializzate, mentre le stringhe con delimitatore interno vengono divise usando "CSV_DELIMITER".

    Notes:
        Le collezioni annidate vengono appiattite ricorsivamente. I valori null-like vengono esclusi dal risultato.
    """
    if _is_null(value):
        return []

    if isinstance(value, str):
        # Alcuni export ricaricati da CSV salvano le liste come testo Python.
        parsed = _parse_literal_list(value)
        if parsed is not None:
            return _as_list(parsed)

        text = _clean_string(value)
        if not text:
            return []

        # Il delimitatore interno del progetto resta l'unica separazione applicata automaticamente, per non spezzare nomi o titoli validi.
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
    """Converte un valore grezzo in intero compatibile con lo schema.

    Args:
        value: Valore da convertire. Per collezioni viene usato il primo elemento non nullo.

    Returns:
        Intero ottenuto dal valore di input, oppure "0" quando il valore e' nullo o non convertibile.

    Notes:
        La conversione passa da "float" per gestire stringhe numeriche senza propagare errori di formato.
    """
    if isinstance(value, (list, tuple, set)):
        value = next((item for item in value if not _is_null(item)), 0)
    if _is_null(value):
        return 0
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _as_year(value: Any) -> str:
    """Estrae un anno a quattro cifre da un valore bibliografico.

    Args:
        value: Valore grezzo contenente eventualmente un anno di pubblicazione.

    Returns:
        Prima sequenza di quattro cifre trovata come stringa; stringa vuota se non viene individuato alcun anno.

    Notes:
        Il risultato resta una stringa per rispettare il contratto del campo "PY" usato dalle funzioni analitiche.
    """
    match = re.search(r"\d{4}", _clean_string(value))
    return match.group(0) if match else ""


def _cast(tag: str, value: Any) -> Any:
    """Converte un valore secondo il tipo previsto per una colonna target.

    Args:
        tag: Nome della colonna nello schema WoS-like interno. value: Valore grezzo da convertire.

    Returns:
        Valore convertito nel tipo dichiarato in "COLUMN_TYPE_CONTRACTS".

    Raises:
        KeyError: Se "tag" non e' presente nel contratto delle colonne.

    Notes:
        Il campo "PY" viene trattato come caso speciale: pur essendo una stringa, deve contenere solo l'anno estratto dal valore originale.
    """
    expected_type = COLUMN_TYPE_CONTRACTS[tag]
    if expected_type is list:
        return _as_list(value)
    if expected_type is int:
        return _as_int(value)
    if tag == "PY":
        return _as_year(value)
    return _clean_string(value)


def _empty_record(db: str) -> dict[str, Any]:
    """Crea un record completo inizializzato con i valori di default.

    Args:
        db: Nome normalizzato della sorgente bibliografica da assegnare al campo "DB".

    Returns:
        Dizionario contenente tutte le colonne dello schema target con valori compatibili con i rispettivi contratti di tipo.

    Notes:
        Il record restituito e' la base comune per tutti i mapper di sorgente.
    """
    record = {tag: _default(contract) for tag, contract in COLUMN_TYPE_CONTRACTS.items()}
    record["DB"] = db
    return record



# Collegamento al file format_functions.py 
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
    """Determina l'estensione effettiva da passare ai formatter legacy.

    Args:
        raw_record: Record grezzo, eventualmente arricchito da "file_extractor" con metadati interni.
        source: Sorgente bibliografica normalizzata. 
        file_type: Tipo file dichiarato dal chiamante come fallback.

    Returns:
        Estensione normalizzata con punto iniziale, oppure ""api"" quando appropriato. Per PubMed da API/XML restituisce "".txt"" per riusare i formatter Medline esistenti.

    Notes:
        I metadati del record hanno priorita' sul parametro esplicito per preservare il tipo originale dei file annidati, ad esempio dentro ZIP.
    """
    effective = str(raw_record.get("_bibliometrix_file_type") or file_type or "").lower().strip()
    if effective and effective != "api" and not effective.startswith("."):
        effective = f".{effective}"

    # I record dell'API di PubMed vengono analizzati e convertiti in chiavi simili a quelle di Medline.
    if source == "PUBMED" and effective in {"api", ".xml", "xml", ""}:
        return ".txt"
    return effective


def _prepare_for_formatters(raw_record: dict[str, Any], source: str) -> dict[str, Any]:
    """Adatta un record grezzo alle aspettative di "format_functions".

    Args:
        raw_record: Record da trasformare prima della chiamata ai formatter.
        source: Nome della sorgente bibliografica normalizzata.

    Returns:
        Copia del record senza metadati interni e con alcune strutture convertite nel formato atteso dai formatter legacy.

    Notes:
        Per PubMed le liste vengono serializzate con il delimitatore interno, perche' i formatter preesistenti lavorano su stringhe Medline-like.
    """
    prepared = {k: v for k, v in raw_record.items() if k not in INTERNAL_KEYS}

    if source == "PUBMED":
        for key, value in list(prepared.items()):
            if isinstance(value, (list, tuple, set)):
                prepared[key] = CSV_DELIMITER.join(_as_list(value))
        if "MH" not in prepared and "OT" in prepared:
            prepared["MH"] = prepared["OT"]

    return prepared


def _build_sr(record: dict[str, Any]) -> str:
    """Costruisce un riferimento breve quando il campo "SR" e' assente.

    Args:
        record: Record gia' convertito nello schema target.

    Returns:
        Stringa nel formato "PrimoAutore, Anno, Sorgente" con le parti vuote omesse.

    Notes:
        Il campo "AU" deve essere una lista, come garantito dalla fase di cast.
    """
    first_author = record["AU"][0] if record["AU"] else ""
    return ", ".join(part for part in [first_author, record["PY"], record["SO"]] if part)


def _finalize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Applica normalizzazioni comuni dopo il mapping specifico di sorgente.

    Args:
        record: Record nello schema target da rifinire.

    Returns:
        Lo stesso dizionario ricevuto in input, aggiornato con campi derivati o normalizzati.

    Notes:
        La funzione modifica il dizionario in-place: "SO" viene portato in maiuscolo, "JI" eredita "SO" se assente e "SR" viene generato come fallback.
    """
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
    """Mappa un record usando i formatter legacy disponibili nel progetto.

    Args:
        raw_record: Record grezzo prodotto da extractor, parser o API.
        source: Sorgente bibliografica normalizzata.
        file_type: Estensione o tipo file da passare ai formatter.

    Returns:
        Record completo conforme a "COLUMN_TYPE_CONTRACTS".

    Notes:
        Le eccezioni dei singoli formatter vengono assorbite e convertite in valori di default tramite "_cast". Questo mantiene robusta la pipeline quando un campo non e' disponibile per una specifica sorgente.
    """
    record = _empty_record(source)
    formatter_source = SOURCE_NAME_MAP.get(source, source)
    prepared = _prepare_for_formatters(raw_record, source)

    for tag, formatter in FORMAT_FUNCTIONS_MAP.items():
        try:
            value = formatter(prepared, formatter_source, file_type)
        except Exception:
            # I formatter legacy possono assumere campi non presenti in tutte le sorgenti; il cast successivo produce il default del contratto.
            value = None
        record[tag] = _cast(tag, value)

    return _finalize_record(record)


# Mappatura OpenAlex, poiché non è coperta da format_functions.py
def _openalex_source(raw_record: dict[str, Any]) -> str:
    """Estrae il nome della sorgente editoriale da un record OpenAlex.

    Args:
        raw_record: Record OpenAlex grezzo.

    Returns:
        Nome normalizzato della venue, rivista o sorgente host; stringa vuota se l'informazione non e' disponibile.

    Notes:
        OpenAlex puo' esporre la sorgente in "primary_location.source" oppure nel campo legacy "host_venue".
    """
    location = raw_record.get("primary_location") or {}
    source = location.get("source") or raw_record.get("host_venue") or {}
    if isinstance(source, dict):
        return _clean_string(source.get("display_name"))
    return _clean_string(source)


def _openalex_authors_and_affiliations(raw_record: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Ricava autori e affiliazioni istituzionali da un record OpenAlex.

    Args:
        raw_record: Record OpenAlex grezzo contenente la lista "authorships".

    Returns:
        Tupla "(authors, affiliations)" con nomi autore e nomi istituzione normalizzati come liste di stringhe.

    Notes:
        Le affiliazioni duplicate vengono scartate mantenendo il primo ordine di apparizione nel record.
    """
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
    """Ricostruisce l'abstract OpenAlex dal suo indice invertito.

    Args:
        raw_record: Record OpenAlex grezzo con eventuale campo "abstract_inverted_index".

    Returns:
        Abstract ricostruito come testo ordinato per posizione; stringa vuota se l'indice non e' disponibile o non ha forma di dizionario.

    Raises:
        ValueError: Se una posizione presente nell'indice non e' convertibile a intero.

    Notes:
        OpenAlex memorizza l'abstract come mappa parola -> posizioni; ordinare le coppie per posizione ripristina la sequenza testuale originale.
    """
    inverted_index = raw_record.get("abstract_inverted_index")
    if not isinstance(inverted_index, dict):
        return ""

    words: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        # L'indice invertito associa ogni parola a una o piu' posizioni nel testo.
        for position in positions or []:
            words.append((int(position), str(word)))
    return " ".join(word for _, word in sorted(words))


def transform_openalex_record(raw_record: dict[str, Any]) -> dict[str, Any]:
    """Mappa un record OpenAlex nello schema Bibliometrix standardizzato.

    Args:
        raw_record: Record OpenAlex grezzo proveniente da API o file JSON.

    Returns:
        Record completo conforme a "COLUMN_TYPE_CONTRACTS".

    Notes:
        Le parole chiave vengono ricavate da "concepts" oppure da "keywords" e riusate sia per "DE" sia per "ID" per mantenere compatibilita' con le analisi downstream.
    """
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


# Righe XLSX/CSV già standardizzate
def _looks_standardized(raw_record: dict[str, Any]) -> bool:
    """Stima se un record e' gia' nel formato standardizzato interno.

    Args:
        raw_record: Record da classificare prima del dispatch di trasformazione.

    Returns:
        "True" se il record contiene "SR" e almeno dieci colonne dello schema target; "False" altrimenti.

    Notes:
        La soglia evita di trattare come standardizzati record grezzi che condividono solo pochi nomi di campo con lo schema finale.
    """
    target_columns = set(COLUMN_TYPE_CONTRACTS)
    return "SR" in raw_record and len(target_columns.intersection(raw_record)) >= 10


def transform_standardized_record(raw_record: dict[str, Any], default_db: str) -> dict[str, Any]:
    """Ricarica un record gia' esportato nello schema standardizzato.

    Args:
        raw_record: Riga o record precedentemente salvato con le colonne target.
        default_db: Valore da usare per "DB" se il record non contiene un dato valido.

    Returns:
        Record completo conforme a "COLUMN_TYPE_CONTRACTS".

    Notes:
        Ogni campo viene comunque passato da "_cast" per ripristinare liste, interi e stringhe dopo la lettura da CSV o Excel.
    """
    record = _empty_record(default_db)
    for tag in COLUMN_TYPE_CONTRACTS:
        record[tag] = _cast(tag, raw_record.get(tag, record[tag]))
    return _finalize_record(record)


def serialize_for_csv(record: dict[str, Any]) -> dict[str, Any]:
    """Serializza un record standardizzato in una forma adatta al CSV.

    Args:
        record: Record conforme allo schema target.

    Returns:
        Dizionario in cui le colonne lista sono convertite in stringhe separate da "CSV_DELIMITER"; gli altri valori restano invariati.

    Notes:
        La serializzazione e' pensata solo per export tabellare. Per l'uso interno della pipeline le liste devono rimanere oggetti "list".
    """
    return {
        tag: CSV_DELIMITER.join(value) if isinstance(value, list) else value
        for tag, value in record.items()
    }


# Punto di ingresso pubblico
def convert2df(
    raw_records: list[dict[str, Any]],
    source: str = "OPENALEX",
    file_type: str = ".csv",
    validate: bool = True,
    for_csv_export: bool = False,
) -> pd.DataFrame:
    """Converte record grezzi nel DataFrame Bibliometrix standardizzato.

    Args:
        raw_records: Lista di record grezzi rappresentati come dizionari.
        source: Sorgente bibliografica di default per i record privi di metadati interni.
        file_type: Tipo file di default usato dai formatter legacy.
        validate: Se "True", applica i controlli di contratto su record e DataFrame finale.
        for_csv_export: Se "True", serializza le colonne lista in stringhe per l'esportazione CSV e salta la validazione del DataFrame su liste.

    Returns:
        "pandas.DataFrame" con colonne ordinate secondo "COLUMN_TYPE_CONTRACTS". Se non sono presenti record validi, restituisce un DataFrame vuoto con lo stesso ordine di colonne.

    Raises:
        ValidationError: Se "validate" e' "True" e un record o il DataFrame finale violano il contratto dello schema.

    Notes:
        I record non rappresentati da dizionari vengono ignorati. Il dispatch sceglie tra ricaricamento standardizzato, mapping OpenAlex e formatter legacy in base ai metadati disponibili.
    """
    source = source.upper().strip()
    records: list[dict[str, Any]] = []

    for raw_record in raw_records or []:
        if not isinstance(raw_record, dict):
            continue

        record_source = str(raw_record.get("_bibliometrix_source", source)).upper().strip()
        effective_file_type = _effective_file_type(raw_record, record_source, file_type)

        # Il dispatch preserva i record gia' standardizzati ed evita passaggi inutili attraverso formatter progettati per dati grezzi.
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
            # Garantisce un DataFrame con schema stabile anche quando tutti i record in input omettono la stessa colonna.
            default_value = _default(expected_type)
            df[tag] = [[] for _ in range(len(df))] if expected_type is list else default_value

    df = df[column_order]
    if validate and not for_csv_export:
        validate_dataframe_contract(df, COLUMN_TYPE_CONTRACTS)

    return df
