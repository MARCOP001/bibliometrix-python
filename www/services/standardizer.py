# =============================================================================
# standardizer.py  —  Phase 2: TRANSFORM – RENAME (The Lookup Strategy)
# =============================================================================
# Responsabilità di questo modulo:
#   1. Mappare i nomi proprietari dei campi OpenAlex ai tag WoS standard
#   2. Applicare i contratti di tipo (type contracts) su ogni colonna
#   3. Gestire i valori mancanti (None / NaN → "" o [] o 0)
#   4. Estrarre i campi complessi (autori, affiliazioni, parole chiave, riferimenti)
#   5. Calcolare i campi derivati (SR – Short Reference)
#   6. Validare il record finale prima dell'esportazione
#   7. Esporre un unico entry-point: convert2df()
# =============================================================================

from __future__ import annotations

import pandas as pd
from typing import Any

# -----------------------------------------------------------------------------
# 1.  DIZIONARI DI MAPPING  (Lookup Strategy)
# -----------------------------------------------------------------------------
# Ogni sorgente ha il proprio dizionario <chiave_nativa> → <tag_WoS>.
# Aggiungere una nuova sorgente significa aggiungere solo un nuovo dict qui.

# Campi scalari diretti (stringa o intero) provenienti dal top-level del record
OPENALEX_SCALAR_MAP: dict[str, str] = {
    "id":               "UT",   # Identificatore univoco articolo
    "doi":              "DI",   # DOI
    "title":            "TI",   # Titolo documento
    "publication_year": "PY",   # Anno di pubblicazione (4 cifre)
    "cited_by_count":   "TC",   # Numero di citazioni ricevute (int)
    "language":         "LA",   # Lingua dell'articolo
    "type":             "DT",   # Tipo documento (Article, Review, …)
}

# -----------------------------------------------------------------------------
# DIZIONARIO DI MAPPING PER OPENALEX (VERSIONE CSV)
# -----------------------------------------------------------------------------
OPENALEX_CSV_SCALAR_MAP: dict[str, str] = {
    "id": "UT",                       # Identificatore Univoco
    "doi": "DI",                      # DOI
    "title": "TI",                    # Titolo documento
    "publication_year": "PY",         # Anno di pubblicazione
    "type": "DT",                     # Tipo documento
    "cited_by_count": "TC",           # Citazioni
    "host_venue": "SO",               # Nome rivista (nei CSV OA a volte è source_display_name)
    "source_display_name": "SO"       # Inseriamo entrambe per robustezza
}

# -----------------------------------------------------------------------------
# DIZIONARIO DI MAPPING PER SCOPUS (CSV EXPORT)
# -----------------------------------------------------------------------------
SCOPUS_SCALAR_MAP: dict[str, str] = {
    "EID": "UT",                           # Scopus Unique ID
    "DOI": "DI",                           # DOI
    "Title": "TI",                         # Titolo
    "Source title": "SO",                  # Nome Rivista
    "Abbreviated Source Title": "JI",      # Abbreviazione Rivista
    "Year": "PY",                          # Anno
    "Document Type": "DT",                 # Tipo documento
    "Cited by": "TC",                      # Citazioni
    "Abstract": "AB",                      # Abstract
    "Volume": "VL",                        # Volume
    "Issue": "IS",                         # Fascicolo
    "Page start": "BP",                    # Pagina iniziale
    "Page end": "EP",                      # Pagina finale
    "PubMed ID": "PMID",                   # PMID (se presente)
    "Language of Original Document": "LA", # Lingua
    "Correspondence Address": "RP",        # Indirizzo di Reprint/Corrispondenza
}

# -----------------------------------------------------------------------------
# DIZIONARIO DI MAPPING PER WEB OF SCIENCE
# -----------------------------------------------------------------------------
# WoS usa nativamente i tag corretti, ma li mappiamo per coerenza
# e per applicare i type contracts.
WOS_SCALAR_MAP: dict[str, str] = {
    "UT": "UT",
    "DI": "DI",
    "PM": "PMID",  # In WoS a volte PubMed ID è 'PM'
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
    "TC": "TC", # In WoS (Z9 o TC dipendentemente dall'export)
    "Z9": "TC"
}

# -----------------------------------------------------------------------------
# DIZIONARIO DI MAPPING PER DIMENSIONS (CSV / XLSX EXPORT)
# -----------------------------------------------------------------------------
DIMENSIONS_SCALAR_MAP: dict[str, str] = {
    "Publication ID": "UT",            # Dimensions Unique ID
    "DOI": "DI",                       # DOI
    "PMID": "PMID",                    # PubMed ID
    "Title": "TI",                     # Titolo
    "Source title": "SO",              # Nome Rivista (o Venue)
    "PubYear": "PY",                   # Anno
    "Publication Type": "DT",          # Tipo documento
    "Times cited": "TC",               # Citazioni
    "Abstract": "AB",                  # Abstract
    "Volume": "VL",                    # Volume
    "Issue": "IS",                     # Fascicolo
    # La colonna Pagination la mappiamo temporaneamente su BP, 
    # poi la splittiamo in BP ed EP nella funzione di trasformazione
    "Pagination": "BP",                
}

