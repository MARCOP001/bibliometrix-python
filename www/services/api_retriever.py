"""
extract.py — Fase 1 (Extract) della Pipeline ETL Bibliometrix.

Output su disco:
  - OpenAlex  →  <output_dir>/openalex_<timestamp>.json
  - PubMed    →  <output_dir>/pubmed_<timestamp>.xml
"""

from __future__ import annotations

import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from urllib.parse import quote_plus

import requests
from .parsers import parse_pubmed_xml_node
from .parsers import parse_pubmed_medline_text, parse_wos_data, parse_cochrane_data

# ---------------------------------------------------------------------------
# Configurazione globale
# ---------------------------------------------------------------------------

MAILTO: str = os.environ.get("BIBLIOMETRIX_EMAIL", "aniello.il.gay@viva_cazzo.it")
DEFAULT_PER_PAGE: int = 25
DEFAULT_MAX_RETRIES: int = 3
_PAGE_SLEEP: float = 0.35          # ≤ 3 req/s su PubMed
_OUTPUT_DIR: Path = Path("data/raw")  # cartella di output di default

# ---------------------------------------------------------------------------
# LIVELLO 1 — Costruttori URL
# ---------------------------------------------------------------------------

def build_openalex_url(
    query: str,
    cursor: str = "*",
    per_page: int = DEFAULT_PER_PAGE,
    only_with_abstract: bool = True,
) -> str:
    """
    Costruisce l'URL per OpenAlex Works Search.
    Se only_with_abstract=True aggiunge filter=has_abstract:true,
    molto utile per pipeline bibliometriche.
    """
    encoded_query = quote_plus(query)
    url = (
        f"https://api.openalex.org/works"
        f"?search={encoded_query}"
        f"&cursor={cursor}"
        f"&per-page={per_page}"
        f"&mailto={MAILTO}"
    )
    if only_with_abstract:
        url += "&filter=has_abstract:true"
    return url


def build_pubmed_search_url(
    query: str, retstart: int, retmax: int = DEFAULT_PER_PAGE
) -> str:
    """Cerca gli PMID su PubMed (risposta JSON)."""
    encoded_query = quote_plus(query)
    return (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={encoded_query}&retstart={retstart}&retmax={retmax}"
        f"&retmode=json&email={MAILTO}"
    )


def build_pubmed_fetch_url(id_list: List[str]) -> str:
    """Scarica i record completi in formato XML dato un elenco di PMID."""
    ids = ",".join(id_list)
    return (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&id={ids}&retmode=xml&email={MAILTO}"
    )

# ---------------------------------------------------------------------------
# LIVELLO 2 — Fetcher con retry e backoff esponenziale
# ---------------------------------------------------------------------------

def fetch_data_with_retries(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    response_format: str = "json",
) -> Optional[Union[Dict, str]]:
    """
    Scarica un URL con gestione automatica di:
      - Rate-limit 429 (rispetta l'header Retry-After)
      - Errori server 5xx (backoff esponenziale)
      - Timeout / problemi di rete

    Restituisce dict (JSON) o str (XML/testo) oppure None se tutti i tentativi falliscono.
    """
    headers: Dict[str, str] = {
        "User-Agent": f"bibliometrix-python/1.0 (mailto:{MAILTO})"
    }
    if response_format == "json":
        headers["Accept"] = "application/json"

    for attempt in range(max_retries):
        wait_time: float = 2 ** attempt
        try:
            preview = url[:90] + ("..." if len(url) > 90 else "")
            print(f"  -> GET {preview} (tentativo {attempt + 1}/{max_retries})")
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                return response.json() if response_format == "json" else response.text

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", wait_time))
                print(f"  -> 429 Rate limit. Attendo {retry_after:.0f}s...")
                time.sleep(retry_after)

            elif response.status_code in (500, 502, 503, 504):
                print(f"  -> {response.status_code} Errore server. Attendo {wait_time:.0f}s...")
                time.sleep(wait_time)

            else:
                print(f"  -> Errore {response.status_code}: {response.text[:120]}")
                return None

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            print(f"  -> Errore di rete ({type(exc).__name__}). Attendo {wait_time:.0f}s...")
            time.sleep(wait_time)

    print("  [FALLIMENTO] Impossibile raggiungere l'endpoint dopo tutti i tentativi.")
    return None

