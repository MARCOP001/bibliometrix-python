"""
extract.py — Fase 1 (Extract) della Pipeline ETL Bibliometrix.

Responsabilità del modulo:
  - Interrogare le API di OpenAlex e PubMed tramite query bibliografiche.
  - Gestire la paginazione, il rate-limiting e gli errori di rete in modo robusto.
  - Persistere i dati grezzi su disco in formato JSON (OpenAlex) e XML (PubMed).
  - Restituire i record parsati come lista di dizionari alla pipeline downstream.

Architettura a livelli:
  Livello 1 — Costruttori URL   : Prepara gli indirizzi web esatti per interrogare i database partendo dalla ricerca dell'utente.
  Livello 2 — Fetcher HTTP      : Si collega a internet per scaricare i dati. Include un sistema di sicurezza: se la connessione fallisce o il server è bloccato, aspetta qualche secondo e riprova in automatico.
  Livello 3 — Persistenza       : Prende i file scaricati dalla rete e li salva fisicamente sul computer in formato JSON o XML per non perderli.
  Livello 4 — Orchestratori     : È il "cervello" del programma. Fa lavorare insieme i livelli precedenti, gestisce il cambio pagina (paginazione) e decide quando fermare l'estrazione dei dati..

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

# ---------------------------------------------------------------------------
# Configurazione globale
# ---------------------------------------------------------------------------

# L'indirizzo email è richiesto dalle policy di utilizzo sia di OpenAlex che
# di NCBI: viene incluso in ogni richiesta per identificare il chiamante.
# La lettura dalla variabile d'ambiente evita di codificare dati sensibili
# direttamente nel sorgente (principio del "no hardcoded credentials").
MAILTO: str = os.environ.get("BIBLIOMETRIX_EMAIL", "aniellomarcorobe@progetto.it")

DEFAULT_PER_PAGE: int = 25       # Numero di record per richiesta (batch size)
DEFAULT_MAX_RETRIES: int = 3     # Numero massimo di tentativi per richiesta fallita

# Pausa minima tra richieste consecutive per rispettare il limite di
# 3 req/s imposto dalle E-Utilities di NCBI senza bisogno di API key.
_PAGE_SLEEP: float = 0.35

_OUTPUT_DIR: Path = Path("data/raw")  # Directory di output predefinita


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

    La paginazione cursor-based di OpenAlex garantisce la coerenza del dataset
    anche se l'indice viene aggiornato durante l'iterazione: il cursore "*"
    indica l'inizio della sequenza, mentre i valori successivi sono opachi e
    restituiti dal campo meta.next_cursor di ogni risposta.

    Args:
        query:               Stringa di ricerca bibliografica (verrà URL-encoded).
        cursor:              Token di paginazione corrente (default "*" = prima pagina).
        per_page:            Numero di record per pagina (max 200 per OpenAlex).
        only_with_abstract:  Se True, esclude i record privi di abstract.

    Returns:
        URL completo e pronto per la richiesta GET.
    """
    encoded_query = quote_plus(query)
    url = (
        f"https://api.openalex.org/works"
        f"?search={encoded_query}"
        f"&cursor={cursor}"
        f"&per-page={per_page}"
        f"&mailto={MAILTO}"
    )
    # Il filtro has_abstract viene applicato opzionalmente: nelle pipeline
    # bibliometriche l'abstract è spesso prerequisito per l'analisi testuale.
    if only_with_abstract:
        url += "&filter=has_abstract:true"
    return url


def build_pubmed_search_url(
    query: str, retstart: int, retmax: int = DEFAULT_PER_PAGE
) -> str:
    """
    Genera l'URL per l'endpoint esearch delle NCBI E-Utilities.

    Questo endpoint restituisce esclusivamente una lista di PMID (PubMed IDs),
    non i record completi. Il recupero del contenuto bibliografico è demandato
    a efetch (vedi build_pubmed_fetch_url). Il formato JSON è preferito a XML
    per semplicità di parsing lato client.

    Args:
        query:     Stringa di ricerca in sintassi PubMed (verrà URL-encoded).
        retstart:  Offset di paginazione (0 = prima pagina).
        retmax:    Numero massimo di PMID da restituire per questa richiesta.

    Returns:
        URL completo per esearch in formato JSON.
    """
    encoded_query = quote_plus(query)
    return (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={encoded_query}&retstart={retstart}&retmax={retmax}"
        f"&retmode=json&email={MAILTO}"
    )