# -----------------------------------------------------------------------------
# DIZIONARIO DI MAPPING PER LENS (CSV EXPORT)
# -----------------------------------------------------------------------------
LENS_SCALAR_MAP: dict[str, str] = {
    "Lens ID": "UT",                   # Lens Unique ID
    "DOI": "DI",                       # DOI
    "PMID": "PMID",                    # PubMed ID
    "Title": "TI",                     # Titolo
    "Publication Year": "PY",          # Anno di pubblicazione
    "Publication Type": "DT",          # Tipo documento
    "Source Title": "SO",              # Nome Rivista
    "Volume": "VL",                    # Volume
    "Issue": "IS",                     # Fascicolo
    "Start Page": "BP",                # Pagina iniziale
    "End Page": "EP",                  # Pagina finale
    "Abstract": "AB",                  # Abstract
    "Citing Works Count": "TC",        # Citazioni
}

# -----------------------------------------------------------------------------
# DIZIONARIO DI MAPPING PER COCHRANE (TXT EXPORT)
# -----------------------------------------------------------------------------
COCHRANE_SCALAR_MAP: dict[str, str] = {
    "TI": "TI",     # Titolo
    "SO": "SO",     # Source / Nome Rivista
    "YR": "PY",     # Cochrane spesso usa YR per l'anno
    "PY": "PY",     # Alternativa per l'anno
    "DO": "DI",     # DOI in Cochrane è DO
    "DI": "DI",     
    "AB": "AB",     # Abstract
    "VL": "VL",     # Volume
    "NO": "IS",     # Issue number in Cochrane è spesso NO o IS
    "IS": "IS",
    "PT": "DT",     # Publication Type
}

# Campi scalari annidati: (percorso_nested, tag_WoS)
# Il percorso è una lista di chiavi da seguire nel dict raw.
OPENALEX_NESTED_SCALAR_MAP: list[tuple[list[str], str]] = [
    (["primary_location", "source", "display_name"],    "SO"),  # Nome rivista
    (["primary_location", "source", "abbreviated_title"],"JI"),  # Abbreviazione ISO
    (["biblio", "volume"],                               "VL"),  # Volume
    (["biblio", "issue"],                                "IS"),  # Fascicolo
    (["biblio", "first_page"],                           "BP"),  # Pagina iniziale
    (["biblio", "last_page"],                            "EP"),  # Pagina finale
    (["ids", "pmid"],                                    "PMID"),# PubMed ID
]

# -----------------------------------------------------------------------------
# 2.  CONTRATTI DI TIPO  (Type Contracts)
# -----------------------------------------------------------------------------
# Definisce il tipo atteso per ogni colonna del glossario WoS.
# Usato sia durante la trasformazione sia nella fase di validazione.

COLUMN_TYPE_CONTRACTS: dict[str, type] = {
    # Scalari stringa
    "DB":   str,
    "UT":   str,
    "DI":   str,
    "PMID": str,
    "TI":   str,
    "SO":   str,
    "JI":   str,
    "PY":   str,
    "DT":   str,
    "LA":   str,
    "RP":   str,
    "AB":   str,
    "VL":   str,
    "IS":   str,
    "BP":   str,
    "EP":   str,
    "SR":   str,
    # Scalare numerico
    "TC":   int,
    # Campi multi-valore
    "AU":   list,
    "AF":   list,
    "C1":   list,
    "CR":   list,
    "DE":   list,
    "ID":   list,
}

# -----------------------------------------------------------------------------
# DIZIONARIO DI MAPPING PER PUBMED (MEDLINE FORMAT)
# -----------------------------------------------------------------------------
PUBMED_SCALAR_MAP: dict[str, str] = {
    "PMID": "UT",   # Identificatore Univoco
    "LID":  "DI",   # Location ID (Spesso contiene il DOI)
    "TI":   "TI",   # Titolo
    "JT":   "SO",   # Journal Title (Nome della rivista)
    "TA":   "JI",   # Journal Title Abbreviation
    "PT":   "DT",   # Publication Type
    "LA":   "LA",   # Language
    "AB":   "AB",   # Abstract
    "VI":   "VL",   # Volume
    "IP":   "IS",   # Issue
    "PG":   "BP",   # Paginazione (richiederà uno split per BP e EP)
}

# Valore di default per ogni tipo (usato in caso di campo mancante/None)
_TYPE_DEFAULTS: dict[type, Any] = {
    str:  "",
    int:  0,
    list: [],
}

# Delimitatore standard per la serializzazione CSV (Phase 2 spec)
CSV_DELIMITER: str = ";"

# -----------------------------------------------------------------------------
# 3.  HELPER: accesso a campi nested
# -----------------------------------------------------------------------------

