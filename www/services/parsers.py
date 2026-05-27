from .utils import *
import re

#### WEB OF SCIENCE PARSER ####
def parse_wos_data(datapath):  # PARSER FOR WEB OF SCIENCE TXT and CIW
    elem_data = []
    data = {}
    current_key = None

    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for i, line in enumerate(lines[2:], start=2):
        # line = line.decode('utf-8')
        line = line.rstrip()
        if line.strip() != " " and line.strip() != "EF":
            if line.startswith("ER"):
                elem_data.append(data.copy())
                current_key = None
                data = {}
            elif line.startswith("  "):
                if current_key:
                    if current_key in data:
                        if current_key in {"DE", "C3", "EM", "FU", "FX", "WC"}:
                            current_value = " ".join(data[current_key]) + " " + line.strip()
                            data[current_key] = [current_value]
                        else:
                            data[current_key].append(line.strip())
                    else:
                        data[current_key] = [line.strip()]
            else:
                line = line.strip()
                key_value = line.split(" ", 1)
                if len(key_value) == 2:
                    key, value = key_value
                    data[key] = [value]
                    current_key = key

    return elem_data


#### PUBMED PARSER ####
def parse_pubmed_data(datapath):  # PARSER FOR PUBMED TXT
    data = []
    current_record = {}
    
    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    for line in lines:
        # line = line.decode('utf-8')  # Decode the line from bytes to string
        if line.strip() == '':
            # If the line is empty, add the current record to the data
            if current_record:
                data.append(current_record)
                current_record = {}
            continue

        key_match = re.match(r'^([A-Z]+)\s*-\s*(.+)', line)
        if key_match:
            key = key_match.group(1)
            value = key_match.group(2)

            if key in current_record:
                current_record[key] += ';' + value
            else:
                current_record[key] = value
        else:
            # Add the content to the previous key
            current_record[key] += ' ' + line.strip()

    # Add the last record if present
    if current_record:
        data.append(current_record)

    return data


#### COCHRANE PARSER ####
def parse_cochrane_data(datapath):
    data = []
    current_record = {}
    
    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    for line in lines:
        line = line.strip()
        if not line:
            # If the line is empty, add the current record to the data
            if current_record:
                if 'Record' in current_record:
                    del current_record['Record']
                if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
                    current_record['AB'] = current_record['AB'][22:].strip()
                data.append(current_record)
                current_record = {}
            continue
        
        if line.startswith('Record #'):
            # If the line starts with 'Record #', it is the beginning of a new record
            if current_record:
                if b'Record' in current_record:
                    del current_record[b'Record']
                if b'AB' in current_record and current_record[b'AB'].startswith(b'Abstract - Background'):
                    current_record[b'AB'] = current_record[b'AB'][22:].strip()
                data.append(current_record)
                current_record = {}
            continue

        # Find columns with the format 'KEY: value'
        key_match = re.match(r'^([A-Z]{2,})\s*:\s*(.+)', line)
        if key_match:
            key = key_match.group(1)
            value = key_match.group(2)
            
            if key in current_record:
                current_record[key] += '; ' + value
            else:
                current_record[key] = value
        else:
            # If the line does not match the format 'KEY: value', add the content to the previous key
            if current_record:
                current_record[key] += ' ' + line.strip()

    # Add the last record if present
    if current_record:
        if 'Record' in current_record:
            del current_record['Record']
        if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
            current_record['AB'] = current_record['AB'][22:].strip()
        data.append(current_record)

    return data

#### FUNZIONI DEFINITE DA NOI

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
        # Ignora righe vuote
        if not line.strip():
            continue

        # Ogni nuovo record PubMed inizia col tag PMID
        if line.startswith("PMID-"):
            if current_record:
                records.append(current_record)
            current_record = {}

        # Identifica un nuovo tag (es. "TI  - ") - Il tag occupa i primi 4 caratteri
        if len(line) > 6 and line[4:6] == "- ":
            current_key = line[:4].strip()
            value = line[6:].strip()

            if current_key in current_record:
                # Se la chiave esiste già (es. un secondo autore "AU"), trasformala in lista
                if isinstance(current_record[current_key], list):
                    current_record[current_key].append(value)
                else:
                    current_record[current_key] = [current_record[current_key], value]
            else:
                # Altrimenti salva il valore scalare
                current_record[current_key] = value

        # Se non c'è un tag, è la continuazione della riga precedente (es. un Abstract lungo)
        elif current_key and line.startswith("      "):
            if isinstance(current_record[current_key], list):
                current_record[current_key][-1] += " " + line.strip()
            else:
                current_record[current_key] += " " + line.strip()

    # Aggiungi l'ultimo record
    if current_record:
        records.append(current_record)

    return records


import xml.etree.ElementTree as ET

def parse_pubmed_xml_node(article_node: ET.Element) -> dict:
    """
    Estrae le informazioni da un nodo <PubmedArticle> (XML) e le formatta
    in un dizionario compatibile con lo standard Medline (chiavi PMID, TI, AU, ecc.).
    Questo permette di riutilizzare la funzione transform_pubmed_record dello standardizer.
    """
    record = {}

    # Helper interno per estrarre in sicurezza il testo dai nodi XML
    def get_text(xpath: str, default: str = "") -> str:
        node = article_node.find(xpath)
        return node.text.strip() if node is not None and node.text else default

    # Campi Scalari Diretti
    record["PMID"] = get_text(".//MedlineCitation/PMID")
    record["TI"] = get_text(".//ArticleTitle")
    record["JT"] = get_text(".//Journal/Title")
    record["TA"] = get_text(".//Journal/ISOAbbreviation")
    
    # In PubMed XML l'anno può essere in <Year> o dentro un <MedlineDate>
    pub_date_year = get_text(".//PubDate/Year")
    if not pub_date_year:
        pub_date_year = get_text(".//PubDate/MedlineDate")[:4]
    record["DP"] = pub_date_year
    
    record["VI"] = get_text(".//JournalIssue/Volume")
    record["IP"] = get_text(".//JournalIssue/Issue")
    record["PG"] = get_text(".//Pagination/MedlinePgn")
    record["LA"] = get_text(".//Language")

    # Abstract (può essere diviso in più tag <AbstractText> es. Background, Methods)
    abstract_texts = article_node.findall(".//AbstractText")
    if abstract_texts:
        record["AB"] = " ".join([node.text.strip() for node in abstract_texts if node.text])

    # DOI (LID in Medline)
    doi_node = article_node.find(".//ArticleId[@IdType='doi']")
    if doi_node is not None and doi_node.text:
        record["LID"] = f"{doi_node.text} [doi]" # Manteniamo il format atteso dal tuo standardizer

    # Liste Complesse: Autori e Affiliazioni
    au_list = []
    fau_list = []
    affiliations = set() # Usiamo un set per evitare doppioni sulle istituzioni

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

        # Affiliazioni
        affil = author.find(".//Affiliation")
        if affil is not None and affil.text:
            affiliations.add(affil.text)

    if au_list: record["AU"] = au_list
    if fau_list: record["FAU"] = fau_list
    if affiliations: record["AD"] = list(affiliations)

    # Liste Complesse: Keywords e Publication Types
    keywords = article_node.findall(".//Keyword")
    if keywords:
        record["OT"] = [k.text for k in keywords if k.text]

    pub_types = article_node.findall(".//PublicationType")
    if pub_types:
        record["PT"] = [pt.text for pt in pub_types if pt.text]

    return record