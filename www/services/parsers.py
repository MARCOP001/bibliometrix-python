"""
Parser per convertire export bibliografici grezzi in dizionari intermedi.

I parser di questo modulo leggono formati specifici delle sorgenti esterne
senza applicare lo schema finale dell'applicazione. 

La standardizzazione dei
campi e dei tipi resta responsabilita' di "standardizer.py".
"""

import logging
import re
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


# PARSER WEB OF SCIENCE 
def parse_wos_data(datapath: str) -> list[dict]:
    """Legge un export testuale Web of Science e lo converte in record grezzi.

    Args:
        datapath: Percorso del file Web of Science in formato ".txt" o ".ciw".

    Returns:
        Lista di dizionari, uno per articolo. I valori sono mantenuti come liste di stringhe per rappresentare correttamente campi ripetuti o multilinea.

    Raises:
        FileNotFoundError: Se "datapath" non esiste.
        OSError: Se il file non puo' essere aperto o letto.
        UnicodeDecodeError: Se il contenuto non e' decodificabile in UTF-8.

    Notes:
        Il parser riconosce "ER" come fine record, "EF" come fine file e le righe indentate come continuazioni del campo precedente. 
        Non effettua conversioni verso lo schema Bibliometrix finale.
    """
    elem_data = []
    data = {}
    current_key = None
    logger.info("Parsing Web of Science: %s", datapath)

    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    # Le prime righe degli export WoS contengono metadati del file, non campi bibliografici dell'articolo.
    for line in lines[2:]:
        line = line.rstrip()

        # EF chiude l'export completo e non appartiene ad alcun record.
        if line.strip() != "" and line.strip() != "EF":

            # ER segnala che il record corrente e' completo e puo' essere salvato.
            if line.startswith("ER"):
                if data:
                    elem_data.append(data.copy())
                current_key = None
                data = {}

            # Le righe indentate continuano il campo precedente secondo il formato testuale WoS.
            elif line.startswith("  "):
                if current_key and current_key in data:
                    # Questi campi rappresentano testo descrittivo continuo: unirli evita di frammentare abstract, keyword o categorie.
                    if current_key in {"DE", "C3", "EM", "FU", "FX", "WC"}:
                        current_value = " ".join(data[current_key]) + " " + line.strip()
                        data[current_key] = [current_value]
                    else:
                        # I campi ripetibili restano liste per non perdere la separazione tra autori, riferimenti o valori analoghi.
                        data[current_key].append(line.strip())

            else:
                line = line.strip()
                # La separazione sul primo spazio preserva eventuali spazi nel valore del campo, ad esempio nei titoli.
                key_value = line.split(" ", 1)
                if len(key_value) == 2:
                    key, value = key_value
                    data[key] = [value]
                    current_key = key

    logger.info("Parsing Web of Science completato: %s record", len(elem_data))
    return elem_data