def build_pubmed_fetch_url(id_list: List[str]) -> str:
    """
    Genera l'URL per l'endpoint efetch delle NCBI E-Utilities.

    I PMID vengono concatenati con virgola, come richiesto dall'API per le
    richieste batch. Il formato XML è obbligatorio per ottenere lo schema
    Medline completo con tutti i campi bibliografici disponibili.

    Args:
        id_list:  Lista di PMID (stringa) da recuperare.

    Returns:
        URL completo per efetch in formato XML.
    """
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
    Esegue una richiesta GET con gestione robusta degli errori e retry automatico.

    Strategia di retry differenziata per tipo di errore:
      - 429 (Rate Limit) : rispetta l'header Retry-After restituito dal server.
      - 5xx (Errore server): applica backoff esponenziale (2^attempt secondi).
      - Errori di rete   : applica lo stesso backoff esponenziale dei 5xx.
      - 4xx non-429      : errore permanente, nessun retry (return None immediato).

    Args:
        url:             URL da richiedere.
        max_retries:     Numero massimo di tentativi prima di arrendersi.
        response_format: "json" per deserializzare la risposta, qualsiasi altro
                         valore per restituire il testo grezzo (es. XML).

    Returns:
        dict se response_format == "json", str altrimenti.
        Restituisce None se tutti i tentativi falliscono.
    """
    headers: Dict[str, str] = {
        # Lo User-Agent identifica il client alle API, utile per la diagnostica
        # e richiesto esplicitamente da alcune policy (es. OpenAlex).
        "User-Agent": f"bibliometrix-python/1.0 (mailto:{MAILTO})"
    }
    if response_format == "json":
        headers["Accept"] = "application/json"

    for attempt in range(max_retries):
        # Il tempo di attesa cresce esponenzialmente: 1s, 2s, 4s...
        # Questo pattern riduce il rischio di aggravare un server già sovraccarico.
        wait_time: float = 2 ** attempt
        try:
            preview = url[:90] + ("..." if len(url) > 90 else "")
            print(f"  -> GET {preview} (tentativo {attempt + 1}/{max_retries})")
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                return response.json() if response_format == "json" else response.text

            if response.status_code == 429:
                # Priorità all'header Retry-After: il server conosce il proprio
                # stato meglio di qualsiasi euristica locale di backoff.
                retry_after = float(response.headers.get("Retry-After", wait_time))
                print(f"  -> 429 Rate limit. Attendo {retry_after:.0f}s...")
                time.sleep(retry_after)

            elif response.status_code in (500, 502, 503, 504):
                print(f"  -> {response.status_code} Errore server. Attendo {wait_time:.0f}s...")
                time.sleep(wait_time)

            else:
                # Errori 4xx (escluso 429): il problema è nella richiesta stessa,
                # non nel server, quindi un retry non porterebbe a risultati diversi.
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
    """
    Garantisce l'esistenza della directory di output in modo idempotente.

    L'uso di parents=True ed exist_ok=True rende la funzione sicura da
    chiamare ripetutamente: non solleva eccezioni se la directory (o parte
    del suo percorso) esiste già.
    """
    output_dir.mkdir(parents=True, exist_ok=True)


def save_openalex_json(results: List[Dict], output_dir: Path) -> Path:
    """
    Serializza la lista di works OpenAlex in un file JSON con timestamp univoco.

    Il timestamp nel nome del file previene sovrascritture tra esecuzioni
    successive e consente la tracciabilità temporale dei dataset estratti.
    ensure_ascii=False preserva i caratteri Unicode tipici dei metadati
    accademici internazionali (es. caratteri accentati, CJK, greco).

    Args:
        results:    Lista di dizionari da serializzare.
        output_dir: Directory di destinazione.

    Returns:
        Path del file JSON creato.
    """
    _ensure_output_dir(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"openalex_{timestamp}.json"
    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2)
    print(f"\n[SALVATAGGIO] OpenAlex JSON → {filepath}  ({len(results)} record)")
    return filepath


def save_pubmed_xml(articles_xml: List[str], output_dir: Path) -> Path:
    """
    Avvolge i record PubMed in un documento XML canonico e lo salva su disco.

    L'elemento radice <PubmedArticleSet> è conforme alla DTD ufficiale PubMed,
    rendendo il file compatibile con tool di analisi bibliometrica standard.
    Il parsing individuale per articolo isola eventuali record malformati:
    un singolo errore XML non pregiudica il salvataggio dell'intero batch.

    Args:
        articles_xml: Lista di stringhe XML grezze (una per articolo).
        output_dir:   Directory di destinazione.

    Returns:
        Path del file XML creato.
    """
    _ensure_output_dir(output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"pubmed_{timestamp}.xml"

    root = ET.Element("PubmedArticleSet")
    for raw in articles_xml:
        try:
            root.append(ET.fromstring(raw))
        except ET.ParseError as exc:
            # Un record malformato viene saltato con un warning: la robustezza
            # del batch è prioritaria rispetto alla completezza del singolo record.
            print(f"  -> Articolo ignorato per errore XML: {exc}")

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")          # Indentazione leggibile (Python >= 3.9)
    tree.write(filepath, encoding="unicode", xml_declaration=True)
    print(f"[SALVATAGGIO] PubMed XML → {filepath}  ({len(articles_xml)} record)")
    return filepath


# ---------------------------------------------------------------------------
# LIVELLO 4 — Orchestratori
# ---------------------------------------------------------------------------

def extract_openalex_data(
    query: str,
    output_dir: Path = _OUTPUT_DIR,
    only_with_abstract: bool = True,
    max_results: int = 100,
) -> List[Dict]:
    """
    Estrae i works da OpenAlex con paginazione cursor-based.

    La paginazione cursor-based è il metodo raccomandato da OpenAlex per
    iterare su dataset di grandi dimensioni: garantisce coerenza anche se
    l'indice viene modificato durante l'iterazione, a differenza dell'offset.

    Il ciclo si interrompe in tre condizioni:
      1. La risposta è vuota o priva del campo "results".
      2. Il server non restituisce un next_cursor (fine del dataset).
      3. Il numero di record accumulati raggiunge max_results.

    Args:
        query:              Stringa di ricerca bibliografica.
        output_dir:         Directory di output per il file JSON.
        only_with_abstract: Se True, filtra i record senza abstract.
        max_results:        Limite massimo di record da estrarre.

    Returns:
        Lista di dizionari con i metadati dei works estratti.
        Il file JSON viene salvato su disco come side-effect.
    """
    sep = "=" * 70
    print(f"\n{sep}\nESTRAZIONE OPENALEX — query: '{query}'\n{sep}")

    all_results: List[Dict] = []
    cursor: str = "*"   # Il cursore "*" indica l'inizio della sequenza paginata
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

        # Il next_cursor è None quando si è raggiunta l'ultima pagina del dataset.
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor or len(all_results) >= max_results:
            print(f"  -> Raggiunto limite o fine risultati. Dataset completato.")
            break

        time.sleep(_PAGE_SLEEP)   # Rispetto del rate-limit: max ~3 req/s
        page_num += 1

    if all_results:
        save_openalex_json(all_results, output_dir)
    else:
        print("  [ATTENZIONE] Nessun dato estratto. Nessun file salvato.")

    return all_results


def extract_pubmed_data(
    query: str,
    output_dir: Path = _OUTPUT_DIR,
    only_with_abstract: bool = True,  # mantenuto per coerenza di firma
    max_results: int = 100,
) -> List[Dict]:
    """
    Estrae i record da PubMed con paginazione offset-based.

    Il protocollo E-Utilities richiede due chiamate HTTP distinte per ogni pagina:
      1. esearch → restituisce i PMID corrispondenti alla query (risposta JSON).
      2. efetch  → recupera i record completi dato l'elenco di PMID (risposta XML).
    La pausa tra le due chiamate rispetta il limite di 3 req/s imposto da NCBI.

    Due strutture dati parallele vengono mantenute in memoria:
      - all_results  : dizionari Medline parsati, pronti per la pipeline downstream.
      - raw_xml_list : stringhe XML grezze, destinate al file di output su disco.
    La separazione consente di ottimizzare indipendentemente le due trasformazioni.

    Il ciclo si interrompe in due condizioni:
      1. Il numero di record accumulati raggiunge max_results.
      2. Il server restituisce una pagina parziale (meno record del previsto),
         segnale che il dataset è stato completamente esaurito.

    Args:
        query:              Stringa di ricerca in sintassi PubMed.
        output_dir:         Directory di output per il file XML.
        only_with_abstract: Mantenuto per coerenza di firma (non utilizzato da PubMed).
        max_results:        Limite massimo di record da estrarre.

    Returns:
        Lista di dizionari in formato Medline (al più max_results elementi).
        Il file XML viene salvato su disco come side-effect.
    """
    sep = "=" * 70
    print(f"\n{sep}\nESTRAZIONE PUBMED — query: '{query}'\n{sep}")

    all_results: List[Dict] = []
    raw_xml_list: List[str] = []   # Usato solo per il salvataggio finale su disco
    offset: int = 0
    page_num: int = 1

    while True:
        print(f"\n--- Pagina {page_num} ---")

        # Fase 1: recupero dei PMID tramite esearch (risposta JSON).
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

        # Pausa obbligatoria tra esearch ed efetch per rispettare
        # il limite di 3 req/s di NCBI senza necessità di API key.
        time.sleep(_PAGE_SLEEP)

        # Fase 2: download dei record completi tramite efetch (risposta XML).
        fetch_url = build_pubmed_fetch_url(id_list)
        xml_data: Optional[str] = fetch_data_with_retries(fetch_url, response_format="xml")

        if not xml_data:
            print("  -> Fetch XML fallito. Interruzione.")
            break

        try:
            root = ET.fromstring(xml_data)
            articles = root.findall(".//PubmedArticle")

            # Separazione tra rappresentazione disco (XML raw) e
            # rappresentazione memoria (dizionari Medline parsati).
            batch_raw_xml = [ET.tostring(art, encoding="unicode") for art in articles]
            raw_xml_list.extend(batch_raw_xml)

            batch_parsed = [parse_pubmed_xml_node(art) for art in articles]
            all_results.extend(batch_parsed)

            print(
                f"  -> Estratti {len(batch_parsed)} articoli XML "
                f"(totale: {len(all_results)} / {total_available} disponibili)"
            )
        except ET.ParseError as exc:
            print(f"  -> Errore nel parsing dell'XML: {exc}. Interruzione.")
            break

        # Condizione di uscita 1: raggiunto il limite di record richiesto.
        if len(all_results) >= max_results:
            print(f"  -> Raggiunto limite richiesto di {max_results} risultati. Completato.")
            break

        # Condizione di uscita 2: il server ha restituito una pagina parziale,
        # segnale che il dataset disponibile è stato completamente esaurito.
        if len(id_list) < DEFAULT_PER_PAGE:
            print("  -> Nessun altro articolo disponibile sul server. Completato.")
            break

        offset += DEFAULT_PER_PAGE
        page_num += 1
        time.sleep(_PAGE_SLEEP)

    if raw_xml_list:
        # Troncamento preventivo: assicura che il file su disco non superi
        # max_results record, coerentemente con la lista restituita in memoria.
        save_pubmed_xml(raw_xml_list[:max_results], output_dir)
    else:
        print("  [ATTENZIONE] Nessun dato estratto. Nessun file salvato.")

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
    Punto di ingresso pubblico del modulo (pattern Facade).

    Astrae i dettagli implementativi degli orchestratori specifici per sorgente,
    esponendo un'interfaccia uniforme al codice chiamante. Il pattern dispatch-table
    (dizionario stringa → lambda) è preferito a una catena if/elif: è più estendibile
    (aggiungere una nuova sorgente equivale ad aggiungere una chiave) e rende esplicita
    la mappatura sorgente → funzione.

    La normalizzazione del parametro source con .lower().strip() tolera variazioni
    di capitalizzazione senza richiedere validazione esplicita da parte del chiamante.

    Parametri
    ----------
    query       : Stringa di ricerca bibliografica.
    source      : Sorgente dati: "openalex" oppure "pubmed" (case-insensitive).
    output_dir  : Directory di output (accetta str o Path per flessibilità).

    Restituisce
    -----------
    Lista di dict con i record estratti dalla sorgente indicata.
    Salva anche i file grezzi su disco nella output_dir come side-effect.

    Raises
    ------
    ValueError  : Se source non è "openalex" né "pubmed".
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
# ESECUZIONE DIRETTA (per test rapidi da riga di comando)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    # Gli argomenti CLI vengono uniti per supportare query multi-parola
    # senza richiedere virgolette (es: python extract.py machine learning).
    query_test = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "machine learning bibliometrics"
    print(f"Query di test: '{query_test}'")

    for src in ("openalex", "pubmed"):
        records = extract_data(query_test, source=src)
        print(f"\n→ {src}: {len(records)} record estratti.\n")