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
    """Orchestra la trasformazione del record applicando i contratti di tipo."""
    standardized_record = clean_scalar_fields(raw_record)
    
    # Integriamo i campi multi-valore
    standardized_record["AU"] = extract_authors(raw_record)
    standardized_record["C1"] = extract_affiliations(raw_record)  
    standardized_record["DE"] = extract_keywords(raw_record)
    
    # Ricostruiamo l'abstract invertito
    standardized_record["AB"] = reconstruct_abstract(raw_record) # <--- Nuova integrazione
    
    # Campi temporaneamente vuoti
    standardized_record["ID"] = []
    standardized_record["CR"] = []
    
    return standardized_record

def extract_affiliations(raw_record: dict) -> list[str]:
    """Estrae le affiliazioni degli autori (C1) come lista di stringhe."""
    authorships = raw_record.get("authorships")
    
    if not authorships:
        return []
        
    affiliation_list = []
    for auth in authorships:
        # Ogni autore può avere più istituzioni associate
        institutions = auth.get("institutions", [])
        for inst in institutions:
            inst_name = inst.get("display_name")
            # Evitiamo duplicati nella lista dell'articolo ed escludiamo i None 
            if inst_name and str(inst_name) not in affiliation_list:
                affiliation_list.append(str(inst_name))
                
    return affiliation_list

def extract_keywords(raw_record: dict) -> list[str]:
    """Estrae le parole chiave dell'autore (DE) convertendole in lista."""
    keywords_data = raw_record.get("keywords")
    
    if not keywords_data:
        return []
        
    keywords_list = []
    for kw in keywords_data:
        kw_name = kw.get("display_name")
        if kw_name:
            keywords_list.append(str(kw_name))
            
    return keywords_list

def reconstruct_abstract(raw_record: dict) -> str:
    """
    Ricostruisce l'abstract di OpenAlex dal suo indice invertito.
    Restituisce una stringa vuota se l'abstract non è presente.
    """
    inverted_index = raw_record.get("abstract_inverted_index")
    
    # Se il campo non esiste o è None, restituiamo stringa vuota per contratto
    if not inverted_index:
        return ""
        
    try:
        # 1. Troviamo l'indice più alto (che corrisponde all'ultima parola)
        # Iteriamo su tutte le liste di posizioni e troviamo il valore massimo
        max_index = max(max(positions) for positions in inverted_index.values())
        
        # 2. Creiamo una lista vuota della giusta dimensione
        # Lunghezza = indice massimo + 1 (perché gli indici partono da 0)
        reconstructed_words = [""] * (max_index + 1)
        
        # 3. Posizioniamo ogni parola nel suo slot corretto
        for word, positions in inverted_index.items():
            for pos in positions:
                reconstructed_words[pos] = word
                
        # 4. Uniamo la lista in un'unica stringa separata da spazi
        # Usiamo ' '.join() per rimettere gli spazi tra le parole
        return " ".join(reconstructed_words).strip()
        
    except Exception as e:
        # Pratica sicura: se qualcosa va storto nella ricostruzione, 
        # meglio restituire vuoto che far crashare l'intera pipeline
        print(f"Errore nella ricostruzione dell'abstract: {e}")
        return ""