# =============================================================================
# standardizer.py  —  Phase 2: TRANSFORM – RENAME (The Lookup Strategy)
# =============================================================================
#
# Module Overview
# ---------------
# This module constitutes the entirety of Phase 2 (Transform) of the
# source-agnostic bibliometric ETL pipeline. Its sole responsibility is to
# accept raw, heterogeneous records from any supported bibliographic database
# and produce a uniform, validated dictionary whose keys strictly conform to
# the Web of Science (WoS).
#
# The module is structured around three interconnected architectural pillars:
#
#   1. **Mapping Dictionaries (Lookup Strategy):** Per-source dictionaries
#      decouple proprietary field names from WoS standard tags. This replaces
#      brittle if/elif chains with pure data, respecting the Single
#      Responsibility Principle — the logic that processes a field never needs
#      to know the field's source-specific name.
#
#   2. **Type Contracts & Null Handling:** `COLUMN_TYPE_CONTRACTS` defines the
#      expected Python type for every output column. `_cast_scalar` and
#      `_get_default_value` enforce these contracts at transformation time,
#      guaranteeing that downstream analytical code never encounters
#      unexpected `None`, `NaN`, or mixed-type columns.
#
#   3. **Transform Dispatcher:** `_TRANSFORM_DISPATCHER` implements a
#      variation of the Strategy / Registry pattern, mapping each source
#      identifier to its dedicated transformation function. This makes the
#      system Open/Closed: adding support for a new database requires adding
#      one dictionary entry and one function, with zero modifications to the
#      main `convert2df` entry point.
#
# Responsibilities of this module:
#   1. Map proprietary source field names to standard WoS tags.
#   2. Enforce type contracts (type contracts) on every column.
#   3. Handle missing values (None / NaN → "" or [] or 0).
#   4. Extract complex fields (authors, affiliations, keywords, references).
#   5. Compute derived fields (SR – Short Reference).
#   6. Validate the final record before export.
#   7. Expose a single public entry-point: convert2df().
# =============================================================================

from __future__ import annotations

import pandas as pd
from typing import Any

# -----------------------------------------------------------------------------
# 1.  MAPPING DICTIONARIES  (Lookup Strategy)
# -----------------------------------------------------------------------------
# Each source database has its own dedicated mapping dictionary that translates
# its proprietary field names (keys) into the corresponding WoS standard tags
# (values). This architecture implements the **Lookup Strategy** pattern:
# instead of encoding source-specific knowledge into conditional logic (e.g.,
# `if source == "SCOPUS": field = record["Title"]`), the mapping is expressed
# as pure, declarative data. The transformation functions remain completely
# source-agnostic — they iterate over a dictionary, never branching on a
# source name. This strictly adheres to the Single Responsibility Principle:
# each mapping dictionary is the single authoritative definition of how one
# database's schema relates to the WoS standard, and it can be updated,
# reviewed, or extended without touching any procedural code.

# Direct scalar fields (string or integer) sourced from the top-level of an
# OpenAlex JSON API record.
OPENALEX_SCALAR_MAP: dict[str, str] = {
    "id":               "UT",   # Unique article identifier
    "doi":              "DI",   # Digital Object Identifier
    "title":            "TI",   # Document title
    "publication_year": "PY",   # 4-digit publication year (int in API, cast to str)
    "cited_by_count":   "TC",   # Total citation count (int)
    "language":         "LA",   # Document language (ISO 639-1 code)
    "type":             "DT",   # Document type (Article, Review, etc.)
}

# -----------------------------------------------------------------------------
# MAPPING DICTIONARY FOR OPENALEX (CSV VARIANT)
# -----------------------------------------------------------------------------
# OpenAlex can be consumed either through its REST API (JSON payloads) or via
# bulk CSV exports. The CSV format uses a flat, denormalized schema that differs
# significantly from the nested JSON structure. A separate mapping dictionary
# is therefore necessary to handle this format variant without polluting the
# JSON transformer with format-detection logic.
OPENALEX_CSV_SCALAR_MAP: dict[str, str] = {
    "id": "UT",                       # Unique identifier
    "doi": "DI",                      # DOI
    "title": "TI",                    # Document title
    "publication_year": "PY",         # Publication year
    "type": "DT",                     # Document type
    "cited_by_count": "TC",           # Citation count
    "host_venue": "SO",               # Journal name (CSV variant A)
    "source_display_name": "SO"       # Journal name (CSV variant B) — both included for robustness
}

# -----------------------------------------------------------------------------
# MAPPING DICTIONARY FOR SCOPUS (CSV EXPORT)
# -----------------------------------------------------------------------------
SCOPUS_SCALAR_MAP: dict[str, str] = {
    "EID": "UT",                           # Scopus unique identifier (Electronic ID)
    "DOI": "DI",                           # DOI
    "Title": "TI",                         # Document title
    "Source title": "SO",                  # Journal / source name
    "Abbreviated Source Title": "JI",      # ISO journal abbreviation
    "Year": "PY",                          # Publication year
    "Document Type": "DT",                 # Document type
    "Cited by": "TC",                      # Citation count
    "Abstract": "AB",                      # Abstract
    "Volume": "VL",                        # Volume number
    "Issue": "IS",                         # Issue number
    "Page start": "BP",                    # First page (Begin Page)
    "Page end": "EP",                      # Last page (End Page)
    "PubMed ID": "PMID",                   # PubMed identifier (when available)
    "Language of Original Document": "LA", # Document language
    "Correspondence Address": "RP",        # Reprint / corresponding author address
}

# -----------------------------------------------------------------------------
# MAPPING DICTIONARY FOR WEB OF SCIENCE
# -----------------------------------------------------------------------------
# WoS natively uses WoS tags as column headers. However, passing its records
# through the same mapping infrastructure as all other sources serves two
# purposes: (a) it guarantees that type contracts are uniformly enforced
# regardless of source, and (b) it handles known edge cases such as the dual
# citation-count field names (TC vs Z9) within different WoS export profiles.
WOS_SCALAR_MAP: dict[str, str] = {
    "UT": "UT",
    "DI": "DI",
    "PM": "PMID",  # In some WoS export profiles PubMed ID appears under "PM"
    "TI": "TI",
    "SO": "SO",
    "JI": "JI",
    "PY": "PY",
    "DT": "DT",
    "LA": "LA",
    "RP": "RP",
    "AB": "AB",
    "VL": "VL",
    "IS": "IS",
    "BP": "BP",
    "EP": "EP",
    "TC": "TC", # Primary citation count field in WoS exports
    "Z9": "TC"  # Alternative citation count field in certain WoS export formats
}