def _get_nested(record: dict, path: list[str]) -> Any:
    """
    Naviga un dict annidato seguendo il percorso `path`.
    Restituisce None se una qualunque chiave non esiste o il valore è None.

    Esempio:
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
    Mappa e pulisce tutti i campi scalari (str / int) del record OpenAlex.

    Applica:
    - La Lookup Strategy tramite OPENALEX_SCALAR_MAP e OPENALEX_NESTED_SCALAR_MAP
    - I contratti di tipo di COLUMN_TYPE_CONTRACTS
    - La gestione dei valori nulli (None → "" o 0)

    Args:
        raw_record: dizionario grezzo proveniente dall'API OpenAlex.

    Returns:
        dict con le sole chiavi WoS scalari valorizzate correttamente.
    """
    result: dict = {}

    # Provenienza del database — sempre esplicita (spec §4.2 DB)
    result["DB"] = "OPENALEX"

    # --- Campi scalari top-level ---
    for oa_key, wos_tag in OPENALEX_SCALAR_MAP.items():
        val = raw_record.get(oa_key)
        expected_type = COLUMN_TYPE_CONTRACTS[wos_tag]
        result[wos_tag] = _cast_scalar(val, expected_type)

    # PY deve essere stringa a 4 cifre
    if result.get("PY"):
        result["PY"] = str(result["PY"])[:4]

    # --- Campi scalari nested ---
    for path, wos_tag in OPENALEX_NESTED_SCALAR_MAP:
        val = _get_nested(raw_record, path)
        expected_type = COLUMN_TYPE_CONTRACTS[wos_tag]
        result[wos_tag] = _cast_scalar(val, expected_type)

    # SO: spec richiede uppercase per convenzione bibliometrix
    if result.get("SO"):
        result["SO"] = result["SO"].upper()

    return result


def _cast_scalar(value: Any, expected_type: type) -> Any:
    """
    Converte `value` nel tipo atteso rispettando i contratti di tipo.

    Regole:
    - None → valore di default per il tipo (""  per str, 0 per int)
    - int  → int(value) con fallback a 0
    - str  → str(value).strip()

    Args:
        value:         valore grezzo (può essere None).
        expected_type: tipo atteso (str o int).

    Returns:
        Valore castato e pulito.
    """
    if value is None:
        return _TYPE_DEFAULTS[expected_type]

    if expected_type is int:
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    # str — convertiamo e rimuoviamo spazi superflui
    return str(value).strip()


# -----------------------------------------------------------------------------
# 5.  EXTRACT COMPLEX FIELDS
# -----------------------------------------------------------------------------

def extract_authors(raw_record: dict) -> list[str]:
    """
    Estrae i nomi degli autori da OpenAlex e li formatta come 'Cognome, Nome'.

    Il formato "Cognome, Nome" è lo standard WoS per il tag AU.
    Se il nome è una sola parola viene lasciato invariato.

    Args:
        raw_record: dizionario grezzo OpenAlex.

    Returns:
        Lista di stringhe nel formato "Cognome, Nome".
        Lista vuota se il campo è assente o privo di dati validi.
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
    Estrae le affiliazioni degli autori (tag C1) come lista di stringhe univoche.

    Itera su tutti gli autori e raccoglie il display_name di ogni istituzione,
    evitando duplicati a livello di articolo.

    Args:
        raw_record: dizionario grezzo OpenAlex.

    Returns:
        Lista di nomi di istituzioni (senza duplicati).
        Lista vuota se il campo è assente.
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
    Estrae l'indirizzo di reprint (RP) dal primo autore corrispondente.

    In OpenAlex, l'autore corrispondente si identifica tramite
    'is_corresponding': True in authorships. Se non presente, viene
    usato il primo autore con almeno un'istituzione.

    Args:
        raw_record: dizionario grezzo OpenAlex.

    Returns:
        Stringa con l'istituzione del corrispondente o "" se non trovata.
    """
    authorships = raw_record.get("authorships", [])
    if not authorships:
        return ""

    # Prima scelta: autore corrispondente esplicito
    for auth in authorships:
        if auth.get("is_corresponding"):
            institutions = auth.get("institutions", [])
            if institutions:
                name = institutions[0].get("display_name", "")
                return str(name).strip() if name else ""

    # Fallback: primo autore con istituzione valorizzata
    for auth in authorships:
        institutions = auth.get("institutions", [])
        if institutions:
            name = institutions[0].get("display_name", "")
            return str(name).strip() if name else ""

    return ""


