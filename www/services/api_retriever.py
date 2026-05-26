"""
extract.py — Fase 1 (Extract) della Pipeline ETL Bibliometrix.

Responsabilità:
    - Costruire gli URL per le API supportate.
    - Eseguire chiamate HTTP in modo sicuro (retry + backoff esponenziale).
    - Gestire la paginazione interattiva tramite cursor (OpenAlex).
    - Esporre un unico entry-point: extract_data(query, source).

Sorgenti attualmente supportate:
    - OpenAlex  (JSON REST, paginazione via cursor)
"""

import os
import time
import requests
from urllib.parse import quote_plus
from typing import Optional

# ---------------------------------------------------------------------------
# Configurazione globale
# ---------------------------------------------------------------------------

# L'email viene letta da una variabile d'ambiente; se assente si usa il
# valore di default. OpenAlex la usa per dare priorità al tuo traffico.
MAILTO: str = os.environ.get("BIBLIOMETRIX_EMAIL", "roberto.gargiulo5@studenti.unina.it")

# Numero di articoli richiesti per ogni singola pagina API.
DEFAULT_PER_PAGE: int = 25

# Tentativi massimi prima di considerare una chiamata fallita.
DEFAULT_MAX_RETRIES: int = 3

# Pausa di cortesia (secondi) tra una pagina e la successiva.
_PAGE_SLEEP: float = 0.15


# ---------------------------------------------------------------------------
# LIVELLO 1 — Costruttori URL
# ---------------------------------------------------------------------------

def build_openalex_url(query: str, cursor: str = "*", per_page: int = DEFAULT_PER_PAGE) -> str:
    """
    Costruisce l'URL per l'API di OpenAlex con paginazione via cursor.
    """
    encoded_query: str = quote_plus(query)
    url = (
        f"https://api.openalex.org/works"
        f"?search={encoded_query}"
        f"&cursor={cursor}"
        f"&per-page={per_page}"
        f"&mailto={MAILTO}"
    )
    return url


# ---------------------------------------------------------------------------
# LIVELLO 2 — Fetcher sicuro con retry e backoff esponenziale
# ---------------------------------------------------------------------------