# -----------------------------------------------------------------------------
# MAPPING DICTIONARY FOR DIMENSIONS (CSV / XLSX EXPORT)
# -----------------------------------------------------------------------------
DIMENSIONS_SCALAR_MAP: dict[str, str] = {
    "Publication ID": "UT",            # Dimensions unique identifier
    "DOI": "DI",                       # DOI
    "PMID": "PMID",                    # PubMed identifier
    "Title": "TI",                     # Document title
    "Source title": "SO",              # Journal or venue name
    "PubYear": "PY",                   # Publication year
    "Publication Type": "DT",          # Document type
    "Times cited": "TC",               # Citation count
    "Abstract": "AB",                  # Abstract
    "Volume": "VL",                    # Volume number
    "Issue": "IS",                     # Issue number
    # The "Pagination" column is initially mapped to BP as a placeholder;
    # the transformer later splits it into BP (start) and EP (end) pages.
    "Pagination": "BP",
}

# -----------------------------------------------------------------------------
# MAPPING DICTIONARY FOR LENS (CSV EXPORT)
# -----------------------------------------------------------------------------
LENS_SCALAR_MAP: dict[str, str] = {
    "Lens ID": "UT",                   # Lens unique identifier
    "DOI": "DI",                       # DOI
    "PMID": "PMID",                    # PubMed identifier
    "Title": "TI",                     # Document title
    "Publication Year": "PY",          # Publication year
    "Publication Type": "DT",          # Document type
    "Source Title": "SO",              # Journal or source name
    "Volume": "VL",                    # Volume number
    "Issue": "IS",                     # Issue number
    "Start Page": "BP",                # First page
    "End Page": "EP",                  # Last page
    "Abstract": "AB",                  # Abstract
    "Citing Works Count": "TC",        # Citation count
}

# -----------------------------------------------------------------------------
# MAPPING DICTIONARY FOR COCHRANE (TXT EXPORT)
# -----------------------------------------------------------------------------
COCHRANE_SCALAR_MAP: dict[str, str] = {
    "TI": "TI",     # Title
    "SO": "SO",     # Source / journal name
    "YR": "PY",     # Year — Cochrane's primary year field is often "YR"
    "PY": "PY",     # Year — alternative field name for robustness
    "DO": "DI",     # DOI — Cochrane uses "DO" instead of the standard "DI"
    "DI": "DI",     # DOI — alternative field name for robustness
    "AB": "AB",     # Abstract
    "VL": "VL",     # Volume
    "NO": "IS",     # Issue number — Cochrane's field is often "NO"
    "IS": "IS",     # Issue number — alternative field name for robustness
    "PT": "DT",     # Publication type
}

# Nested scalar fields for the OpenAlex JSON format: each entry specifies a
# traversal path through the nested JSON structure and the WoS tag to which
# the resolved value should be assigned. This list-of-tuples structure enables
# the `clean_scalar_fields` function to handle arbitrarily deep nesting in a
# single, uniform loop, rather than requiring bespoke access code per field.
OPENALEX_NESTED_SCALAR_MAP: list[tuple[list[str], str]] = [
    (["primary_location", "source", "display_name"],    "SO"),  # Journal display name
    (["primary_location", "source", "abbreviated_title"],"JI"),  # ISO journal abbreviation
    (["biblio", "volume"],                               "VL"),  # Volume number
    (["biblio", "issue"],                                "IS"),  # Issue number
    (["biblio", "first_page"],                           "BP"),  # First page
    (["biblio", "last_page"],                            "EP"),  # Last page
    (["ids", "pmid"],                                    "PMID"),# PubMed identifier
]

# -----------------------------------------------------------------------------
# 2.  TYPE CONTRACTS  (Data Integrity)
# -----------------------------------------------------------------------------
# This dictionary is the central schema definition of the pipeline's output.
# It maps every WoS output tag to the single Python type that is permissible
# for that column. Enforcing these contracts at transformation time — rather
# than at analysis time — is a fundamental Data Integrity principle: it
# prevents invalid states from ever entering the system, instead of requiring
# defensive checks to be scattered throughout all downstream consumers.
#
# Concretely, this prevents a class of runtime errors common in bibliometric
# pipelines: a column expected to hold integers (e.g., TC) receiving a mix of
# integers and `None` values, which would silently break arithmetic operations
# such as citation count rankings or correlation analyses.

COLUMN_TYPE_CONTRACTS: dict[str, type] = {
    # String scalar fields — bibliographic metadata
    "DB":   str,   # Source database identifier
    "UT":   str,   # Unique record identifier
    "DI":   str,   # DOI
    "PMID": str,   # PubMed identifier
    "TI":   str,   # Title
    "SO":   str,   # Source (journal) name
    "JI":   str,   # ISO journal abbreviation
    "PY":   str,   # Publication year (stored as 4-char string for consistency)
    "DT":   str,   # Document type
    "LA":   str,   # Language
    "RP":   str,   # Reprint address
    "AB":   str,   # Abstract
    "VL":   str,   # Volume
    "IS":   str,   # Issue
    "BP":   str,   # Begin page
    "EP":   str,   # End page
    "SR":   str,   # Short Reference (derived / computed field)
    # Integer scalar field
    "TC":   int,   # Total citation count
    # Multi-value list fields — require special handling during serialization
    "AU":   list,  # Authors (WoS format: "Surname, Firstname")
    "AF":   list,  # Authors full names
    "C1":   list,  # Institutional affiliations
    "CR":   list,  # Cited references
    "DE":   list,  # Author keywords
    "ID":   list,  # Index keywords / Keywords Plus
}

# -----------------------------------------------------------------------------
# MAPPING DICTIONARY FOR PUBMED (MEDLINE FORMAT)
# -----------------------------------------------------------------------------
PUBMED_SCALAR_MAP: dict[str, str] = {
    "PMID": "UT",   # PubMed unique identifier doubles as the record UT
    "LID":  "DI",   # Location ID — in MEDLINE this often carries the DOI
    "TI":   "TI",   # Title
    "JT":   "SO",   # Full journal title
    "TA":   "JI",   # Journal title abbreviation
    "PT":   "DT",   # Publication type
    "LA":   "LA",   # Language
    "AB":   "AB",   # Abstract
    "VI":   "VL",   # Volume
    "IP":   "IS",   # Issue (IP = Issue/Part)
    "PG":   "BP",   # Pagination — requires a split into BP and EP downstream
}

# Canonical default values keyed by Python type. These are used by `_cast_scalar`
# to resolve `None` inputs into type-safe empty values.
_TYPE_DEFAULTS: dict[type, Any] = {
    str:  "",
    int:  0,
    list: [],
}

def _get_default_value(expected_type: type) -> Any:
    """Quando nel database di origine manca un'informazione (ad esempio, un articolo non ha autori o non ha un anno di pubblicazione), 
    questa funzione riempie il buco con un valore di partenza (default) corretto. Lo fa in base al tipo di dato che la colonna richiede.
    Il "trucco" salvavita sulle liste: In Python, c'è una trappola nota come shared mutable state. Se la funzione usasse sempre la stessa lista vuota per tutti i record a cui manca un dato, 
    tutti quei record condividerebbero la stessa identica area di memoria. Il risultato? Se aggiungessi un autore al "Record A", questo apparirebbe magicamente anche nel "Record B" e nel "Record C".
    Restituendo [] direttamente nell'if, il codice costruisce letteralmente una nuova scatola vuota e indipendente per ogni singolo record, evitando che i dati si mescolino tra loro.
    """
    if expected_type is list:
        return []  # A new list object is constructed on each call, never shared
    return _TYPE_DEFAULTS.get(expected_type, "")

