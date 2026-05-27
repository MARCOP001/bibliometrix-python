import pandas as pd
import os
import re

# Importiamo i parser per i file di testo proprietari
from parsers import parse_pubmed_medline_text, parse_wos_data, parse_cochrane_data

def extract_from_file(file_path: str, source: str) -> list[dict]:
    """
    Fase 1 (Extract) - Base Level.
    Legge un file grezzo esportato manualmente dalle sei principali piattaforme 
    bibliometriche e lo converte in una lista di dizionari (raw_records).
    
    Supporta: WEB_OF_SCIENCE, SCOPUS, PUBMED, OPENALEX, DIMENSIONS, LENS.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Errore: Il file '{file_path}' non esiste.")
        
    source_upper = source.upper().strip()
    file_extension = os.path.splitext(file_path)[1].lower()
    
    # ---------------------------------------------------------
    # STRATEGIA A: FILE DI TESTO PROPRIETARI (TXT/CIW)
    # ---------------------------------------------------------
    if file_extension in ['.txt', '.ciw']:
        print(f"[{source_upper}] Lettura file testuale proprietario: {file_path}")
        
        if source_upper == "PUBMED":
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            return parse_pubmed_medline_text(text_content)
            
        elif source_upper == "WEB_OF_SCIENCE":
            # Usiamo la funzione del pacchetto originale
            return parse_wos_data(file_path)
        elif source_upper == "COCHRANE":
            return parse_cochrane_data(file_path)
            
        else:
            raise ValueError(
                f"I file di testo (.txt/.ciw) sono supportati solo per PUBMED e WEB_OF_SCIENCE. "
                f"Ricevuto: {source_upper}"
            )

    # ---------------------------------------------------------
    # STRATEGIA B: FILE TABELLARI (CSV/XLSX)
    # (Scopus, Dimensions, Lens, OpenAlex, e versioni tabellari di WoS)
    # ---------------------------------------------------------
    elif file_extension in ['.csv', '.xlsx', '.xls']:
        print(f"[{source_upper}] Lettura file tabellare {file_extension}: {file_path}")
        
        try:
            if file_extension == '.csv':
                # Leggiamo tutto come stringa per evitare troncamenti di ID o anni
                df = pd.read_csv(
                    file_path, 
                    dtype=str, 
                    on_bad_lines='skip',
                    encoding='utf-8' # Standard per l'export di questi database
                )
            else:
                df = pd.read_excel(file_path, dtype=str)
                
            # Riempiamo i NaN per evitare problemi di iterazione nello standardizer
            df = df.fillna("")
            return df.to_dict(orient="records")
            
        except pd.errors.EmptyDataError:
             print(f"[ERRORE] Il file '{file_path}' è vuoto.")
             return []
        except Exception as e:
             print(f"[ERRORE] Impossibile leggere il file tabellare: {e}")
             return []
             
    else:
        raise ValueError(
            f"Formato file non supportato: {file_extension}. "
            f"I formati accettati sono: .csv, .xlsx, .txt, .ciw"
        )