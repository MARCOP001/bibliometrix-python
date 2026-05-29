import re
import xml.etree.ElementTree as ET


# WEB OF SCIENCE PARSER
def parse_wos_data(datapath: str) -> list[dict]:  
    """
    Legge un file di esportazione testuale da Web of Science (.txt o .ciw) 
    e lo converte in una lista di dizionari.
    
    Args:
        datapath (str): Il percorso del file grezzo nel sistema.
    Returns:
        list[dict]: Una lista dove ogni elemento rappresenta un articolo.
    """
    elem_data = []
    data = {}
    current_key = None

    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Ignoriamo le prime due righe (lines[2:]) perché in WoS di solito contengono intestazioni di sistema e non i dati dell'articolo.
    for line in lines[2:]:
        line = line.rstrip() # Rimuoviamo gli spazi vuoti a fine riga
        
        # Ignoriamo le righe vuote e il tag "EF" (End of File, fine del documento)
        if line.strip() != "" and line.strip() != "EF":
            
            # "ER" sta per End Record. Indica che l'articolo corrente è finito.
            if line.startswith("ER"):
                if data:
                    elem_data.append(data.copy()) # Salviamo una copia del record completato
                current_key = None
                data = {} # Svuotiamo il dizionario per il prossimo articolo
                
            # In WoS, se una riga inizia con due spazi, non è una nuova chiave ma la continuazione del testo della chiave precedente.
            elif line.startswith("  "):
                if current_key and current_key in data:
                    # Alcuni campi (es. DE: Keywords, AB: Abstract) hanno più senso come unica stringa di testo. Li uniamo separandoli da uno spazio.
                    if current_key in {"DE", "C3", "EM", "FU", "FX", "WC"}:
                        current_value = " ".join(data[current_key]) + " " + line.strip()
                        data[current_key] = [current_value]
                    # Altri campi (es. AU: Autori) hanno più senso come liste separate.
                    else:
                        data[current_key].append(line.strip())
                        
            # Se non è ER e non inizia con due spazi, è una nuova etichetta (es. "TI Titolo")
            else:
                line = line.strip()
                # Dividiamo la riga solo al primo spazio: a sinistra la chiave, a destra il valore
                key_value = line.split(" ", 1)
                if len(key_value) == 2:
                    key, value = key_value
                    data[key] = [value]
                    current_key = key

    return elem_data


# COCHRANE PARSER 
def parse_cochrane_data(datapath: str) -> list[dict]:
    """
    Legge un file di testo esportato dalla Cochrane Library 
    e lo converte in una lista di dizionari.
    
    Args:
        datapath (str): Il percorso del file grezzo nel sistema.
    Returns:
        list[dict]: Una lista di articoli.
    """
    data = []
    current_record = {}
    current_key = None # Traccia l'ultima chiave letta per gestire i testi su più righe
    
    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    for line in lines:
        line = line.strip()
        
        # Un nuovo record inizia o dopo una riga vuota o con il tag "Record #"
        if not line or line.startswith('Record #'):
            if current_record:
                # Fase di pulizia prima del salvataggio:
                # Rimuoviamo la chiave interna 'Record' perché è inutile ai fini dell'analisi
                if 'Record' in current_record:
                    del current_record['Record']
                # Puliamo l'intestazione fissa 'Abstract - Background' per avere solo il testo
                if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
                    current_record['AB'] = current_record['AB'][22:].strip()
                
                data.append(current_record)
                current_record = {}
                current_key = None
            continue

        # Regex: Cerca all'inizio riga (^) almeno 2 lettere maiuscole ([A-Z]{2,}), seguite da due punti (:), ed estrae il resto della riga (.+). Es: "AU: Rossi M"
        key_match = re.match(r'^([A-Z]{2,})\s*:\s*(.+)', line)
        if key_match:
            current_key = key_match.group(1)
            value = key_match.group(2)
            
            # Se la chiave esiste già (es. autori multipli), accodiamo il nuovo valore con un punto e virgola
            if current_key in current_record:
                current_record[current_key] += '; ' + value
            else:
                current_record[current_key] = value
        else:
            # Se la regex non trova una corrispondenza (es. non ci sono i due punti), assumiamo che sia il proseguimento del testo della riga precedente
            if current_record and current_key and current_key in current_record:
                current_record[current_key] += ' ' + line.strip()

    # Se il file finisce senza una riga vuota, ci assicuriamo di salvare l'ultimo record pendente
    if current_record:
        if 'Record' in current_record:
            del current_record['Record']
        if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
            current_record['AB'] = current_record['AB'][22:].strip()
        data.append(current_record)

    return data