"""Alcuni campi, come gli "Autori" (AU) o le "Parole Chiave" (DE), contengono più elementi. 
Quando devi salvare questi dati in un file di testo piatto (come un CSV da aprire in Excel), non puoi inserirci dentro una lista Python vera e propria.
Questa semplice variabile (CSV_DELIMITER = ";") stabilisce una regola fissa: quando le liste vengono convertite in testo per essere salvate, 
i vari elementi dovranno essere separati da un punto e virgola."""
CSV_DELIMITER: str = ";"

# -----------------------------------------------------------------------------
# 3.  HELPER: NESTED FIELD ACCESS
# -----------------------------------------------------------------------------

def _get_nested(record: dict, path: list[str]) -> Any:
    """Safely traverses a nested dictionary by following a sequence of keys.

    This utility centralises the access pattern for deeply nested JSON
    structures (such as those returned by the OpenAlex API), avoiding
    repetitive and error-prone chains of ``.get()`` calls scattered across
    the codebase. It short-circuits at the first missing key or ``None``
    intermediate value, returning ``None`` safely rather than raising a
    ``KeyError`` or ``TypeError``.

    Args:
        record: The root dictionary to traverse.
        path:   An ordered list of string keys representing the traversal path.
                Example: ``["primary_location", "source", "display_name"]``
                is equivalent to
                ``record["primary_location"]["source"]["display_name"]``.

    Returns:
        The value found at the end of the path, or ``None`` if any
        intermediate key is absent or its value is ``None``.

    Example::

        _get_nested(rec, ["primary_location", "source", "display_name"])
        → rec["primary_location"]["source"]["display_name"]
    """
    current: Any = record
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


# -----------------------------------------------------------------------------
# 4.  CLEAN SCALAR FIELDS
# -----------------------------------------------------------------------------

def clean_scalar_fields(raw_record: dict) -> dict:
    """
    Estrae, ripulisce e formatta i dati singoli (scalari, come Titolo o Anno)
    da un record JSON grezzo di OpenAlex, convertendoli nello standard Web of Science (WoS).

    Esegue queste operazioni in ordine:
    1. Origine: Scrive esplicitamente "OPENALEX" nella colonna DB per tracciare la provenienza.
    2. Superficie: Traduce i campi di primo livello nei tag WoS (es. "title" -> "TI")
       e usa il controllore dei tipi per assicurarsi che i dati siano puliti e sicuri.
    3. Sicurezza Anno: Taglia l'anno di pubblicazione (PY) a esattamente 4 caratteri
       (es. "2024-10-15" -> "2024") per prevenire errori in caso di cambi futuri nelle API.
    4. Profondità: Usa l'esploratore sicuro (_get_nested) per pescare dati nascosti
       più in profondità nel file JSON (es. il nome della rivista).
    5. Normalizzazione: Converte il nome della rivista (SO) tutto in MAIUSCOLO
       per garantire la compatibilità con il pacchetto Bibliometrix originale in R.
    """
    result: dict = {}

    # Imposta esplicitamente l'identificativo del database (DB)
    result["DB"] = "OPENALEX"

    # --- Campi scalari di primo livello ---
    for oa_key, wos_tag in OPENALEX_SCALAR_MAP.items():
        val = raw_record.get(oa_key)
        expected_type = COLUMN_TYPE_CONTRACTS[wos_tag]
        result[wos_tag] = _cast_scalar(val, expected_type)

    # Assicura che l'anno (PY) sia una stringa di 4 caratteri
    if result.get("PY"):
        result["PY"] = str(result["PY"])[:4]

    # --- Campi scalari nidificati ---
    for path, wos_tag in OPENALEX_NESTED_SCALAR_MAP:
        val = _get_nested(raw_record, path)
        expected_type = COLUMN_TYPE_CONTRACTS[wos_tag]
        result[wos_tag] = _cast_scalar(val, expected_type)

    # Converte in maiuscolo il nome della rivista (SO)
    if result.get("SO"):
        result["SO"] = result["SO"].upper()

    return result

def _cast_scalar(value: Any, expected_type: type) -> Any:
    """
    Il "Garante delle Regole": forza un dato grezzo a rispettare il suo Contratto di Tipo.

    Questa è la linea di difesa fondamentale per l'integrità dei dati della pipeline. 
    Assicura che nel risultato finale non entrino mai valori 'None', tipi di dato 
    sbagliati o testi sporchi. Raggruppare questa logica in un'unica funzione (principio DRY) 
    evita di dover scrivere gli stessi controlli decine di volte in tutto il codice.

    Regole di conversione (Coercion rules):
    - Se è ``None`` → restituisce il valore vuoto di default per quel tipo (es. 0 o "").
    - Se è richiesto un numero (``int``) → tenta di convertirlo. Se c'è un errore (es. lettere 
      invece di numeri), non fa crashare il sistema ma restituisce uno ``0`` di sicurezza.
    - Se è richiesto un testo (``str``) → lo trasforma in stringa e usa ``.strip()`` 
      per "tagliare via" eventuali spazi vuoti accidentali all'inizio o alla fine.
    """
    if value is None:
        return _TYPE_DEFAULTS[expected_type]

    if expected_type is int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    # str — convert and strip extraneous whitespace
    return str(value).strip()


# -----------------------------------------------------------------------------
# 5.  EXTRACT COMPLEX FIELDS
# -----------------------------------------------------------------------------

def extract_authors(raw_record: dict) -> list[str]:
    """
    Il "Riformattatore di Nomi": estrae gli autori da OpenAlex e li riordina.

    Le API di OpenAlex forniscono i nomi nel formato naturale "Nome Cognome" 
    (es. "Mario Rossi"). Tuttavia, lo standard Web of Science (tag AU) impone 
    il formato "Cognome, Nome" ("Rossi, Mario"). Questa normalizzazione è 
    assolutamente cruciale per far funzionare bene le analisi successive 
    (come i grafi sulle reti di collaborazione), dove l'identità dell'autore 
    deve essere perfetta e coerente.

    Come funziona:
    - Divide il nome in parole: l'ultima parola diventa il cognome, il resto il nome.
    - Se il nome è formato da una sola parola (es. il nome di un'azienda o un mononimo),
      lo lascia così com'è, visto che non c'è niente da dividere.
    """
    authorships = raw_record.get("authorships")
    if not authorships:
        return []

    author_list: list[str] = []
    for auth in authorships:
        author_data = auth.get("author", {})
        name = author_data.get("display_name")
        if not name:
            continue

        name_str = str(name).strip()
        parts = name_str.split()
        if len(parts) > 1:
            surname = parts[-1]
            first_names = " ".join(parts[:-1])
            formatted = f"{surname}, {first_names}"
        else:
            formatted = name_str

        author_list.append(formatted)

    return author_list