# ---------------------------------------------------------------------------
# LIVELLO 3 — Salvataggio su disco
# ---------------------------------------------------------------------------

def _ensure_output_dir(output_dir: Path) -> None:
    """Crea la cartella di output se non esiste."""
    output_dir.mkdir(parents=True, exist_ok=True)


def save_openalex_json(results: List[Dict], output_dir: Path) -> Path:
    """Serializza la lista di works OpenAlex in un file JSON."""
    _ensure_output_dir(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"openalex_{timestamp}.json"
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"\n[SALVATAGGIO] OpenAlex JSON → {filepath}  ({len(results)} record)")
    return filepath


def save_pubmed_xml(articles_xml: List[str], output_dir: Path) -> Path:
    """
    Avvolge tutti gli articoli XML in un tag radice <PubmedArticleSet>
    e salva il file .xml, pronto per essere riletto con ET.parse().
    """
    _ensure_output_dir(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"pubmed_{timestamp}.xml"

    root = ET.Element("PubmedArticleSet")
    for raw in articles_xml:
        try:
            root.append(ET.fromstring(raw))
        except ET.ParseError as exc:
            print(f"  -> Articolo ignorato per errore XML: {exc}")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")          # indentazione leggibile (Python ≥ 3.9)
    tree.write(filepath, encoding="unicode", xml_declaration=True)
    print(f"[SALVATAGGIO] PubMed XML → {filepath}  ({len(articles_xml)} record)")
    return filepath

# ---------------------------------------------------------------------------
# LIVELLO 4 — Orchestratori interattivi
# ---------------------------------------------------------------------------

def extract_openalex_data(
    query: str,
    output_dir: Path = _OUTPUT_DIR,
    only_with_abstract: bool = True,
    max_results: int = 100, 
) -> List[Dict]:
    """
    Estrae i works da OpenAlex (paginazione cursor-based).
    Dopo ogni pagina chiede conferma per continuare.
    Al termine salva il file JSON e restituisce la lista dei record.
    """
    sep = "=" * 70
    print(f"\n{sep}\nESTRAZIONE OPENALEX — query: '{query}'\n{sep}")

    all_results: List[Dict] = []
    cursor: str = "*"
    page_num: int = 1

    while True:
        print(f"\n--- Pagina {page_num} ---")
        url = build_openalex_url(query, cursor=cursor, only_with_abstract=only_with_abstract)
        data = fetch_data_with_retries(url, response_format="json")

        if not data or not data.get("results"):
            print("  -> Nessun risultato o risposta vuota. Fine estrazione.")
            break

        results: List[Dict] = data["results"]
        all_results.extend(results)
        total_available = data.get("meta", {}).get("count", "?")
        print(
            f"  -> Estratti {len(results)} works "
            f"(totale: {len(all_results)} / {total_available} disponibili)"
        )

        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor or len(all_results) >= max_results:
            print(f"  -> Raggiunto limite o fine risultati. Dataset completato.")
            break
        
        time.sleep(_PAGE_SLEEP)
        page_num += 1

    if all_results:
        save_openalex_json(all_results, output_dir)
    else:
        print("  [ATTENZIONE] Nessun dato estratto. Nessun file salvato.")

    return all_results


def extract_pubmed_data(
    query: str,
    output_dir: Path = _OUTPUT_DIR,
    only_with_abstract: bool = True, # mantenuto per coerenza di firma
    max_results: int = 100, 
) -> List[Dict]:
    """
    Estrae i record da PubMed (paginazione offset-based, risposta XML).
    L'estrazione è completamente automatizzata per essere usata tramite Dashboard.
    Si ferma automaticamente al raggiungimento di max_results.
    Al termine salva un file XML con tutti gli articoli e restituisce
    la lista di dict parsati (formato Medline).
    """
    sep = "=" * 70
    print(f"\n{sep}\nESTRAZIONE PUBMED — query: '{query}'\n{sep}")

    all_results: List[Dict] = []
    raw_xml_list: List[str] = []   # usato solo per il salvataggio finale
    offset: int = 0
    page_num: int = 1

    while True:
        print(f"\n--- Pagina {page_num} ---")

        # 1. Recupera gli PMID (JSON)
        search_url = build_pubmed_search_url(query, retstart=offset)
        search_data = fetch_data_with_retries(search_url, response_format="json")

        if not search_data:
            print("  -> Ricerca PMID fallita. Interruzione.")
            break

        esearch = search_data.get("esearchresult", {})
        id_list: List[str] = esearch.get("idlist", [])
        total_available: str = esearch.get("count", "?")

        if not id_list:
            print("  -> Nessun PMID trovato. Fine dataset.")
            break

        # Pausa tra la ricerca e il fetch (rispetta i 3 req/s di NCBI)
        time.sleep(_PAGE_SLEEP)

        # 2. Scarica i record completi (XML)
        fetch_url = build_pubmed_fetch_url(id_list)
        xml_data: Optional[str] = fetch_data_with_retries(fetch_url, response_format="xml")

        if not xml_data:
            print("  -> Fetch XML fallito. Interruzione.")
            break

        try:
            root = ET.fromstring(xml_data)
            articles = root.findall(".//PubmedArticle")
            
            # Salviamo le stringhe XML grezze per l'output su disco
            batch_raw_xml = [ET.tostring(art, encoding="unicode") for art in articles]
            raw_xml_list.extend(batch_raw_xml)
            
            # Generiamo i dizionari Medline per la pipeline in memoria
            batch_parsed = [parse_pubmed_xml_node(art) for art in articles]
            all_results.extend(batch_parsed)
            
            print(
                f"  -> Estratti {len(batch_parsed)} articoli XML "
                f"(totale: {len(all_results)} / {total_available} disponibili)"
            )
        except ET.ParseError as exc:
            print(f"  -> Errore nel parsing dell'XML: {exc}. Interruzione.")
            break

        # --- LE TUE MODIFICHE SONO QUI ---
        
        # 1. Se abbiamo raggiunto o superato il limite richiesto, ci fermiamo
        if len(all_results) >= max_results:
            print(f"  -> Raggiunto limite richiesto di {max_results} risultati. Completato.")
            break
            
        # 2. Se l'API ha restituito meno risultati del previsto per una pagina, 
        # significa che abbiamo esaurito gli articoli sul server
        if len(id_list) < DEFAULT_PER_PAGE:
            print("  -> Nessun altro articolo disponibile sul server. Completato.")
            break

        # Niente più input() utente! Incrementiamo per il prossimo giro
        offset += DEFAULT_PER_PAGE
        page_num += 1
        time.sleep(_PAGE_SLEEP)

    if raw_xml_list:
        # Tronca i file salvati se per caso nell'ultima pagina abbiamo sforato il max_results
        save_pubmed_xml(raw_xml_list[:max_results], output_dir)
    else:
        print("  [ATTENZIONE] Nessun dato estratto. Nessun file salvato.")

    # Tronca la lista in memoria per rispettare esattamente il max_results
    return all_results[:max_results]

# ---------------------------------------------------------------------------
# ENTRY POINT UNIFICATO
# ---------------------------------------------------------------------------

def extract_data(
    query: str,
    source: str,
    output_dir: Union[str, Path] = _OUTPUT_DIR,
) -> List[Dict]:
    """
    Punto di ingresso pubblico.

    Parametri
    ----------
    query       : stringa di ricerca bibliografica
    source      : "openalex" oppure "pubmed"
    output_dir  : cartella dove scrivere i file grezzi (default: data/raw)

    Restituisce
    -----------
    Lista di dict con i record estratti.
    Salva anche i file su disco nella output_dir.
    """
    output_path = Path(output_dir)
    normalized = source.lower().strip()

    dispatch: Dict[str, object] = {
        "openalex": lambda q: extract_openalex_data(q, output_dir=output_path),
        "pubmed":   lambda q: extract_pubmed_data(q, output_dir=output_path),
    }

    if normalized not in dispatch:
        raise ValueError(
            f"Sorgente '{source}' non supportata. Usa 'openalex' oppure 'pubmed'."
        )

    return dispatch[normalized](query)


# ---------------------------------------------------------------------------
# ESECUZIONE DIRETTA (per test rapidi)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    query_test = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "machine learning bibliometrics"
    print(f"Query di test: '{query_test}'")

    for src in ("openalex", "pubmed"):
        records = extract_data(query_test, source=src)
        print(f"\n→ {src}: {len(records)} record estratti.\n")