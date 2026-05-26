# Mappatura delle chiavi OpenAlex ai tag standard Web of Science (WoS)
OPENALEX_TO_WOS = {
    "id": "UT",                # Identificatore univoco 
    "doi": "DI",               # DOI 
    "title": "TI",             # Titolo del documento 
    "publication_year": "PY",  # Anno di pubblicazione 
    "cited_by_count": "TC",    # Numero di citazioni ricevute 
    "abstract_inverted_index": "AB" # L'abstract (OpenAlex lo fornisce invertito) 
}

def clean_scalar_fields(raw_record: dict) -> dict:
    """Mappa e pulisce i campi scalari (stringhe/interi) eliminando i None[cite: 51, 65, 76]."""
    cleaned_scalars = {}
    
    # Impostiamo esplicitamente la provenienza del database come richiesto 
    cleaned_scalars["DB"] = "OPENALEX" 
    
    # Applichiamo la Lookup Strategy per i campi standard [cite: 41, 42]
    for oa_key, wos_tag in OPENALEX_TO_WOS.items():
        val = raw_record.get(oa_key)
        
        # Gestione specifica per le citazioni (Times Cited) che deve essere int 
        if wos_tag == "TC":
            cleaned_scalars[wos_tag] = int(val) if val is not None else 0 [cite: 65]
        # Gestione per l'anno di pubblicazione (deve essere stringa o int a 4 cifre) 
        elif wos_tag == "PY":
            cleaned_scalars[wos_tag] = str(val) if val is not None else "" [cite: 51, 65]
        # Gestione standard delle stringhe
        else:
            cleaned_scalars[wos_tag] = str(val) if val is not None else "" [cite: 51]
            
    return cleaned_scalars

def extract_authors(raw_record: dict) -> list[str]:
    """Estrae i nomi degli autori trasformandoli in una lista di stringhe[cite: 45, 76]."""
    authorships = raw_record.get("authorships")
    
    # Se il campo è nullo o mancante, restituiamo una lista vuota 
    if not authorships:
        return [] [cite: 50]
        
    author_list = []
    for auth in authorships:
        # Navighiamo nella struttura di OpenAlex per prendere il nome visualizzato dell'autore
        author_data = auth.get("author", {})
        name = author_data.get("display_name")
        if name:
            author_list.append(str(name))
            
    return author_list [cite: 45]

def transform_openalex_record(raw_record: dict) -> dict:
    """Orchestra la trasformazione del record applicando i contratti di tipo[cite: 13, 76]."""
    # 1. Pulisce i campi scalari
    standardized_record = clean_scalar_fields(raw_record)
    
    # 2. Integra i campi multi-valore convertiti in liste 
    standardized_record["AU"] = extract_authors(raw_record) [cite: 45, 65]
    
    # Nota: Qui aggiungerai le chiamate alle funzioni per C1, DE, CR ecc. 
    # Se un campo del glossario non è ancora implementato, lo inseriamo vuoto per contratto [cite: 64]
    standardized_record["C1"] = [] [cite: 50, 64, 65]
    standardized_record["DE"] = [] [cite: 50, 64, 65]
    standardized_record["ID"] = [] [cite: 50, 64, 65]
    
    return standardized_record