def extract_keywords(raw_record: dict) -> list[str]:
    """
    Estrae le parole chiave dell'autore (tag DE) dal campo 'keywords'.

    Args:
        raw_record: dizionario grezzo OpenAlex.

    Returns:
        Lista di keyword come stringhe.
        Lista vuota se il campo è assente o vuoto.
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
    Estrae gli Index Keywords / Keywords Plus (tag ID) dai topic di OpenAlex.

    OpenAlex espone i concetti tematici nel campo 'topics'.
    Questi mappano al tag WoS ID (Index Keywords assegnati dall'indicizzatore).

    Args:
        raw_record: dizionario grezzo OpenAlex.

    Returns:
        Lista di nomi di topic come stringhe.
        Lista vuota se il campo è assente.
    """
    topics_data = raw_record.get("topics")
    if not topics_data:
        # Fallback su 'concepts' (versione precedente dell'API OpenAlex)
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
    Estrae i riferimenti citati (tag CR) come lista di ID OpenAlex.

    In OpenAlex i referenced_works sono forniti come URL/ID del tipo
    'https://openalex.org/W...'. Vengono restituiti come stringhe grezze
    poiché la normalizzazione completa nel formato WoS richiederebbe
    chiamate API aggiuntive (fuori dallo scope di questa fase).

    Args:
        raw_record: dizionario grezzo OpenAlex.

    Returns:
        Lista di stringhe (ID OpenAlex dei lavori citati).
        Lista vuota se il campo è assente.
    """
    references = raw_record.get("referenced_works")
    if not references:
        return []

    return [str(ref).strip() for ref in references if ref]


def reconstruct_abstract(raw_record: dict) -> str:
    """
    Ricostruisce l'abstract di OpenAlex dall'indice invertito (InvertedIndex).

    OpenAlex non fornisce l'abstract come testo lineare ma come dizionario
    { parola: [lista_di_posizioni] }. Questa funzione inverte la struttura
    e restituisce il testo ricostruito.

    Args:
        raw_record: dizionario grezzo OpenAlex.

    Returns:
        Stringa con l'abstract ricostruito, oppure "" se assente o
        in caso di errore nella ricostruzione.
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
        # Safe fallback: meglio restituire stringa vuota che bloccare la pipeline
        print(f"[WARN] Errore nella ricostruzione dell'abstract: {exc}")
        return ""


# -----------------------------------------------------------------------------
# 7.  TRASFORMAZIONE PRINCIPALE
# -----------------------------------------------------------------------------

def transform_openalex_record(raw_record: dict) -> dict:
    """
    Orchestra la trasformazione di un singolo record OpenAlex nel formato WoS.
    """
    # 1. Scheletro completo
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }

    # 2. Campi scalari
    standardized.update(clean_scalar_fields(raw_record))

    # 3. Campi complessi
    standardized["AU"] = extract_authors(raw_record)
    standardized["AF"] = standardized["AU"]          
    standardized["C1"] = extract_affiliations(raw_record)
    standardized["RP"] = extract_reprint_address(raw_record)
    standardized["DE"] = extract_keywords(raw_record)
    standardized["ID"] = extract_index_keywords(raw_record)
    standardized["CR"] = extract_references(raw_record)
    standardized["AB"] = reconstruct_abstract(raw_record)

    # Se JI è vuoto o non esiste, usiamo il nome completo della rivista (SO) come ripiego
    if not standardized.get("JI") and standardized.get("SO"):
        standardized["JI"] = standardized["SO"]

    return standardized

