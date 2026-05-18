from .utils import *


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
            current_record['AB'] = current_record['AB'][20:].strip()
        data.append(current_record)

    return data





#parser
