import re
import xml.etree.ElementTree as ET
# from .utils import * # Scommenta solo se importi funzioni specifiche

#### WEB OF SCIENCE PARSER ####
def parse_wos_data(datapath: str) -> list[dict]:  
    """PARSER FOR WEB OF SCIENCE TXT and CIW"""
    elem_data = []
    data = {}
    current_key = None

    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Salta le prime due righe di intestazione tipiche dei file WoS
    for line in lines[2:]:
        line = line.rstrip()
        
        # Salta righe vuote o la fine del file (EF)
        if line.strip() != "" and line.strip() != "EF":
            
            # Fine del record
            if line.startswith("ER"):
                if data:
                    elem_data.append(data.copy())
                current_key = None
                data = {}
                
            # Continuazione del campo precedente (inizia con due spazi)
            elif line.startswith("  "):
                if current_key and current_key in data:
                    # Alcuni campi in WoS preferiscono la concatenazione stringa, altri liste di stringhe
                    if current_key in {"DE", "C3", "EM", "FU", "FX", "WC"}:
                        current_value = " ".join(data[current_key]) + " " + line.strip()
                        data[current_key] = [current_value]
                    else:
                        data[current_key].append(line.strip())
                        
            # Nuova chiave
            else:
                line = line.strip()
                key_value = line.split(" ", 1)
                if len(key_value) == 2:
                    key, value = key_value
                    data[key] = [value]
                    current_key = key

    return elem_data


#### COCHRANE PARSER ####
def parse_cochrane_data(datapath: str) -> list[dict]:
    data = []
    current_record = {}
    current_key = None # Inizializzato per evitare UnboundLocalError
    
    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    for line in lines:
        line = line.strip()
        
        # Riga vuota o nuovo record
        if not line or line.startswith('Record #'):
            if current_record:
                # Pulizia chiavi interne inutili o sporche
                if 'Record' in current_record:
                    del current_record['Record']
                if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
                    current_record['AB'] = current_record['AB'][22:].strip()
                
                data.append(current_record)
                current_record = {}
                current_key = None
            continue

        # Trova colonne con formato 'CHIAVE: valore'
        key_match = re.match(r'^([A-Z]{2,})\s*:\s*(.+)', line)
        if key_match:
            current_key = key_match.group(1)
            value = key_match.group(2)
            
            if current_key in current_record:
                current_record[current_key] += '; ' + value
            else:
                current_record[current_key] = value
        else:
            # Se la riga non ha il formato chiave:valore, accoda al valore precedente
            if current_record and current_key and current_key in current_record:
                current_record[current_key] += ' ' + line.strip()

    # Aggiungi l'ultimo record se il file non terminava con riga vuota
    if current_record:
        if 'Record' in current_record:
            del current_record['Record']
        if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
            current_record['AB'] = current_record['AB'][22:].strip()
        data.append(current_record)

    return data


#### PUBMED MEDLINE PARSER (Definita da voi, in uso su file_extractor) ####
def parse_pubmed_medline_text(text: str) -> list[dict]:
    """
    Legge un blocco di testo in formato MEDLINE (PubMed) e lo converte
    in una lista di dizionari. Gestisce i campi ripetuti (es. multipli 'AU')
    creando automaticamente delle liste.
    """
    records = []
    current_record = {}
    current_key = None

    for line in text.splitlines():
        if not line.strip():
            continue

        if line.startswith("PMID-"):
            if current_record:
                records.append(current_record)
            current_record = {}

        if len(line) > 6 and line[4:6] == "- ":
            current_key = line[:4].strip()
            value = line[6:].strip()

            if current_key in current_record:
                if isinstance(current_record[current_key], list):
                    current_record[current_key].append(value)
                else:
                    current_record[current_key] = [current_record[current_key], value]
            else:
                current_record[current_key] = value

        elif current_key and line.startswith("      "):
            if isinstance(current_record[current_key], list):
                current_record[current_key][-1] += " " + line.strip()
            else:
                current_record[current_key] += " " + line.strip()

    if current_record:
        records.append(current_record)

    return records


#### PUBMED XML PARSER ####
def parse_pubmed_xml_node(article_node: ET.Element) -> dict:
    """
    Estrae le informazioni da un nodo <PubmedArticle> (XML) e le formatta
    in un dizionario compatibile con lo standard Medline.
    """
    record = {}

    def get_text(xpath: str, default: str = "") -> str:
        node = article_node.find(xpath)
        return node.text.strip() if node is not None and node.text else default

    record["PMID"] = get_text(".//MedlineCitation/PMID")
    record["TI"] = get_text(".//ArticleTitle")
    record["JT"] = get_text(".//Journal/Title")
    record["TA"] = get_text(".//Journal/ISOAbbreviation")
    
    pub_date_year = get_text(".//PubDate/Year")
    if not pub_date_year:
        pub_date_year = get_text(".//PubDate/MedlineDate")[:4]
    record["DP"] = pub_date_year
    
    record["VI"] = get_text(".//JournalIssue/Volume")
    record["IP"] = get_text(".//JournalIssue/Issue")
    record["PG"] = get_text(".//Pagination/MedlinePgn")
    record["LA"] = get_text(".//Language")

    abstract_texts = article_node.findall(".//AbstractText")
    if abstract_texts:
        record["AB"] = " ".join([node.text.strip() for node in abstract_texts if node.text])

    doi_node = article_node.find(".//ArticleId[@IdType='doi']")
    if doi_node is not None and doi_node.text:
        record["LID"] = f"{doi_node.text} [doi]" 

    au_list = []
    fau_list = []
    affiliations = set() 

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

        affil = author.find(".//Affiliation")
        if affil is not None and affil.text:
            affiliations.add(affil.text)

    if au_list: record["AU"] = au_list
    if fau_list: record["FAU"] = fau_list
    if affiliations: record["AD"] = list(affiliations)

    keywords = article_node.findall(".//Keyword")
    if keywords:
        record["OT"] = [k.text for k in keywords if k.text]

    pub_types = article_node.findall(".//PublicationType")
    if pub_types:
        record["PT"] = [pt.text for pt in pub_types if pt.text]

    return record