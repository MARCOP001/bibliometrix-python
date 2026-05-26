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
    """Mappa e pulisce i campi scalari (stringhe/interi) eliminando i None."""
    cleaned_scalars = {}
    
    # Impostiamo esplicitamente la provenienza del database come richiesto 
    cleaned_scalars["DB"] = "OPENALEX" 
    
    # Applichiamo la Lookup Strategy per i campi standard
    for oa_key, wos_tag in OPENALEX_TO_WOS.items():
        val = raw_record.get(oa_key)
        
        # Gestione specifica per le citazioni (Times Cited) che deve essere int 
        if wos_tag == "TC":
            cleaned_scalars[wos_tag] = int(val) if val is not None else 0
        # Gestione per l'anno di pubblicazione (deve essere stringa o int a 4 cifre) 
        elif wos_tag == "PY":
            cleaned_scalars[wos_tag] = str(val) if val is not None else ""
        # Gestione standard delle stringhe
        else:
            cleaned_scalars[wos_tag] = str(val) if val is not None else ""
            
    return cleaned_scalars

def extract_authors(raw_record: dict) -> list[str]:
    """Estrae i nomi degli autori e li formatta in 'Cognome, Nome'."""
    authorships = raw_record.get("authorships")
    
    if not authorships:
        return []
        
    author_list = []
    for auth in authorships:
        author_data = auth.get("author", {})
        name = author_data.get("display_name")
        
        if name:
            name_str = str(name)
            # Logica semplice per convertire "Nome Cognome" in "Cognome, Nome"
            parts = name_str.split()
            if len(parts) > 1:
                surname = parts[-1]
                first_names = " ".join(parts[:-1])
                formatted_name = f"{surname}, {first_names}"
            else:
                formatted_name = name_str # Se è una sola parola, la teniamo così
                
            author_list.append(formatted_name)
            
    return author_list

def extract_references(raw_record: dict) -> list[str]:
    """
    Estrae i riferimenti citati (CR).
    In OpenAlex, i referenced_works sono forniti come lista di ID.
    """
    references = raw_record.get("referenced_works")
    
    # Gestione dei valori mancanti o nulli
    if not references:
        return []
        
    reference_list = []
    for ref in references:
        if ref:
            # Assicuriamoci che ogni riferimento sia una stringa
            reference_list.append(str(ref))
            
    return reference_list

def transform_openalex_record(raw_record: dict) -> dict:
    """Orchestra la trasformazione del record applicando i contratti di tipo."""
    
    # 1. Creiamo lo scheletro completo per superare la validazione (tutte le colonne del glossario)
    standardized_record = {
        "DB": "", "UT": "", "DI": "", "PMID": "", "TI": "", 
        "SO": "", "JI": "", "PY": "", "DT": "", "LA": "", 
        "TC": 0, "RP": "", "AB": "", "VL": "", "IS": "", 
        "BP": "", "EP": "", "SR": "",
        "AU": [], "AF": [], "C1": [], "CR": [], "DE": [], "ID": []
    }
    
    # 2. Sovrascriviamo con i campi scalari estratti da OpenAlex
    extracted_scalars = clean_scalar_fields(raw_record)
    standardized_record.update(extracted_scalars)
    
    # 3. Integriamo i campi complessi calcolati
    standardized_record["AU"] = extract_authors(raw_record)
    # OpenAlex non fa molta differenza tra AU e AF, possiamo duplicarlo per sicurezza
    standardized_record["AF"] = standardized_record["AU"] 
    standardized_record["C1"] = extract_affiliations(raw_record)  
    standardized_record["DE"] = extract_keywords(raw_record)
    standardized_record["AB"] = reconstruct_abstract(raw_record)
    
    # ... (codice precedente dello scheletro e dei campi scalari/complessi) ...
    standardized_record["AB"] = reconstruct_abstract(raw_record)
    
    # 4. Aggiungiamo i riferimenti citati
    standardized_record["CR"] = extract_references(raw_record)
    
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