"""
main.py — Orchestratore della Pipeline ETL Bibliometrix (Livello Avanzato)

Questo script unisce la Fase 1 (Extract) e le Fasi 2-5 (Transform, Validation, 
Calculated Fields, Export) in un unico flusso automatizzato, senza alcun
intervento manuale sui file, come richiesto dalla specifica Advanced.
"""

import pandas as pd
from api_retriever import extract_data
from standardizer import convert2df

def run_etl_pipeline(query: str, source: str = "openalex", output_csv: str = "bibliometrix_export.csv") -> pd.DataFrame | None:
    """
    Esegue l'intera pipeline ETL:
      1. Scarica i dati via API (Extract).
      2. Pulisce, valida e calcola i campi derivati (Transform).
      3. Salva il risultato su disco (Load).
    """
    print("\n" + "="*70)
    print("🚀 AVVIO PIPELINE ETL BIBLIOMETRIX (LIV. AVANZATO)")
    print("="*70)

    # ---------------------------------------------------------
    # FASE 1: EXTRACT (Download via API)
    # ---------------------------------------------------------
    print(f"\n[1/3] FASE DI ESTRAZIONE ({source.upper()})...")
    
    # Questa chiamata avvia il prompt interattivo del tuo collega!
    raw_records = extract_data(query=query, source=source)

    if not raw_records:
        print("\n❌ Nessun dato estratto. Pipeline interrotta.")
        return None

    # ---------------------------------------------------------
    # FASI 2, 4 e 5: TRANSFORM, CALCULATED FIELDS e VALIDATION
    # ---------------------------------------------------------
    print(f"\n[2/3] FASE DI TRASFORMAZIONE E VALIDAZIONE...")
    
    try:
        # Passiamo i record grezzi al tuo standardizer.
        # NOTA BENE: for_csv_export=True è FONDAMENTALE per convertire
        # le liste in stringhe con il delimitatore ';' come chiede l'esame!
        df = convert2df(
            raw_records=raw_records, 
            source=source, 
            validate=True, 
            for_csv_export=True
        )
    except Exception as e:
        print(f"\n❌ Errore critico durante la trasformazione: {e}")
        return None

    # ---------------------------------------------------------
    # FASE 3: LOAD (Salvataggio in CSV)
    # ---------------------------------------------------------
    print(f"\n[3/3] FASE DI CARICAMENTO (Salvataggio CSV)...")
    
    # encoding="utf-8-sig" è cruciale per permettere a Excel/R di leggere 
    # correttamente i caratteri speciali degli autori internazionali.
    df.to_csv(output_csv, index=False, encoding="utf-8-sig")
    
    print("\n" + "="*70)
    print(f"✅ PIPELINE COMPLETATA CON SUCCESSO!")
    print(f"📊 Dimensioni DataFrame: {df.shape[0]} righe x {df.shape[1]} colonne")
    print(f"💾 File salvato in: {output_csv}")
    print("="*70 + "\n")

    return df

# =========================================================
# ESECUZIONE DELLO SCRIPT
# =========================================================
if __name__ == "__main__":
    # Test della pipeline con una query accademica reale
    QUERY_ESAME = "machine learning AND bibliometrics"
    
    # Esegue l'ETL e crea il file "risultati_finali.csv"
    df_risultato = run_etl_pipeline(
        query=QUERY_ESAME, 
        source="openalex",
        output_csv="risultati_finali.csv"
    )