# PUBMED PARSER (MEDLINE TEXT)
def parse_pubmed_medline_text(text: str) -> list[dict]:
    """
    Elabora un blocco di testo in formato MEDLINE (standard PubMed).
    Gestisce dinamicamente i campi ripetuti creando liste in automatico.
    
    Args:
        text (str): L'intero contenuto del file MEDLINE come singola stringa.
    Returns:
        list[dict]: Una lista di articoli.
    """
    records = []
    current_record = {}
    current_key = None

    for line in text.splitlines():
        if not line.strip():
            continue

        # "PMID-" indica l'inizio di un nuovo articolo.
        if line.startswith("PMID-"):
            if current_record:
                records.append(current_record)
            current_record = {}

        # Il formato Medline standard usa 4 caratteri per l'etichetta, seguiti da "- " 
        # Esempio: "TI  - Titolo dell'articolo"
        if len(line) > 6 and line[4:6] == "- ":
            current_key = line[:4].strip()
            value = line[6:].strip()

            if current_key in current_record:
                # Se la chiave c'è già ed è una lista, facciamo semplicemente un append
                if isinstance(current_record[current_key], list):
                    current_record[current_key].append(value)
                # Se c'è già ma è una stringa singola, la convertiamo al volo in una lista
                else:
                    current_record[current_key] = [current_record[current_key], value]
            else:
                # Se è la prima volta che incontriamo questa chiave, la salviamo come stringa
                current_record[current_key] = value

        # In Medline, le righe che iniziano con 6 spazi indicano la continuazione del campo precedente
        elif current_key and line.startswith("      "):
            if isinstance(current_record[current_key], list):
                # Se è una lista (es. un autore diviso su più righe), accodiamo la stringa all'ultimo elemento
                current_record[current_key][-1] += " " + line.strip()
            else:
                # Se è una stringa singola, la concateniamo
                current_record[current_key] += " " + line.strip()

    # Salvataggio dell'ultimo record a fine ciclo
    if current_record:
        records.append(current_record)

    return records



# PUBMED PARSER (XML)
def parse_pubmed_xml_node(article_node: ET.Element) -> dict:
    """
    Estrae i dati da un singolo nodo <PubmedArticle> dell'albero XML
    e lo traduce in un dizionario compatibile con la nomenclatura Medline 
    (es. trasforma <ArticleTitle> in 'TI').
    
    Args:
        article_node (ET.Element): Nodo XML rappresentante un singolo articolo.
    Returns:
        dict: Dizionario strutturato dell'articolo.
    """
    record = {}

    # Funzione Helper: previene errori se il nodo XML è mancante.
    # Se il percorso XPath esiste estrae il testo, altrimenti restituisce la stringa vuota di default.
    def get_text(xpath: str, default: str = "") -> str:
        node = article_node.find(xpath)
        return node.text.strip() if node is not None and node.text else default

    # Estrazione Dati Base
    record["PMID"] = get_text(".//MedlineCitation/PMID")
    record["TI"] = get_text(".//ArticleTitle")  # Title
    record["JT"] = get_text(".//Journal/Title") # Journal Title
    record["TA"] = get_text(".//Journal/ISOAbbreviation")
    
    # Gestione Data di Pubblicazione
    pub_date_year = get_text(".//PubDate/Year")
    if not pub_date_year:
        # Se non c'è l'anno esatto, spesso PubMed usa una 'MedlineDate' (es. "2023 Jan-Feb"). 
        # Ne estraiamo i primi 4 caratteri.
        pub_date_year = get_text(".//PubDate/MedlineDate")[:4]
    record["DP"] = pub_date_year # Date of Publication
    
    record["VI"] = get_text(".//JournalIssue/Volume")
    record["IP"] = get_text(".//JournalIssue/Issue")
    record["PG"] = get_text(".//Pagination/MedlinePgn") # Pages
    record["LA"] = get_text(".//Language")

    # Estrazione Abstract
    # Un abstract può essere diviso in più nodi (es. <AbstractText Label="METHODS">, <AbstractText Label="RESULTS">)
    abstract_texts = article_node.findall(".//AbstractText")
    if abstract_texts:
        record["AB"] = " ".join([node.text.strip() for node in abstract_texts if node.text])

    # Estrazione DOI
    doi_node = article_node.find(".//ArticleId[@IdType='doi']")
    if doi_node is not None and doi_node.text:
        record["LID"] = f"{doi_node.text} [doi]" # Formattato secondo lo standard Medline

    # Estrazione Autori e Affiliazioni
    au_list = []      # Autori (Formato breve, es. "Rossi M")
    fau_list = []     # Autori (Full name, es. "Rossi, Mario")
    affiliations = set() # Usiamo un Set per evitare di registrare doppioni della stessa università

    for author in article_node.findall(".//Author"):
        last_name = author.find("LastName")
        initials = author.find("Initials")
        fore_name = author.find("ForeName")

        ln = last_name.text if last_name is not None and last_name.text else ""
        init = initials.text if initials is not None and initials.text else ""
        fn = fore_name.text if fore_name is not None and fore_name.text else ""

        if ln:
            au_list.append(f"{ln} {init}".strip())
            fau_list.append(f"{ln}, {fn}".strip())

        # Cerchiamo l'affiliazione legata a questo specifico autore
        affil = author.find(".//Affiliation")
        if affil is not None and affil.text:
            affiliations.add(affil.text)

    if au_list: record["AU"] = au_list
    if fau_list: record["FAU"] = fau_list
    if affiliations: record["AD"] = list(affiliations)

    # Keyword e Tipi di Pubblicazione
    keywords = article_node.findall(".//Keyword")
    if keywords:
        record["OT"] = [k.text for k in keywords if k.text] # OT = Other Terms (Keywords)

    pub_types = article_node.findall(".//PublicationType")
    if pub_types:
        record["PT"] = [pt.text for pt in pub_types if pt.text]

    return record