# PARSER COCHRANE 
def parse_cochrane_data(datapath: str) -> list[dict]:
    """Legge un export Cochrane Library e lo converte in record grezzi.

    Args:
        datapath: Percorso del file testuale esportato da Cochrane Library.

    Returns:
        Lista di dizionari, uno per record bibliografico, con valori testuali aggregati per tag.

    Raises:
        FileNotFoundError: Se "datapath" non esiste.
        OSError: Se il file non puo' essere aperto o letto.
        UnicodeDecodeError: Se il contenuto non e' decodificabile in UTF-8.

    Notes:
        Le righe "Record #" e le righe vuote delimitano i record. Le chiavi ripetute vengono concatenate con "; " per restare compatibili con i formatter downstream.
    """
    data = []
    current_record = {}
    current_key = None
    logger.info("Parsing Cochrane: %s", datapath)

    with open(datapath, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()

        # In Cochrane un record termina prima di una riga vuota o del successivo identificatore "Record #".
        if not line or line.startswith('Record #'):
            if current_record:
                # Il campo Record e' un identificatore interno dell'export, non un metadato bibliografico usato dalle analisi.
                if 'Record' in current_record:
                    del current_record['Record']
                # Cochrane antepone questa intestazione fissa al testo dell'abstract; rimuoverla evita rumore nelle analisi testuali.
                if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
                    current_record['AB'] = current_record['AB'][22:].strip()

                data.append(current_record)
                current_record = {}
                current_key = None
            continue

        # I tag Cochrane sono formati da almeno due lettere maiuscole seguite da due punti, ad esempio "AU: Rossi M".
        key_match = re.match(r'^([A-Z]{2,})\s*:\s*(.+)', line)
        if key_match:
            current_key = key_match.group(1)
            value = key_match.group(2)

            # I tag ripetuti vengono serializzati con lo stesso delimitatore usato dai formatter per i campi multivalore.
            if current_key in current_record:
                current_record[current_key] += '; ' + value
            else:
                current_record[current_key] = value
        else:
            # Una riga senza tag prosegue il contenuto del campo precedente, tipicamente abstract o note descrittive.
            if current_record and current_key and current_key in current_record:
                current_record[current_key] += ' ' + line.strip()

    # Gestisce export che terminano senza separatore dopo l'ultimo record.
    if current_record:
        if 'Record' in current_record:
            del current_record['Record']
        if 'AB' in current_record and current_record['AB'].startswith('Abstract - Background'):
            current_record['AB'] = current_record['AB'][22:].strip()
        data.append(current_record)

    logger.info("Parsing Cochrane completato: %s record", len(data))
    return data


# PARSER PUBMED (Testo MEDLINE)
def parse_pubmed_medline_text(text: str) -> list[dict]:
    """Elabora testo MEDLINE PubMed e produce record grezzi per articolo.

    Args:
        text: Contenuto completo del file MEDLINE come singola stringa.

    Returns:
        Lista di dizionari. I campi ripetuti vengono convertiti in liste, mentre i campi presenti una sola volta restano stringhe.

    Notes:
        "PMID-" viene interpretato come inizio di un nuovo record. Le righe con sei spazi iniziali continuano il campo precedente, come previsto dal formato MEDLINE.
    """
    records = []
    current_record = {}
    current_key = None
    logger.info("Parsing PubMed MEDLINE: %s righe", len(text.splitlines()))

    for line in text.splitlines():
        if not line.strip():
            continue

        # PMID apre un nuovo record; quello precedente e' completo quando esiste.
        if line.startswith("PMID-"):
            if current_record:
                records.append(current_record)
            current_record = {}

        # MEDLINE usa una label a quattro caratteri seguita da "- ".
        if len(line) > 6 and line[4:6] == "- ":
            current_key = line[:4].strip()
            value = line[6:].strip()

            if current_key in current_record:
                if isinstance(current_record[current_key], list):
                    current_record[current_key].append(value)
                else:
                    # Il primo duplicato stabilisce che il campo e' multivalore.
                    current_record[current_key] = [current_record[current_key], value]
            else:
                current_record[current_key] = value

        elif current_key and line.startswith("      "):
            if isinstance(current_record[current_key], list):
                # La continuazione appartiene all'ultimo valore del campo ripetuto, non a un nuovo elemento della lista.
                current_record[current_key][-1] += " " + line.strip()
            else:
                current_record[current_key] += " " + line.strip()

    # Il formato non richiede un marker esplicito di chiusura a fine file.
    if current_record:
        records.append(current_record)

    logger.info("Parsing PubMed MEDLINE completato: %s record", len(records))
    return records


# PARSER PUBMED (XML)
def parse_pubmed_xml_node(article_node: ET.Element) -> dict:
    """Estrae un nodo XML PubMed in un dizionario compatibile con MEDLINE.

    Args:
        article_node: Nodo "PubmedArticle" dell'albero XML PubMed.

    Returns:
        Dizionario con tag in stile MEDLINE, ad esempio "TI" per il titolo, "AU" per gli autori e "AB" per l'abstract.

    Notes:
        Il parser legge solo i campi usati dalla pipeline downstream. 
        I valori assenti vengono omessi o sostituiti con stringa vuota tramite helper locale, senza validare lo schema finale.
    """
    record = {}

    def get_text(xpath: str, default: str = "") -> str:
        """Restituisce il testo di un nodo XML o un fallback sicuro.

        Args:
            xpath: Percorso XPath relativo a "article_node".
            default: Valore da restituire quando il nodo o il testo mancano.

        Returns:
            Testo del nodo senza spazi esterni, oppure "default".

        Notes:
            L'helper evita controlli ripetuti sui nodi opzionali del formato PubMed XML.
        """
        node = article_node.find(xpath)
        return node.text.strip() if node is not None and node.text else default

    # Campi bibliografici principali mappati sulla nomenclatura MEDLINE.
    record["PMID"] = get_text(".//MedlineCitation/PMID")
    record["TI"] = get_text(".//ArticleTitle")  # Title
    record["JT"] = get_text(".//Journal/Title") # Journal Title
    record["TA"] = get_text(".//Journal/ISOAbbreviation")

    pub_date_year = get_text(".//PubDate/Year")
    if not pub_date_year:
        # PubMed usa MedlineDate quando non espone un anno strutturato.
        pub_date_year = get_text(".//PubDate/MedlineDate")[:4]
    record["DP"] = pub_date_year # Data di pubblicazione

    record["VI"] = get_text(".//JournalIssue/Volume")
    record["IP"] = get_text(".//JournalIssue/Issue")
    record["PG"] = get_text(".//Pagination/MedlinePgn") 
    record["LA"] = get_text(".//Language")

    # Gli abstract PubMed possono essere segmentati in piu' sezioni etichettate.
    abstract_texts = article_node.findall(".//AbstractText")
    if abstract_texts:
        record["AB"] = " ".join([node.text.strip() for node in abstract_texts if node.text])

    doi_node = article_node.find(".//ArticleId[@IdType='doi']")
    if doi_node is not None and doi_node.text:
        record["LID"] = f"{doi_node.text} [doi]" # Formattato secondo lo standard Medline

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

        # Il set mantiene una sola copia delle affiliazioni duplicate tra autori.
        affil = author.find(".//Affiliation")
        if affil is not None and affil.text:
            affiliations.add(affil.text)

    if au_list: record["AU"] = au_list
    if fau_list: record["FAU"] = fau_list
    if affiliations: record["AD"] = list(affiliations)

    keywords = article_node.findall(".//Keyword")
    if keywords:
        record["OT"] = [k.text for k in keywords if k.text] # OT = Other Terms (Keywords)

    pub_types = article_node.findall(".//PublicationType")
    if pub_types:
        record["PT"] = [pt.text for pt in pub_types if pt.text]

    return record