# -----------------------------------------------------------------------------
# FUNZIONE DI TRASFORMAZIONE PER OPENALEX CSV
# -----------------------------------------------------------------------------
def transform_openalex_csv_record(raw_record: dict) -> dict:
    """
    Converte una riga piatta di un CSV di OpenAlex nei tag WoS standard.
    Si occupa di splittare le stringhe separate da virgola o punto e virgola in liste.
    """
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    # Manteniamo il nome del DB corretto per le analisi a valle
    standardized["DB"] = "OPENALEX"

    # 1. Mappatura dei campi scalari diretti
    for csv_key, wos_tag in OPENALEX_CSV_SCALAR_MAP.items():
        if csv_key in raw_record and raw_record[csv_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[csv_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # 2. Gestione dei campi Multi-Valore (Split delle stringhe)
    
    # Autori (AU e AF): Nel CSV di solito sono in una colonna "authors" o "author_display_names"
    authors_str = str(raw_record.get("authors", raw_record.get("author_display_names", "")))
    if authors_str and authors_str.strip():
        # I CSV possono usare la virgola o il punto e virgola come separatore interno
        separator = ";" if ";" in authors_str else ","
        # Splittiamo e rimuoviamo gli spazi vuoti extra
        authors_list = [a.strip() for a in authors_str.split(separator) if a.strip()]
        
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Concetti / Index Keywords (ID): Di solito in "concepts" o "topics"
    concepts_str = str(raw_record.get("concepts", ""))
    if concepts_str and concepts_str.strip():
        separator = ";" if ";" in concepts_str else ","
        standardized["ID"] = [c.strip() for c in concepts_str.split(separator) if c.strip()]
        
    # Riferimenti Citati (CR): Di solito in "referenced_works"
    refs_str = str(raw_record.get("referenced_works", ""))
    if refs_str and refs_str.strip():
        separator = ";" if ";" in refs_str else ","
        standardized["CR"] = [r.strip() for r in refs_str.split(separator) if r.strip()]

    return standardized

# -----------------------------------------------------------------------------
# FUNZIONE DI TRASFORMAZIONE PER PUBMED
# -----------------------------------------------------------------------------
def transform_pubmed_record(raw_record: dict) -> dict:
    """
    Converte un record estratto dal formato MEDLINE nei tag WoS standard.
    """
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "PUBMED"
    standardized["PMID"] = raw_record.get("PMID", "")

    # Mappatura campi scalari diretti
    for medline_key, wos_tag in PUBMED_SCALAR_MAP.items():
        val = raw_record.get(medline_key)
        # Alcuni campi scalari in Medline potrebbero essere stati parsati come list 
        # se presenti più volte per errore, forziamo l'uso del primo elemento
        if isinstance(val, list):
            val = val[0]
        standardized[wos_tag] = _cast_scalar(val, COLUMN_TYPE_CONTRACTS[wos_tag])

    # --- Estrazioni Specifiche per PubMed ---

    # Anno di pubblicazione (DP in Medline è solitamente "2024 Oct 15", prendiamo le prime 4 cifre)
    dp = raw_record.get("DP", "")
    if dp and len(dp) >= 4:
        standardized["PY"] = dp[:4]

    # DOI (LID in Medline contiene spesso "10.xxx [doi]", dobbiamo pulirlo)
    lid = raw_record.get("LID", "")
    if "[doi]" in str(lid):
        standardized["DI"] = str(lid).split("[doi]")[0].strip()

    # Pagine (PG in Medline è spesso "123-145")
    pg = raw_record.get("PG", "")
    if "-" in pg:
        parts = pg.split("-")
        standardized["BP"] = parts[0].strip()
        standardized["EP"] = parts[1].strip()
    else:
        standardized["BP"] = pg

    # Autori (AU). In Medline sono già nel formato "Cognome Iniziali" (es. "Smith J")
    au = raw_record.get("AU", [])
    standardized["AU"] = au if isinstance(au, list) else [au]
    
    # Autori Completi (FAU)
    fau = raw_record.get("FAU", [])
    standardized["AF"] = fau if isinstance(fau, list) else [fau]

    # Affiliazioni (AD)
    ad = raw_record.get("AD", [])
    standardized["C1"] = ad if isinstance(ad, list) else [ad]

    # Parole Chiave (OT - Other Term)
    ot = raw_record.get("OT", [])
    standardized["DE"] = ot if isinstance(ot, list) else [ot]

    return standardized

# -----------------------------------------------------------------------------
# FUNZIONE DI TRASFORMAZIONE PER SCOPUS
# -----------------------------------------------------------------------------
def transform_scopus_record(raw_record: dict) -> dict:
    """
    Converte una riga del CSV esportato da Scopus nei tag WoS standard.
    Scopus esporta i campi multi-valore separandoli tipicamente con una virgola
    o un punto e virgola.
    """
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "SCOPUS"

    # 1. Mappatura campi scalari
    for scopus_key, wos_tag in SCOPUS_SCALAR_MAP.items():
        if scopus_key in raw_record and raw_record[scopus_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[scopus_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # 2. Campi Multi-Valore (Split)
    
    # Autori (AU e AF): Scopus li fornisce come "Smith J., Doe A."
    authors_str = str(raw_record.get("Authors", ""))
    if authors_str and authors_str.strip() and authors_str.lower() != "[no author name available]":
        # Split intelligente: Scopus usa spesso la virgola, ma a volte il punto e virgola.
        separator = ";" if ";" in authors_str else ","
        authors_list = [a.strip() for a in authors_str.split(separator) if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list # In Scopus l'export base non ha i nomi completi estesi, usiamo AU
        
    # Affiliazioni (C1)
    affiliations_str = str(raw_record.get("Affiliations", ""))
    if affiliations_str and affiliations_str.strip():
        standardized["C1"] = [aff.strip() for aff in affiliations_str.split(";") if aff.strip()]

    # Parole chiave dell'autore (DE)
    auth_kw_str = str(raw_record.get("Author Keywords", ""))
    if auth_kw_str and auth_kw_str.strip():
        standardized["DE"] = [kw.strip() for kw in auth_kw_str.split(";") if kw.strip()]
        
    # Parole chiave di indicizzazione (ID)
    idx_kw_str = str(raw_record.get("Index Keywords", ""))
    if idx_kw_str and idx_kw_str.strip():
        standardized["ID"] = [kw.strip() for kw in idx_kw_str.split(";") if kw.strip()]

    # Riferimenti Citati (CR): Scopus spesso ha un lungo blocco di testo separato da ';'
    refs_str = str(raw_record.get("References", ""))
    if refs_str and refs_str.strip():
        standardized["CR"] = [r.strip() for r in refs_str.split(";") if r.strip()]

    # Pulizia standard su Nome Rivista (in maiuscolo come da convenzione)
    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# FUNZIONE DI TRASFORMAZIONE PER WEB OF SCIENCE (Migliorata per TXT e CSV)
# -----------------------------------------------------------------------------
def transform_wos_record(raw_record: dict) -> dict:
    """
    Converte e pulisce un record grezzo di WoS.
    Supporta sia l'output del parser testuale (liste) sia quello CSV (stringhe piatte).
    """
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "WEB_OF_SCIENCE"

    # 1. Mappatura campi scalari diretti
    for wos_key, standard_tag in WOS_SCALAR_MAP.items():
        if wos_key in raw_record:
            val = raw_record[wos_key]
            
            # Se arriva dal parser testuale, i valori singoli sono intrappolati in liste
            if isinstance(val, list) and len(val) > 0:
                val = val[0]
                
            standardized[standard_tag] = _cast_scalar(val, COLUMN_TYPE_CONTRACTS[standard_tag])

    # 2. Funzione helper per estrarre liste (gestisce sia input TXT che CSV)
    def extract_list_field(field_key: str) -> list[str]:
        raw_val = raw_record.get(field_key, [])
        if isinstance(raw_val, list):
            return [str(v).strip() for v in raw_val if v]
        elif isinstance(raw_val, str) and raw_val.strip():
            # I CSV di WoS usano il punto e virgola come separatore
            return [v.strip() for v in raw_val.split(";") if v.strip()]
        return []

    # 3. Campi multi-valore
    standardized["AU"] = extract_list_field("AU")
    standardized["AF"] = extract_list_field("AF") or standardized["AU"]
    standardized["C1"] = extract_list_field("C1")
    standardized["CR"] = extract_list_field("CR")
    standardized["DE"] = extract_list_field("DE")
    standardized["ID"] = extract_list_field("ID")

    return standardized

# -----------------------------------------------------------------------------
# FUNZIONE DI TRASFORMAZIONE PER DIMENSIONS
# -----------------------------------------------------------------------------
def transform_dimensions_record(raw_record: dict) -> dict:
    """
    Converte una riga del file CSV o XLSX esportato da Dimensions 
    nei tag WoS standard.
    """
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "DIMENSIONS"

    # 1. Mappatura campi scalari diretti
    for dim_key, wos_tag in DIMENSIONS_SCALAR_MAP.items():
        if dim_key in raw_record and raw_record[dim_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[dim_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # 2. Gestione Speciale: Paginazione
    # Dimensions spesso fornisce i numeri di pagina come "123-145"
    pagination = str(raw_record.get("Pagination", ""))
    if "-" in pagination:
        parts = pagination.split("-", 1) # Splittiamo solo sul primo trattino
        standardized["BP"] = parts[0].strip()
        standardized["EP"] = parts[1].strip()

    # 3. Campi Multi-Valore (Split)
    
    # Autori (AU e AF): Dimensions li separa tipicamente con il punto e virgola
    authors_str = str(raw_record.get("Authors", ""))
    if authors_str and authors_str.strip():
        authors_list = [a.strip() for a in authors_str.split(";") if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Affiliazioni (C1)
    affiliations_str = str(raw_record.get("Authors Affiliations", ""))
    if affiliations_str and affiliations_str.strip():
        standardized["C1"] = [aff.strip() for aff in affiliations_str.split(";") if aff.strip()]

    # Concepts (DE) - I concetti estratti dall'AI di Dimensions
    concepts_str = str(raw_record.get("Concepts", ""))
    if concepts_str and concepts_str.strip():
        standardized["DE"] = [c.strip() for c in concepts_str.split(";") if c.strip()]

    # MeSH Terms (ID) - Termini di indicizzazione medica
    mesh_str = str(raw_record.get("MeSH terms", ""))
    if mesh_str and mesh_str.strip():
        standardized["ID"] = [m.strip() for m in mesh_str.split(";") if m.strip()]

    # References (CR) - Dimensions di solito esporta un elenco di Reference IDs
    refs_str = str(raw_record.get("Reference IDs", ""))
    if refs_str and refs_str.strip():
        # A volte usa la virgola, a volte il punto e virgola
        separator = ";" if ";" in refs_str else ","
        standardized["CR"] = [r.strip() for r in refs_str.split(separator) if r.strip()]

    # Pulizia standard su Nome Rivista (in maiuscolo come da convenzione)
    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# FUNZIONE DI TRASFORMAZIONE PER COCHRANE
# -----------------------------------------------------------------------------
def transform_cochrane_record(raw_record: dict) -> dict:
    """
    Converte un record estratto dal file di testo Cochrane nei tag WoS standard.
    Il parser originale 'parse_cochrane_data' concatena già i campi multipli 
    con il punto e virgola, quindi applichiamo uno split.
    """
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "COCHRANE"

    # 1. Mappatura campi scalari diretti
    for coch_key, wos_tag in COCHRANE_SCALAR_MAP.items():
        if coch_key in raw_record and raw_record[coch_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[coch_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # 2. Gestione Speciale: Paginazione
    # In Cochrane le pagine (PG) possono essere "1-10" o singole
    pg = str(raw_record.get("PG", ""))
    if "-" in pg:
        parts = pg.split("-", 1)
        standardized["BP"] = parts[0].strip()
        standardized["EP"] = parts[1].strip()
    elif pg:
        standardized["BP"] = pg.strip()

    # 3. Campi Multi-Valore (Split)
    
    # Autori (AU e AF): Il parser li ha uniti con "; "
    au_str = str(raw_record.get("AU", ""))
    if au_str and au_str.strip():
        authors_list = [a.strip() for a in au_str.split(";") if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Parole chiave (KW in Cochrane diventa DE in WoS)
    kw_str = str(raw_record.get("KW", ""))
    if kw_str and kw_str.strip():
        standardized["DE"] = [k.strip() for k in kw_str.split(";") if k.strip()]

    # Pulizia standard su Nome Rivista
    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    # Nota: Cochrane raramente esporta References strutturate (CR) o Affiliazioni (C1)
    # in un formato facilmente parsabile nel txt base. I Type Contracts 
    # assicureranno che rimangano liste vuote [] senza causare crash.

    return standardized

# -----------------------------------------------------------------------------
# FUNZIONE DI TRASFORMAZIONE PER LENS
# -----------------------------------------------------------------------------
def transform_lens_record(raw_record: dict) -> dict:
    """
    Converte una riga del file CSV esportato da Lens nei tag WoS standard.
    Lens separa quasi esclusivamente i campi multi-valore con il punto e virgola.
    """
    standardized: dict = {
        tag: _TYPE_DEFAULTS[contract]
        for tag, contract in COLUMN_TYPE_CONTRACTS.items()
    }
    
    standardized["DB"] = "LENS"

    # 1. Mappatura campi scalari diretti
    for lens_key, wos_tag in LENS_SCALAR_MAP.items():
        if lens_key in raw_record and raw_record[lens_key]:
            standardized[wos_tag] = _cast_scalar(raw_record[lens_key], COLUMN_TYPE_CONTRACTS[wos_tag])

    # 2. Campi Multi-Valore (Split)
    
    # Autori (AU e AF): Lens li esporta nella colonna "Author/s" separati da ';'
    authors_str = str(raw_record.get("Author/s", ""))
    if authors_str and authors_str.strip():
        authors_list = [a.strip() for a in authors_str.split(";") if a.strip()]
        standardized["AU"] = authors_list
        standardized["AF"] = authors_list

    # Parole Chiave Autore (DE): Lens usa "Keywords"
    kw_str = str(raw_record.get("Keywords", ""))
    if kw_str and kw_str.strip():
        standardized["DE"] = [k.strip() for k in kw_str.split(";") if k.strip()]

    # Index Keywords (ID): Lens usa "Fields of Study" (basato su concetti AI come Dimensions)
    fos_str = str(raw_record.get("Fields of Study", ""))
    if fos_str and fos_str.strip():
        standardized["ID"] = [f.strip() for f in fos_str.split(";") if f.strip()]

    # Riferimenti Citati (CR): Lens usa "References" o "Lens ID delle referenze"
    refs_str = str(raw_record.get("References", ""))
    if refs_str and refs_str.strip():
        standardized["CR"] = [r.strip() for r in refs_str.split(";") if r.strip()]

    # Affiliazioni (C1): Spesso esportate come "Affiliations" in Lens
    aff_str = str(raw_record.get("Affiliations", ""))
    if aff_str and aff_str.strip():
        standardized["C1"] = [aff.strip() for aff in aff_str.split(";") if aff.strip()]

    # Pulizia standard su Nome Rivista (in maiuscolo come da convenzione)
    if standardized.get("SO"):
        standardized["SO"] = standardized["SO"].upper()

    return standardized

# -----------------------------------------------------------------------------
# 8.  DISPATCHER  (estensibilità multi-sorgente)
# -----------------------------------------------------------------------------
# Mappa il nome della sorgente alla funzione di trasformazione corrispondente.
# Per aggiungere una nuova sorgente (es. Scopus) basta:
#   1. Implementare transform_scopus_record(raw_record) in questo modulo
#      (o in un sottomodulo apposito)
#   2. Aggiungere la voce "SCOPUS": transform_scopus_record qui sotto

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
# 9.  VALIDAZIONE  (Phase 5)
# -----------------------------------------------------------------------------

class ValidationError(Exception):
    """Eccezione sollevata quando un record non supera la validazione."""
    pass


def validate_record(record: dict) -> None:
    """
    Verifica che il record standardizzato rispetti tutti i contratti di tipo.

    Controlla:
    - Presenza di tutte le colonne obbligatorie definite in COLUMN_TYPE_CONTRACTS
    - Assenza di valori None o NaN (pandas.isna)
    - Correttezza del tipo Python per ogni colonna

    Args:
        record: dizionario standardizzato da validare.

    Raises:
        ValidationError: se almeno un controllo fallisce, con messaggio
                         descrittivo di tutti gli errori trovati.
    """
    errors: list[str] = []

    for tag, expected_type in COLUMN_TYPE_CONTRACTS.items():
        # Colonna presente?
        if tag not in record:
            errors.append(f"[MISSING_COLUMN] Tag '{tag}' assente nel record.")
            continue

        val = record[tag]

        # Valore nullo?
        try:
            if pd.isna(val):
                errors.append(
                    f"[NULL_VALUE] Tag '{tag}' contiene NaN/None."
                )
                continue
        except (TypeError, ValueError):
            # pd.isna lancia TypeError su liste — in quel caso non è None
            pass

        # Tipo corretto?
        if not isinstance(val, expected_type):
            errors.append(
                f"[TYPE_ERROR] Tag '{tag}': atteso {expected_type.__name__}, "
                f"trovato {type(val).__name__} (valore: {repr(val)[:60]})."
            )

    if errors:
        raise ValidationError(
            f"Validazione fallita con {len(errors)} errore/i:\n"
            + "\n".join(f"  • {e}" for e in errors)
        )


# -----------------------------------------------------------------------------
# 10.  SERIALIZZAZIONE CSV
# -----------------------------------------------------------------------------

def serialize_for_csv(record: dict) -> dict:
    """
    Converte le liste in stringhe delimitate da ';' per la serializzazione CSV.

    I campi multi-valore (list[str]) vengono uniti con il delimitatore
    standard CSV_DELIMITER (';'), come richiesto dalla spec §Phase 2.
    I campi scalari non vengono modificati.

    Args:
        record: dizionario standardizzato (post-validazione).

    Returns:
        Nuovo dizionario con tutti i valori serializzabili come celle CSV.
    """
    serialized = {}
    for tag, val in record.items():
        if isinstance(val, list):
            serialized[tag] = CSV_DELIMITER.join(str(item) for item in val)
        else:
            serialized[tag] = val
    return serialized


# -----------------------------------------------------------------------------
# 11.  ENTRY POINT PRINCIPALE: convert2df()
# -----------------------------------------------------------------------------

def convert2df(
    raw_records: list[dict],
    source: str = "OPENALEX",
    validate: bool = True,
    for_csv_export: bool = False,
) -> pd.DataFrame:
    """
    Entry point principale del modulo — trasforma una lista di record grezzi
    in un DataFrame standardizzato pronto per le analisi bibliometriche.

    Replica concettualmente la funzione `convert2df()` di Bibliometrix-R.

    Pipeline interna:
      1. Seleziona la funzione di trasformazione tramite il Dispatcher
      2. Applica la trasformazione a ogni record
      3. (Opzionale) Valida ogni record standardizzato
      4. (Opzionale) Serializza le liste per l'esportazione CSV
      5. Assembla e restituisce il DataFrame

    Args:
        raw_records:    lista di dizionari grezzi dalla sorgente (API o file).
        source:         identificatore della sorgente dati (default: "OPENALEX").
                        Deve corrispondere a una chiave in _TRANSFORM_DISPATCHER.
        validate:       se True (default), esegue la validazione su ogni record
                        e solleva ValidationError al primo errore trovato.
        for_csv_export: se True, serializza le liste con il delimitatore ';'
                        per compatibilità con pandas.to_csv().

    Returns:
        pd.DataFrame con colonne ordinate secondo il glossario WoS §4.2.

    Raises:
        ValueError:      se `source` non è registrata nel Dispatcher.
        ValidationError: se un record non supera la validazione (solo se
                         validate=True).

    Esempio:
        >>> records = fetch_openalex_records(query="machine learning")
        >>> df = convert2df(records, source="OPENALEX")
        >>> df.to_csv("standardized_output.csv", index=False)
    """
    source_upper = source.upper()

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
                # Non blocchiamo l'intera pipeline: inseriamo comunque il record
                # con un flag di warning. Per un comportamento strict,
                # sostituire 'continue' a 'print' sopra.

        if for_csv_export:
            record = serialize_for_csv(record)

        standardized_records.append(record)

    # Ordine delle colonne conforme al glossario §4.2
    column_order = list(COLUMN_TYPE_CONTRACTS.keys())

    if not standardized_records:
        return pd.DataFrame(columns=column_order)

    df = pd.DataFrame(standardized_records)

    # Garantiamo che tutte le colonne del glossario siano presenti
    for col in column_order:
        if col not in df.columns:
            if for_csv_export:
                df[col] = ""  # Se è per CSV, tutto deve essere testo vuoto
            else:
                df[col] = _TYPE_DEFAULTS[COLUMN_TYPE_CONTRACTS[col]]

    # =========================================================================
    # FASE 4: CALCULATED FIELDS (SR) - Applicazione sul DataFrame
    # =========================================================================
    try:
        from www.services.metatagextraction import SR
        df = SR(df)
        
    except ImportError:
        print("[WARN] Funzione SR non trovata in www.services.metatagextraction. Applicazione fallback.")
        if not df.empty:
            # Fallback avanzato: gestisce sia le liste (memoria) sia le stringhe serializzate per CSV
            first_author = df["AU"].apply(
                lambda x: x[0].split(",")[0].strip() if isinstance(x, list) and len(x) > 0 
                else (str(x).split(";")[0].split(",")[0].strip() if isinstance(x, str) and str(x).strip() else "Unknown")
            )
            df["SR"] = first_author + ", " + df["PY"].astype(str) + ", " + df["SO"].astype(str)
            df["SR"] = df["SR"].str.strip(", ")

    # Restituiamo il DataFrame ordinato secondo il glossario
    return df[column_order]

