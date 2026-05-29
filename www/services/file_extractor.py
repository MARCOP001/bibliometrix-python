import pandas as pd
import os

from .parsers import parse_pubmed_medline_text, parse_wos_data, parse_cochrane_data

def extract_from_file(file_path: str, source: str) -> list[dict]:
    """
    Legge un file grezzo esportato manualmente dalle principali piattaforme 
    bibliometriche e lo converte in una struttura dati Python standardizzata.
    
    Args:
        file_path (str): Il percorso assoluto o relativo del file da leggere.
        source (str): Il nome del database di origine (es. "Scopus", "PubMed").
        
    Returns:
        list[dict]: Una lista dove ogni dizionario rappresenta un singolo articolo.
        
    Raises:
        FileNotFoundError: Se il percorso del file indicato non esiste.
        ValueError: Se l'estensione del file o la fonte testuale non sono supportate.
    """
    
    # Controlliamo subito se il file esiste sul disco. 
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Errore: Il file '{file_path}' non esiste.")
        
    # Pulizia dell'input: trasformiamo la fonte in maiuscolo e togliamo gli spazi accidentali
    source_upper = source.upper().strip()
    
    # Estraiamo l'estensione del file e la mettiamo in minuscolo
    file_extension = os.path.splitext(file_path)[1].lower()
    
    # FILE DI TESTO PROPRIETARI (TXT/CIW)
    # Wos, Cochrane e PubMed
    if file_extension in ['.txt', '.ciw']:
        print(f"[{source_upper}] Lettura file testuale proprietario: {file_path}")
        
        # Gestione specifica per PubMed:
        if source_upper == "PUBMED":
            # PubMed richiede che il testo venga letto qui e passato al parser come stringa.
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            return parse_pubmed_medline_text(text_content)
            
        # Gestione per Web of Science:
        elif source_upper == "WEB_OF_SCIENCE":
            return parse_wos_data(file_path)
            
        # Gestione per Cochrane:
        elif source_upper == "COCHRANE":
            return parse_cochrane_data(file_path)
            
        else:
            raise ValueError(
                f"I file di testo (.txt/.ciw) sono supportati solo per PUBMED, WEB_OF_SCIENCE e COCHRANE. "
                f"Ricevuto: {source_upper}"
            )

    # FILE TABELLARI (CSV/XLSX/XLS)
    # Scopus, Dimensions, Lens, OpenAlex e WoS tabellare
    
    elif file_extension in ['.csv', '.xlsx', '.xls']:
        print(f"[{source_upper}] Lettura file tabellare {file_extension}: {file_path}")
        
        try:
            if file_extension == '.csv':
                df = pd.read_csv(
                    file_path, 
                    dtype=str,           
                    on_bad_lines='skip', 
                    encoding='utf-8'     
                )
            else:
                df = pd.read_excel(file_path, dtype=str)
                
            # --- PATCH DIMENSIONS (Risoluzione del preambolo) ---
            if source_upper == "DIMENSIONS":
                # Se l'intestazione corretta è finita nella prima riga di dati a causa del preambolo:
                if "Publication ID" not in df.columns:
                    # Rinomina le colonne usando la prima riga di dati
                    df.columns = df.iloc[0]
                    # Elimina la prima riga (che ormai è diventata l'intestazione)
                    df = df[1:].reset_index(drop=True)
            # ----------------------------------------------------

            # Sostituiamo i NaN con stringhe vuote.
            df = df.fillna("")
            
            # Converte il DataFrame in una una lista di dizionari.
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