def fetch_data_with_retries(
    url: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Optional[dict]:
    """
    Esegue una richiesta HTTP GET con logica di retry e backoff esponenziale.
    """
    headers = {
        "User-Agent": f"bibliometrix-python/1.0 (mailto:{MAILTO})",
        "Accept": "application/json",
    }

    for attempt in range(max_retries):
        wait_time: float = 2 ** attempt  # 1s → 2s → 4s

        try:
            print(f"  -> GET {url[:90]}{'...' if len(url) > 90 else ''} "
                  f"(tentativo {attempt + 1}/{max_retries})")

            response = requests.get(url, headers=headers, timeout=15)

            # — Successo —
            if response.status_code == 200:
                return response.json()

            # — Rate limit: aspetta e riprova —
            elif response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", wait_time))
                print(f"  -> 429 Rate limit. Attendo {retry_after:.0f}s...")
                time.sleep(retry_after)

            # — Errori server transitori: aspetta e riprova —
            elif response.status_code in (500, 502, 503, 504):
                print(f"  -> {response.status_code} Errore server. Attendo {wait_time:.0f}s...")
                time.sleep(wait_time)

            # — Qualsiasi altro errore HTTP (4xx): non recuperabile —
            else:
                print(f"  -> Errore {response.status_code} non recuperabile. "
                      f"Messaggio: {response.text[:120]}")
                return None

        except requests.exceptions.Timeout:
            print(f"  -> Timeout dopo 15s. Attendo {wait_time:.0f}s e riprovo...")
            time.sleep(wait_time)

        except requests.exceptions.ConnectionError as exc:
            print(f"  -> Errore di connessione: {exc}. Attendo {wait_time:.0f}s e riprovo...")
            time.sleep(wait_time)

    # Tutti i tentativi esauriti
    print(f"  [FALLIMENTO] Impossibile raggiungere l'endpoint dopo {max_retries} tentativi.")
    return None


# ---------------------------------------------------------------------------
# LIVELLO 3 — Orchestratore OpenAlex Interattivo
# ---------------------------------------------------------------------------

def extract_openalex_data(query: str) -> list[dict]:
    """
    Scarica articoli da OpenAlex in modo interattivo.
    Dopo ogni pagina, mostra il conteggio totale e chiede all'utente se procedere.
    """
    print(f"\n{'='*70}")
    print(f"ESTRAZIONE OPENALEX INTERATTIVA — query: '{query}'")
    print(f"{'='*70}")

    all_results: list[dict] = []
    cursor: str = "*"  # Cursore iniziale OpenAlex
    page_num: int = 1

    while True:
        print(f"\n--- Estrazione Pagina {page_num} ---")

        # 1. Costruisci URL con il cursor corrente
        url = build_openalex_url(query, cursor=cursor)

        # 2. Chiama l'API in modo sicuro
        data = fetch_data_with_retries(url)

        # 3. Gestione risposta fallita
        if data is None:
            print("  -> Chiamata fallita. Interrompo l'estrazione.")
            break

        # 4. Estrai i risultati
        results: list[dict] = data.get("results", [])
        if not results:
            print("  -> Pagina vuota. Fine dataset raggiunta.")
            break

        all_results.extend(results)
        total_available: int = data.get("meta", {}).get("count", "?")
        
        print(f"  -> Successo: +{len(results)} articoli.")
        print(f"  -> Totale scaricati finora: {len(all_results)} | Disponibili su OpenAlex: {total_available}")

        # 5. Leggi il cursore per la pagina successiva
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            print("  -> Nessun next_cursor ricevuto. Fine dataset.")
            break

        # 6. Interazione utente
        risposta = input("\nVuoi scaricare la pagina successiva? (s/n): ").strip().lower()
        if risposta != 's':
            print("  -> Estrazione interrotta dall'utente.")
            break

        # Piccola pausa di cortesia verso il server
        time.sleep(_PAGE_SLEEP)
        page_num += 1

    print(f"\n{'='*70}")
    print(f"ESTRAZIONE COMPLETATA — {len(all_results)} articoli totali raccolti.")
    print(f"{'='*70}\n")
    return all_results


# ---------------------------------------------------------------------------
# ENTRY POINT UNIFICATO — dispatcher per sorgente
# ---------------------------------------------------------------------------

def extract_data(query: str, source: str) -> list[dict]:
    """
    Entry point unico per la Fase 1 dell'ETL. Instrada la richiesta alla
    funzione di estrazione corretta in base alla sorgente selezionata.
    """
    normalized_source = source.lower().strip()

    dispatch_table = {
        "openalex": extract_openalex_data,
        # "pubmed": extract_pubmed_data,  # da aggiungere nella prossima iterazione
    }

    if normalized_source not in dispatch_table:
        supported = ", ".join(f'"{k}"' for k in dispatch_table)
        raise ValueError(
            f"Sorgente '{source}' non supportata. "
            f"Valori accettati: {supported}."
        )

    extractor = dispatch_table[normalized_source]
    return extractor(query)


# ---------------------------------------------------------------------------
# BLOCCO DI TEST — si attiva solo con: python extract.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    TEST_QUERY = "machine learning"
    TEST_SOURCE = "openalex"

    print(f"Avvio test interattivo con query='{TEST_QUERY}' e source='{TEST_SOURCE}'\n")

    try:
        risultati = extract_data(TEST_QUERY, source=TEST_SOURCE)
    except ValueError as e:
        print(f"Errore configurazione: {e}")
        risultati = []

    if risultati:
        print(f"\nPrimi 3 articoli estratti come prova:")
        for i, record in enumerate(risultati[:3], start=1):
            title = record.get("title") or "Titolo mancante"
            year = record.get("publication_year", "N/A")
            doi = record.get("doi") or "N/A"
            print(f"  {i}. [{year}] {title[:80]}")
            print(f"        DOI: {doi}")
    else:
        print("Nessun risultato ottenuto.")