def extract_affiliations(raw_record: dict) -> list[str]:
    """
    L'"Estrattore di Istituzioni": recupera le affiliazioni (tag C1) senza creare doppioni.

    Scorre tutti gli autori di un articolo e raccoglie il nome dell'istituzione o
    dell'università di appartenenza. È uno scenario comunissimo che molti co-autori 
    lavorino per la stessa università. Questa funzione elimina i doppioni sul nascere.

    Come funziona:
    - Usa un ``set`` (un insieme matematico) per tenere a mente le università già lette.
    - Se l'università trovata non è ancora nel set, la aggiunge alla lista finale.
    - Questo metodo è super-efficiente e assicura che una collaborazione tra 10 colleghi
      della stessa università non generi 10 voci identiche nel file finale.
    """
    authorships = raw_record.get("authorships")
    if not authorships:
        return []

    affiliation_list: list[str] = []
    seen: set[str] = set()

    for auth in authorships:
        institutions = auth.get("institutions", [])
        for inst in institutions:
            inst_name = inst.get("display_name")
            if inst_name:
                name_str = str(inst_name).strip()
                if name_str not in seen:
                    seen.add(name_str)
                    affiliation_list.append(name_str)

    return affiliation_list


def extract_reprint_address(raw_record: dict) -> str:
    """
    Il "Cercatore dell'Autore Principale": recupera l'indirizzo per i contatti (tag RP).

    In ambito accademico è importante sapere quale università contattare (il "corresponding author").
    Questa funzione usa una strategia a due tentativi per non lasciare mai il campo vuoto
    se c'è almeno un'informazione utile:

    1. Tentativo Principale: Cerca esplicitamente l'autore che OpenAlex ha marchiato 
       come "is_corresponding: True" e prende il nome della sua istituzione.
    2. Piano B (Fallback): Molti record non hanno questa etichetta. In tal caso, 
       la funzione si accontenta del primo autore della lista che abbia un'università 
       associata, salvando così il dato.
    """
    authorships = raw_record.get("authorships", [])
    if not authorships:
        return ""

    # Prima scelta: l'autore esplicitamente segnato come corrispondente
    for auth in authorships:
        if auth.get("is_corresponding"):
            institutions = auth.get("institutions", [])
            if institutions:
                name = institutions[0].get("display_name", "")
                return str(name).strip() if name else ""

    # Piano B: il primo autore con almeno un'istituzione affiliata
    for auth in authorships:
        institutions = auth.get("institutions", [])
        if institutions:
            name = institutions[0].get("display_name", "")
            return str(name).strip() if name else ""

    return ""


def extract_keywords(raw_record: dict) -> list[str]:
    """
    L'"Estrattore di Parole Chiave" (tag DE).

    Recupera le parole chiave scelte direttamente dagli autori dell'articolo 
    (che in OpenAlex si trovano nel campo 'keywords'). Queste corrispondono al tag DE 
    (Descriptor) di Web of Science e sono essenziali per le analisi sulle reti concettuali.
    """
    keywords_data = raw_record.get("keywords")
    if not keywords_data:
        return []

    return [
        str(kw["display_name"]).strip()
        for kw in keywords_data
        if kw.get("display_name")
    ]


def extract_index_keywords(raw_record: dict) -> list[str]:
    """
    L'"Estrattore di Parole Chiave Aggiuntive" (Keywords Plus, tag ID).

    A differenza delle parole scelte dagli autori, questi sono concetti tematici 
    assegnati in automatico dai database (i cosiddetti "Keywords Plus" in WoS).
    OpenAlex usa tecnologie di intelligenza artificiale per assegnare questi argomenti.

    Strategia di sicurezza:
    Attualmente OpenAlex chiama questo campo 'topics'. Tuttavia, per i record più 
    vecchi usava il nome 'concepts'. Questa funzione cerca prima i 'topics'; 
    se non li trova, non si arrende e va a cercare nei vecchi 'concepts'.
    """
    topics_data = raw_record.get("topics")
    if not topics_data:
        # Piano B: usa il vecchio campo 'concepts' per i record API non ancora aggiornati
        concepts_data = raw_record.get("concepts")
        if not concepts_data:
            return []
        return [
            str(c["display_name"]).strip()
            for c in concepts_data
            if c.get("display_name")
        ]

    return [
        str(t["display_name"]).strip()
        for t in topics_data
        if t.get("display_name")
    ]


def extract_references(raw_record: dict) -> list[str]:
    """
    Il "Raccoglitore di Citazioni" (tag CR).

    Prende l'elenco di tutti gli articoli citati dal documento (la bibliografia).
    Attenzione: OpenAlex non fornisce il testo completo della citazione (es. "Rossi (2024)..."), 
    ma fornisce dei link diretti (es. "https://openalex.org/W12345").
    
    Questa funzione si limita a raccogliere questi link in una lista. Risolvere ogni 
    singolo link per ottenere il testo completo richiederebbe una chiamata API 
    aggiuntiva per ogni singola citazione, un'operazione troppo lenta per questa fase.
    """
    references = raw_record.get("referenced_works")
    if not references:
        return []

    return [str(ref).strip() for ref in references if ref]


def reconstruct_abstract(raw_record: dict) -> str:
    """
    Il "Ricostruttore di Abstract" (Il Puzzle delle Parole).

    Questa è una delle funzioni più particolari per OpenAlex. 
    Per risparmiare spazio, OpenAlex non invia l'abstract come un normale testo da leggere. 
    Invia un "indice invertito": un dizionario che dice quale parola compare e in quale posizione 
    (es. {"machine": [0, 14], "learning": [1]}).

    Questa funzione risolve il puzzle:
    1. Calcola quanto è lungo l'abstract guardando il numero di posizione più alto.
    2. Crea una lista vuota lunga quanto l'abstract.
    3. Inserisce ogni parola nella sua posizione corretta.
    4. Unisce tutto in un'unica stringa di testo leggibile.

    Se qualcosa va storto (es. dati corrotti), cattura l'errore e restituisce un testo vuoto,
    evitando che l'intero articolo venga scartato.
    """
    inverted_index = raw_record.get("abstract_inverted_index")
    if not inverted_index:
        return ""

    try:
        max_index = max(
            max(positions)
            for positions in inverted_index.values()
        )
        words: list[str] = [""] * (max_index + 1)
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word
        return " ".join(words).strip()

    except Exception as exc:
        # Piano di emergenza: se il puzzle è rotto, restituisce un testo vuoto
        # invece di bloccare l'elaborazione dell'intero articolo.
        print(f"[WARN] Errore nella ricostruzione dell'abstract: {exc}")
        return ""


