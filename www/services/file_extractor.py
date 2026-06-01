"""Estrae record bibliografici grezzi dai file prima della standardizzazione."""

from __future__ import annotations

import os
import tempfile
import zipfile

import pandas as pd
from bibtexparser.bparser import BibTexParser

from .parsers import parse_cochrane_data, parse_pubmed_medline_text, parse_wos_data


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".txt", ".ciw", ".bib"}


def _annotate_records(records: list[dict], file_extension: str, source: str) -> list[dict]:
    """Aggiunge i metadati di sorgente usati dal dispatcher di trasformazione.

    Parametri:
        records: Record bibliografici grezzi estratti da un file.
        file_extension: Estensione minuscola del file di origine.
        source: Nome normalizzato della sorgente associata ai record.

    Restituisce:
        La stessa lista di record, arricchita sul posto con chiavi di metadati
        interni.

    Note:
        La funzione modifica direttamente ogni record per permettere ai
        convertitori successivi di instradarlo senza riesaminare il file
        originale.
    """
    for record in records:
        record["_bibliometrix_file_type"] = file_extension
        record["_bibliometrix_source"] = source
    return records


def _read_tabular_file(file_path: str, file_extension: str, source_upper: str) -> list[dict]:
    """Legge un export bibliografico CSV o Excel in dizionari grezzi.

    Parametri:
        file_path: Percorso del file tabellare di input.
        file_extension: Estensione usata per scegliere il lettore pandas.
        source_upper: Nome della sorgente in maiuscolo; gli export Dimensions
            richiedono di saltare una riga di metadati.

    Restituisce:
        Una lista di dizionari, uno per riga, con i valori mancanti sostituiti
        da stringhe vuote.

    Solleva:
        pandas.errors.EmptyDataError: Propagata quando un file CSV non contiene
            dati.
        Exception: Propaga gli errori di lettura sollevati da pandas per
            contenuti tabellari non supportati o malformati.
    """
    # Gli export Dimensions includono una prima riga descrittiva prima
    # dell'intestazione reale.
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
    """Converte un export BibTeX in dizionari di record grezzi.

    Parametri:
        file_path: Percorso del file BibTeX codificato in UTF-8.

    Restituisce:
        Una lista di dizionari prodotta da ``bibtexparser``.

    Solleva:
        FileNotFoundError: Propagata se il percorso non esiste.
        Exception: Propaga errori di parsing o decodifica sollevati da
            ``bibtexparser`` e dal lettore del file.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        parser = BibTexParser()
        return parser.parse_file(file).entries


def _extract_zip_file(file_path: str, source_upper: str) -> list[dict]:
    """Estrae i file supportati da un archivio ZIP e ne legge i record.

    Parametri:
        file_path: Percorso dell'archivio ZIP.
        source_upper: Nome della sorgente in maiuscolo passato all'estrazione
            dei file annidati.

    Restituisce:
        Lista combinata dei record estratti dai file supportati presenti
        nell'archivio.

    Solleva:
        zipfile.BadZipFile: Propagata quando l'archivio non e' valido.
        ValueError: Propagata dall'estrazione annidata per contenuti non
            supportati.
    """
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
    """Legge un export bibliografico grezzo e restituisce record dizionario.

    La funzione e' intenzionalmente limitata alla fase di estrazione: non
    rinomina colonne e non applica lo schema WoS. Quel lavoro e' delegato a
    ``standardizer.convert2df``.

    Parametri:
        file_path: Percorso dell'export bibliografico da leggere.
        source: Sorgente selezionata dal chiamante. Il valore viene
            normalizzato in maiuscolo prima del dispatch ai parser specifici.

    Restituisce:
        Una lista di dizionari di record grezzi annotati con metadati di
        sorgente e tipo file.

    Solleva:
        FileNotFoundError: Se ``file_path`` non esiste.
        ValueError: Se l'estensione o la combinazione sorgente/estensione non
            e' supportata.

    Note:
        I file tabellari vuoti o non leggibili vengono segnalati e convertiti
        in una lista vuota, preservando il comportamento di estrazione attuale.
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

        # Gli export testuali usano convenzioni di tag specifiche per sorgente,
        # quindi vengono inviati ai parser dedicati prima dell'annotazione comune.
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