# -----------------------------------------------------------------------------
# 7.  PRIMARY TRANSFORMATION FUNCTION
# -----------------------------------------------------------------------------

def transform_openalex_record(raw_record: dict) -> dict:
    """
    Il "Direttore d'Orchestra" per OpenAlex (Formato JSON).

    Questa funzione non fa il lavoro sporco da sola, ma coordina tutte le altre
    funzioni specializzate (gli "operai") che abbiamo visto finora. Segue una 
    ricetta fissa e infallibile (il pattern "Template Method"):

    1. Costruisce lo Scheletro: Crea un dizionario vuoto ma sicuro, dove tutti i tag 
       WoS hanno già il loro valore di default (es. liste vuote per gli autori). 
       Questo garantisce che il record finale avrà *sempre* tutte le colonne necessarie.
    2. Mappa i campi base: Chiama il traduttore dei campi semplici.
    3. Estrae i campi complessi: Delega l'estrazione di autori, affiliazioni, ecc., 
       alle funzioni specifiche.
    4. Piano B per la Rivista: Se non trova l'abbreviazione ufficiale della rivista (JI), 
       ci copia dentro il nome completo (SO) per non lasciare il buco.
    """
    # Passo 1: Inizializza lo scheletro sicuro
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }

    # Passo 2: Sovrascrive i campi scalari (semplici)
    standardized.update(clean_scalar_fields(raw_record))

    # Passo 3: Estrae e assegna i campi complessi (liste e dati nidificati)
    standardized["AU"] = extract_authors(raw_record)
    standardized["AF"] = standardized["AU"]          
    standardized["C1"] = extract_affiliations(raw_record)
    standardized["RP"] = extract_reprint_address(raw_record)
    standardized["DE"] = extract_keywords(raw_record)
    standardized["ID"] = extract_index_keywords(raw_record)
    standardized["CR"] = extract_references(raw_record)
    standardized["AB"] = reconstruct_abstract(raw_record)

    # Piano di riserva per l'abbreviazione della rivista
    if not standardized.get("JI") and standardized.get("SO"):
        standardized["JI"] = standardized["SO"]

    return standardized

# -----------------------------------------------------------------------------
# TRANSFORMATION FUNCTION FOR OPENALEX CSV VARIANT
# -----------------------------------------------------------------------------
def transform_openalex_csv_record(raw_record: dict) -> dict:
    """
    L'"Operaio Specializzato" per i CSV di OpenAlex.

    A volte OpenAlex viene esportato come tabella piatta (CSV) invece che come 
    JSON. In questo formato, non ci sono "scatole cinesi", ma le liste (come gli autori) 
    sono schiacciate in un'unica cella di testo. Questa funzione gestisce questa 
    variante senza inquinare o complicare il "Direttore d'Orchestra" del JSON.

    Per dividere le liste, usa l'intelligenza: cerca prima il punto e virgola (;). 
    Se non lo trova, prova con la virgola (,). Il punto e virgola ha la precedenza 
    perché una virgola potrebbe far parte del nome di un autore (es. "Rossi, Mario").
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "OPENALEX"

    # 1. Traduce i campi base
    for csv_key, wos_tag in OPENALEX_CSV_SCALAR_MAP.items():
        if csv_key in raw_record and raw_record[csv_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[csv_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # 2. Estrazione delle liste (divisione delle stringhe)
    
    # Autori (AU e AF)
    authors_str = str(raw_record.get("authors", raw_record.get("author_display_names", "")))
    if authors_str and authors_str.strip():
        separator = ";" if ";" in authors_str else ","
        authors_list = [a.strip() for a in authors_str.split(separator) if a.strip()]
        
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Concetti / Parole chiave (ID)
    concepts_str = str(raw_record.get("concepts", ""))
    if concepts_str and concepts_str.strip():
        separator = ";" if ";" in concepts_str else ","
        standardized["ID"] = [c.strip() for c in concepts_str.split(separator) if c.strip()]
        
    # Citazioni (CR)
    refs_str = str(raw_record.get("referenced_works", ""))
    if refs_str and refs_str.strip():
        separator = ";" if ";" in refs_str else ","
        standardized["CR"] = [r.strip() for r in refs_str.split(separator) if r.strip()]

    return standardized

# -----------------------------------------------------------------------------
# TRANSFORMATION FUNCTION FOR PUBMED (MEDLINE FORMAT)
# -----------------------------------------------------------------------------
def transform_pubmed_record(raw_record: dict) -> dict:
    """
    Il "Traduttore Medico" per i dati di PubMed (formato MEDLINE).

    Risolve le stranezze storiche del formato PubMed:
    - Anno (DP): Taglia le date complete (es. "2024 Oct 15") tenendo solo l'anno a 4 cifre.
    - DOI (LID): Rimuove l'etichetta "[doi]" appiccicata alla fine del codice.
    - Pagine (PG): Divide le pagine fuse col trattino (es. "123-145") in Inizio (BP) e Fine (EP).
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "PUBMED"
    standardized["PMID"] = raw_record.get("PMID", "")

    # Mappa i campi semplici
    for medline_key, wos_tag in PUBMED_SCALAR_MAP.items():
        val = raw_record.get(medline_key)
        # Protezione: se un singolo valore arriva intrappolato in una lista, lo estrae
        if isinstance(val, list):
            val = val[0]
        standardized[wos_tag] = _cast_scalar(val, COLUMN_TYPE_CONTRACTS[wos_tag])

    # --- Cure specifiche per PubMed ---

    dp = raw_record.get("DP", "")
    if dp and len(dp) >= 4:
        standardized["PY"] = dp[:4]

    lid = raw_record.get("LID", "")
    if "[doi]" in str(lid):
        standardized["DI"] = str(lid).split("[doi]")[0].strip()

    pg = raw_record.get("PG", "")
    if "-" in pg:
        parts = pg.split("-")
        standardized["BP"] = parts[0].strip()
        standardized["EP"] = parts[1].strip()
    else:
        standardized["BP"] = pg

    au = raw_record.get("AU", [])
    standardized["AU"] = au if isinstance(au, list) else [au]
    
    fau = raw_record.get("FAU", [])
    standardized["AF"] = fau if isinstance(fau, list) else [fau]

    ad = raw_record.get("AD", [])
    standardized["C1"] = ad if isinstance(ad, list) else [ad]

    ot = raw_record.get("OT", [])
    standardized["DE"] = ot if isinstance(ot, list) else [ot]

    return standardized

# -----------------------------------------------------------------------------
# TRANSFORMATION FUNCTION FOR SCOPUS (CSV EXPORT)
# -----------------------------------------------------------------------------
def transform_scopus_record(raw_record: dict) -> dict:
    """
    L'"Operaio Specializzato" per i CSV di Scopus.

    Scopus esporta le liste (autori, affiliazioni) in singole celle separate da punteggiatura.
    Questa funzione cerca il punto e virgola (usato spesso per affiliazioni e parole chiave)
    per spacchettare correttamente i dati.

    Filtro anti-spazzatura: intercetta ed elimina il testo "[no author name available]"
    che Scopus inserisce fastidiosamente quando mancano i dati sugli autori.
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "SCOPUS"

    for scopus_key, wos_tag in SCOPUS_SCALAR_MAP.items():
        if scopus_key in raw_record and raw_record[scopus_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[scopus_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # Autori (scarta il testo segnaposto se presente)
    authors_str = str(raw_record.get("Authors", ""))
    if authors_str and authors_str.strip() and authors_str.lower() != "[no author name available]":
        separator = ";" if ";" in authors_str else ","
        authors_list = [a.strip() for a in authors_str.split(separator) if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list 
        
    affiliations_str = str(raw_record.get("Affiliations", ""))
    if affiliations_str and affiliations_str.strip():
        standardized["C1"] = [aff.strip() for aff in affiliations_str.split(";") if aff.strip()]

    auth_kw_str = str(raw_record.get("Author Keywords", ""))
    if auth_kw_str and auth_kw_str.strip():
        standardized["DE"] = [kw.strip() for kw in auth_kw_str.split(";") if kw.strip()]
        
    idx_kw_str = str(raw_record.get("Index Keywords", ""))
    if idx_kw_str and idx_kw_str.strip():
        standardized["ID"] = [kw.strip() for kw in idx_kw_str.split(";") if kw.strip()]

    refs_str = str(raw_record.get("References", ""))
    if refs_str and refs_str.strip():
        standardized["CR"] = [r.strip() for r in refs_str.split(";") if r.strip()]

    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# TRANSFORMATION FUNCTION FOR WEB OF SCIENCE (TXT and CSV variants)
# -----------------------------------------------------------------------------
def transform_wos_record(raw_record: dict) -> dict:
    """
    L'"Adattatore Bivalente" per Web of Science.

    WoS può essere esportato in due modi: come file di testo TXT (dove i campi sono 
    suddivisi in liste dal parser) o come CSV (dove tutto è una stringa piatta).
    Questa funzione è intelligente: rileva "al volo" il tipo di dato e si adatta.

    - Se vede una lista (TXT), la prende così com'è.
    - Se vede una stringa (CSV), la spezza usando il punto e virgola.
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "WEB_OF_SCIENCE"

    # 1. Mappa i campi semplici (se trova una lista dal TXT, estrae solo il primo valore)
    for wos_key, standard_tag in WOS_SCALAR_MAP.items():
        if wos_key in raw_record:
            val = raw_record[wos_key]
            
            if isinstance(val, list) and len(val) > 0:
                val = val[0]
                
            standardized[standard_tag] = _cast_scalar(val, COLUMN_TYPE_CONTRACTS[standard_tag])

    # 2. Funzione aiutante interna per gestire la doppia natura TXT/CSV per le liste
    def extract_list_field(field_key: str) -> list[str]:
        raw_val = raw_record.get(field_key, [])
        if isinstance(raw_val, list):
            return [str(v).strip() for v in raw_val if v]
        elif isinstance(raw_val, str) and raw_val.strip():
            return [v.strip() for v in raw_val.split(";") if v.strip()]
        return []

    # 3. Assegna le liste in modo sicuro
    standardized["AU"] = extract_list_field("AU")
    standardized["AF"] = extract_list_field("AF") or standardized["AU"]
    standardized["C1"] = extract_list_field("C1")
    standardized["CR"] = extract_list_field("CR")
    standardized["DE"] = extract_list_field("DE")
    standardized["ID"] = extract_list_field("ID")

    return standardized

# -----------------------------------------------------------------------------
# TRANSFORMATION FUNCTION FOR DIMENSIONS (CSV / XLSX EXPORT)
# -----------------------------------------------------------------------------
def transform_dimensions_record(raw_record: dict) -> dict:
    """
    L'"Operaio Specializzato" per i file di Dimensions (CSV / Excel).

    Risolve due particolarità del formato di esportazione di Dimensions:
    1. Impaginazione: Invece di dare pagina di inizio e fine, Dimensions le fonde
       insieme (es. "10-25"). La funzione le separa usando il trattino.
    2. Citazioni (Reference IDs): Il separatore cambia a seconda di come l'utente 
       ha esportato il file. La funzione cerca prima il punto e virgola, poi la virgola.
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "DIMENSIONS"

    for dim_key, wos_tag in DIMENSIONS_SCALAR_MAP.items():
        if dim_key in raw_record and raw_record[dim_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[dim_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # Divisione delle pagine
    pagination = str(raw_record.get("Pagination", ""))
    if "-" in pagination:
        parts = pagination.split("-", 1)  # Taglia solo al primo trattino (es. per pagine come "e1-e15")
        standardized["BP"] = parts[0].strip()
        standardized["EP"] = parts[1].strip()

    # Autori
    authors_str = str(raw_record.get("Authors", ""))
    if authors_str and authors_str.strip():
        authors_list = [a.strip() for a in authors_str.split(";") if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Affiliazioni
    affiliations_str = str(raw_record.get("Authors Affiliations", ""))
    if affiliations_str and affiliations_str.strip():
        standardized["C1"] = [aff.strip() for aff in affiliations_str.split(";") if aff.strip()]

    # Parole chiave scelte dall'IA di Dimensions
    concepts_str = str(raw_record.get("Concepts", ""))
    if concepts_str and concepts_str.strip():
        standardized["DE"] = [c.strip() for c in concepts_str.split(";") if c.strip()]

    # Vocabolario Medico (MeSH)
    mesh_str = str(raw_record.get("MeSH terms", ""))
    if mesh_str and mesh_str.strip():
        standardized["ID"] = [m.strip() for m in mesh_str.split(";") if m.strip()]

    # Citazioni
    refs_str = str(raw_record.get("Reference IDs", ""))
    if refs_str and refs_str.strip():
        separator = ";" if ";" in refs_str else ","
        standardized["CR"] = [r.strip() for r in refs_str.split(separator) if r.strip()]

    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# TRANSFORMATION FUNCTION FOR COCHRANE (TXT EXPORT)
# -----------------------------------------------------------------------------
def transform_cochrane_record(raw_record: dict) -> dict:
    """
    Il "Traduttore per la Libreria Cochrane".

    I file TXT di Cochrane usano etichette di sole due lettere che somigliano a quelle
    di Web of Science, ma spesso sono diverse (es. usa "YR" per l'anno invece di "PY", 
    oppure "DO" per il DOI). Questa funzione sistema i nomi.

    Nota di sicurezza: Cochrane raramente esporta la bibliografia (CR) o le università (C1). 
    Grazie allo scheletro iniziale che inserisce liste vuote di default, il codice 
    non andrà in crash quando tenterà di analizzare questi dati inesistenti.
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "COCHRANE"

    for coch_key, wos_tag in COCHRANE_SCALAR_MAP.items():
        if coch_key in raw_record and raw_record[coch_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[coch_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # Divisione delle pagine
    pg = str(raw_record.get("PG", ""))
    if "-" in pg:
        parts = pg.split("-", 1)
        standardized["BP"] = parts[0].strip()
        standardized["EP"] = parts[1].strip()
    elif pg:
        standardized["BP"] = pg.strip()

    # Autori
    au_str = str(raw_record.get("AU", ""))
    if au_str and au_str.strip():
        authors_list = [a.strip() for a in au_str.split(";") if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Parole chiave (Cochrane usa KW invece di DE)
    kw_str = str(raw_record.get("KW", ""))
    if kw_str and kw_str.strip():
        standardized["DE"] = [k.strip() for k in kw_str.split(";") if k.strip()]

    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# TRANSFORMATION FUNCTION FOR LENS (CSV EXPORT)
# -----------------------------------------------------------------------------
def transform_lens_record(raw_record: dict) -> dict:
    """
    L'"Operaio Specializzato" per Lens.org.

    Lens è un database aperto e fortunatamente il suo CSV è molto pulito:
    usa costantemente il punto e virgola per separare tutti i campi a lista.
    Questa funzione si limita a spacchettare in sicurezza tutte le colonne.

    Particolarità: Lens genera argomenti tematici chiamati "Fields of Study".
    Questi vengono inseriti nel tag "ID" (Index Keywords) di Web of Science.
    """
    standardized: dict = {
        tag: _get_default_value(contract)
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "LENS"

    for lens_key, wos_tag in LENS_SCALAR_MAP.items():
        if lens_key in raw_record and raw_record[lens_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[lens_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # Autori
    authors_str = str(raw_record.get("Author/s", ""))
    if authors_str and authors_str.strip():
        authors_list = [a.strip() for a in authors_str.split(";") if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Parole Chiave Autore
    kw_str = str(raw_record.get("Keywords", ""))
    if kw_str and kw_str.strip():
        standardized["DE"] = [k.strip() for k in kw_str.split(";") if k.strip()]

    # Argomenti di studio (Assegnati dall'Intelligenza Artificiale)
    fos_str = str(raw_record.get("Fields of Study", ""))
    if fos_str and fos_str.strip():
        standardized["ID"] = [f.strip() for f in fos_str.split(";") if f.strip()]

    # Citazioni
    refs_str = str(raw_record.get("References", ""))
    if refs_str and refs_str.strip():
        standardized["CR"] = [r.strip() for r in refs_str.split(";") if r.strip()]

    # Affiliazioni
    aff_str = str(raw_record.get("Affiliations", ""))
    if aff_str and aff_str.strip():
        standardized["C1"] = [aff.strip() for aff in aff_str.split(";") if aff.strip()]

    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# 8.  TRANSFORM DISPATCHER  (Strategy / Registry Pattern)
# -----------------------------------------------------------------------------
# Il "Vigile Urbano" (Design Pattern: Strategy / Registry)
#
# Questo dizionario è il segreto che rende il programma incredibilmente facile da 
# aggiornare. Associa semplicemente il nome di ogni database (la chiave) alla sua 
# funzione "Operaio Specializzato" (il valore).

_TRANSFORM_DISPATCHER: dict[str, Any] = {
    "WEB_OF_SCIENCE": transform_wos_record,
    "SCOPUS":         transform_scopus_record,
    "PUBMED":         transform_pubmed_record,
    "OPENALEX":       transform_openalex_record,
    "OPENALEX_CSV":   transform_openalex_csv_record,
    "DIMENSIONS":     transform_dimensions_record,
    "COCHRANE":       transform_cochrane_record,
    "LENS":           transform_lens_record,
}


# -----------------------------------------------------------------------------
# 9.  VALIDATION  (Phase 5)
# -----------------------------------------------------------------------------

class ValidationError(Exception):
    """
    Allarme Dati Sporchi (Eccezione personalizzata).

    Crea un tipo di errore specifico per il nostro programma. Invece di lanciare 
    un generico errore di sistema (che farebbe pensare a un bug del codice), 
    questo allarme dice chiaramente all'operatore: "Attenzione, il codice funziona 
    benissimo, ma i dati che stai cercando di inserire sono corrotti o fuori standard".
    """
    pass


def validate_record(record: dict) -> None:
    """
    L'"Ispezione Finale": verifica che il record sia assolutamente perfetto.

    Questa funzione è il casello di controllo prima di mandare i dati alle vere e 
    proprie analisi di Bibliometrix (Fase 3: Load). Esegue un triplo controllo di 
    sicurezza su ogni singola colonna del record.

    I 3 Controlli:
    1. L'Appello (Presence check): Controlla che tutte le etichette obbligatorie 
       richieste dal Contratto di Tipo esistano davvero.
    2. Il Controllo Vuoti (Null check): Usa gli strumenti di Pandas per scovare 
       eventuali 'NaN' o 'None' sfuggiti alla pulizia. (Nota tecnica: le liste 
       sono sicure per natura, quindi ignora i falsi allarmi su di esse).
    3. Il Controllo di Identità (Type check): Verifica che il tipo di dato sia 
       esattamente quello promesso (es. se si aspetta un numero, non deve esserci una parola).

    La strategia "Raccogli e Segnala":
    Invece di bloccarsi e urlare al primissimo errore trovato, la funzione si annota 
    tutti i problemi del record su un taccuino (`errors`). Alla fine, se ci sono stati 
    intoppi, lancia un unico allarme con la lista completa. Questo fa risparmiare 
    tantissimo tempo a chi deve correggere i dati, perché vede tutti gli errori in una volta sola.

    Args:
        record: Un dizionario appena uscito da una delle funzioni di trasformazione.

    Raises:
        ValidationError: Se anche uno solo dei tre controlli fallisce.
    """
    errors: list[str] = []

    for tag, expected_type in COLUMN_TYPE_CONTRACTS.items():
        # 1. L'Appello (Presenza)
        if tag not in record:
            errors.append(f"[MISSING_COLUMN] Tag '{tag}' assente nel record.")
            continue

        val = record[tag]

        # 2. Il Controllo Vuoti (Cerca NaN / None)
        try:
            if pd.isna(val):
                errors.append(
                    f"[NULL_VALUE] Tag '{tag}' contiene NaN/None."
                )
                continue
        except (TypeError, ValueError):
            # Le liste fanno arrabbiare pd.isna scatenando un TypeError. 
            # Ma siccome una lista per noi non è mai "nulla" (al massimo è []), 
            # possiamo tranquillamente ignorare questo falso allarme.
            pass

        # 3. Il Controllo di Identità (Tipo corretto)
        if not isinstance(val, expected_type):
            errors.append(
                f"[TYPE_ERROR] Tag '{tag}': atteso {expected_type.__name__}, "
                f"trovato {type(val).__name__} (valore: {repr(val)[:60]})."
            )

    # Se il taccuino degli errori non è vuoto, fa suonare l'allarme
    if errors:
        raise ValidationError(
            f"Validazione fallita con {len(errors)} errore/i:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )


# -----------------------------------------------------------------------------
# 10.  CSV SERIALISATION
# -----------------------------------------------------------------------------

def serialize_for_csv(record: dict) -> dict:
    """
    L'"Imballatore per l'Esportazione" in CSV.

    Quando devi salvare i dati in un file piatto (come un CSV da aprire in Excel), 
    Pandas va in confusione se dentro una cella trova una lista Python vera e propria. 
    Finirebbe per salvare roba illeggibile o farebbe crashare il salvataggio.

    Questa funzione interviene appena prima dell'esportazione: prende tutte le liste 
    (es. gli autori) e le "schiaccia" in un unico testo separato da un punto e virgola 
    (es. da ["Rossi", "Bianchi"] a "Rossi;Bianchi"). 
    I testi normali e i numeri vengono lasciati in pace.
    """
    serialized = {}
    for tag, val in record.items():
        if isinstance(val, list):
            serialized[tag] = CSV_DELIMITER.join(str(item) for item in val)
        else:
            serialized[tag] = val
    return serialized


# -----------------------------------------------------------------------------
# 11.  PRIMARY ENTRY POINT: convert2df()
# -----------------------------------------------------------------------------

def convert2df(
    raw_records: list[dict],
    source: str = "OPENALEX",
    validate: bool = True,
    for_csv_export: bool = False,
) -> pd.DataFrame:
    """
    Il "Direttore Generale" della Fabbrica (Punto di Accesso Principale).

    Questa è la funzione più importante del modulo: è l'equivalente diretto della 
    storica funzione `convert2df()` in R. Nasconde tutta la complessità del sistema 
    (smistamento, traduzione, validazione) dietro un'unica semplice interfaccia. 
    L'utente finale deve solo chiamare questa funzione e riceverà un DataFrame perfetto.
    
    1. Auto-Riconoscimento OpenAlex: Se l'utente dice "OPENALEX", la funzione guarda il primo
       record e capisce da sola se è un JSON complicato (dalle API) o un CSV piatto. 
       Questo evita all'utente di dover specificare manualmente la differenza.
       
    2. Delega al Dispatcher: Usa il nostro "Vigile Urbano" per capire immediatamente 
       a quale funzione di trasformazione inviare i dati, rispettando il principio Open/Closed.
       
    3. Tolleranza agli Errori (Best-Effort): Se stai analizzando 10.000 articoli e uno 
       è corrotto, il sistema non va in crash buttando via tutto il lavoro. Registra 
       l'errore per quel singolo record, lo salta, e procede con gli altri 9.999.
       
    4. Ordine Ferreo delle Colonne: Indipendentemente da come arrivano i dati, il 
       DataFrame finale avrà sempre le colonne nello stesso identico ordine ufficiale WoS.
       
    5. Protezione Bug Pandas: Se a un DataFrame viene assegnata una lista vuota `[]` in modo 
       ingenuo, Pandas assegna *la stessa* lista a tutte le righe (creando un disastro 
       se provi a modificarne una). Questa funzione usa un "trucco" (una list comprehension) 
       per creare una lista unica e indipendente per ogni singola riga.

    Args:
        raw_records:    I dati grezzi estratti nella Fase 1.
        source:         Il nome del database (es. "SCOPUS"). Non importa se è minuscolo.
        validate:       Se True, fa passare l'ispezione finale a ogni record.
        for_csv_export: Se True, chiama l'"Imballatore" per convertire le liste in testo.

    Returns:
        Un DataFrame Pandas perfettamente formattato, tipizzato e ordinato.
    """
    source_upper = source.upper()

    if source_upper == "OPENALEX" and raw_records:
        # Capisce da solo se OpenAlex è formato JSON o formato CSV guardando le chiavi
        first_record = raw_records[0]
        if "authorships" not in first_record and ("author_display_names" in first_record or "publication_year" in first_record):
            source_upper = "OPENALEX_CSV"

    if source_upper not in _TRANSFORM_DISPATCHER:
        registered = list(_TRANSFORM_DISPATCHER.keys())
        raise ValueError(
            f"Sorgente '{source}' non registrata nel Dispatcher. "
            f"Sorgenti disponibili: {registered}"
        )

    transform_fn = _TRANSFORM_DISPATCHER[source_upper]

    standardized_records: list[dict] = []
    for idx, raw in enumerate(raw_records):
        try:
            record = transform_fn(raw)
        except Exception as exc:
            print(f"[ERROR] Trasformazione fallita per il record {idx}: {exc}")
            continue

        if validate:
            try:
                validate_record(record)
            except ValidationError as ve:
                print(f"[WARN] Validazione fallita per il record {idx}:\n{ve}")
                # Modalità Best-Effort: se un record fallisce la validazione, stampa l'avviso
                # ma continua. Per far crashare il programma al primo errore, usa 'raise'.

        if for_csv_export:
            record = serialize_for_csv(record)

        standardized_records.append(record)

    # L'ordine delle colonne è dettato dai Contratti di Tipo (COLUMN_TYPE_CONTRACTS)
    column_order = list(COLUMN_TYPE_CONTRACTS.keys())

    if not standardized_records:
        return pd.DataFrame(columns=column_order)

    df = pd.DataFrame(standardized_records)

    # Assicura che tutte le colonne esistano, anche se i record non avevano quei dati
    for col in column_order:
        if col not in df.columns:
            if for_csv_export:
                df[col] = ""  # Nel formato CSV, tutto deve essere stringa
            else:
                default_val = _TYPE_DEFAULTS[COLUMN_TYPE_CONTRACTS[col]]
                # Protezione anti-bug Pandas: genera una lista NUOVA per ogni riga
                if isinstance(default_val, list):
                    df[col] = [[] for _ in range(len(df))]
                else:
                    df[col] = default_val

    # =========================================================================
    # FASE 4: CAMPI CALCOLATI (La Short Reference - SR)
    # =========================================================================
    # Cerca di usare la funzione SR originale di Bibliometrix.
    # Se non la trova, usa un Piano B di emergenza (Fallback).
    try:
        from www.services.metatagextraction import SR
        df = SR(df)
        
    except ImportError:
        print("[WARN] Funzione SR non trovata in www.services.metatagextraction. Applicazione fallback.")
        if not df.empty:
            # Piano B per la costruzione della SR: PrimoAutore, Anno, Rivista.
            first_author = df["AU"].apply(
                lambda x: x[0].split(",")[0].strip() if isinstance(x, list) and len(x) > 0 
                else (str(x).split(";")[0].split(",")[0].strip() if isinstance(x, str) and str(x).strip() else "Unknown")
            )
            df["SR"] = first_author + ", " + df["PY"].astype(str) + ", " + df["SO"].astype(str)
            df["SR"] = df["SR"].str.strip(", ")

    # Restituisce il DataFrame con le colonne rigorosamente in ordine
    return df[column_order]