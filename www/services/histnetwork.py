from .utils import *
from .cocmatrix import *


def histNetwork(df, min_citations=0, sep=";", network=True):
    """
    Create a historical network of citations from a DataFrame containing metadata of scientific papers.
    
    Args:
        df (DataFrame): A DataFrame containing metadata of scientific papers.
        min_citations (int): Minimum number of citations to include a paper in the analysis.
        sep (str): Separator used to separate references in the citation network.
        network (bool): If True, a citation network is created.
    
    Returns:
        A dictionary containing the following keys:
            - NetMatrix: A DataFrame containing the citation network.
            - histData: A DataFrame containing the metadata of the papers.
            - M: A DataFrame containing the metadata of the papers with the Local Citation Score (LCS).
            - LCS: A list containing the Local Citation Score of each paper.
    """
    M = df.get()
    db = M['DB'][0]

    # Ensure required fields are present
    if 'DI' not in M:
        M['DI'] = ""
    M['DI'] = M['DI'].fillna("")

    if 'CR' not in M:
        print("\nYour collection does not contain Cited References metadata (Field CR is missing)\n")
        return None

    # Fill missing values in TC
    M['TC'] = M['TC'].fillna(0)

    if db == "Web_of_Science":
        results = wos(M, min_citations=min_citations, sep=sep, network=network)
    elif db == "Scopus":
        results = scopus(M, min_citations=min_citations, sep=sep, network=network)
    else:
        print("\nDatabase not compatible with direct citation analysis\n")
        return None

    return results


def wos(M, min_citations, sep, network):

    print("\nWOS DB:\nSearching local citations (LCS) by reference items (SR) and DOIs...\n")

    # Sort data by publication year
    M = M.sort_values(by="PY").reset_index(drop=True)

    # Add unique labels to papers
    M['Paper'] = np.arange(0, len(M))
    M['nLABEL'] = np.arange(0, len(M))

    # Process cited references (CR)
    CR = []
    for i, refs in enumerate(M['CR']):
        for ref in refs:
            # Extract DOI
            doi = ""
            if 'DOI' in ref:
                parts = ref.split('DOI', 1)
                doi = parts[1].strip() if len(parts) > 1 else ""
            # Extract AU, PY, SO
            ref_parts = ref.split(',')
            au = ref_parts[0].replace('.', ' ').strip() if len(ref_parts) > 0 else ""
            py = ref_parts[1].strip() if len(ref_parts) > 1 else ""
            so = ref_parts[2].strip() if len(ref_parts) > 2 else ""
            sr = f"{au}, {py}, {so}"
            CR.append({'ref': ref, 'Paper': i, 'DI': doi, 'AU': au, 'PY': py, 'SO': so, 'SR': sr})

    print(f"\nAnalyzing {len(CR)} reference items...\n")

    CR_df = pd.DataFrame(CR)

    # Add LABEL field to M and CR
    M['LABEL'] = M['SR_FULL'].fillna('').str.upper() + " DOI " + M['DI'].fillna('').str.upper()
    M['LABEL'] = M['LABEL'].str.strip()
    CR_df['LABEL'] = CR_df['SR'].fillna('').str.upper() + " DOI " + CR_df['DI'].fillna('').str.upper()
    CR_df['LABEL'] = CR_df['LABEL'].str.strip()

    # Match references with papers (left join as in R)
    L = pd.merge(M, CR_df, on='LABEL', how='left', suffixes=('_M', '_CR'))
    L = L[L['Paper_CR'].notnull()]
    L['CITING'] = M.loc[L['Paper_CR'], 'LABEL'].values
    L['nCITING'] = M.loc[L['Paper_CR'], 'nLABEL'].values
    L['CIT_PY'] = M.loc[L['Paper_CR'], 'PY'].values

    # Compute Local Citation Scores (LCS)
    LCS = L.groupby('nLABEL').size().reset_index(name='LCS')
    M['LCS'] = M['nLABEL'].map(LCS.set_index('nLABEL')['LCS']).fillna(0).astype(int)

    # Prepare histData
    histData = M[M['TC'] >= min_citations][['LABEL', 'TI', 'DE', 'ID', 'DI', 'PY', 'LCS', 'TC']]
    histData.columns = ['Paper', 'Title', 'Author_Keywords', 'KeywordsPlus', 'DOI', 'Year', 'LCS', 'GCS']

    WLCR = None
    if network:
        # Build citation network
        CITING = L.groupby('CITING').agg(
            LCR=('LABEL', lambda x: ';'.join(x.dropna())),
            PY=('CIT_PY', 'first'),
            Paper=('Paper_CR', 'first')
        ).reset_index().sort_values(by='PY')

        # Assign LCR to the correct Paper index (Paper is 0-based)
        M['LCR'] = ""
        for idx, row in CITING.iterrows():
            paper_idx = int(row['Paper'])
            if 0 <= paper_idx < len(M):
                M.at[paper_idx, 'LCR'] = row['LCR']

        # Assign unique names to duplicated LABELs
        st = False
        i = 0
        while not st:
            ind = M['LABEL'].duplicated(keep=False)
            if ind.any():
                i += 1
                M.loc[ind, 'LABEL'] = M.loc[ind, 'LABEL'] + f"-{chr(96 + i)}"
            else:
                st = True
        M.index = M['LABEL'].str.strip()

        M['LCR'] = M['LCR'].fillna('')

        # Ensure all papers are included as both rows and columns
        WLCR = cocMatrix(reactive.Value(M), Field="LCR", sep=sep)
        
        # Trova le LABEL mancanti
        missing_LABEL = set(M.index) - set(WLCR.columns)
        
        # Aggiungi colonne per le LABEL mancanti con valori 0 (in un'unica operazione per evitare frammentazione)
        if missing_LABEL:
            missing_df = pd.DataFrame(0, index=WLCR.index, columns=list(missing_LABEL))
            WLCR = pd.concat([WLCR, missing_df], axis=1)

        num_ones = (WLCR.values == 1).sum()
        print(f"\nFound {len(M[M['LCS'] > 0])} documents with non-empty Local Citations (LCS)\n")

    results = {
        'NetMatrix': WLCR,
        'histData': histData,
        'M': M,
        'LCS': M['LCS'].tolist()
    }

    return results


def scopus(M, min_citations=0, sep=";", network=True):

    print("\nScopus DB:\nProcessing citations...\n")

    # Process the citations
    CR = M['CR']
    CR = pd.DataFrame({
        'SR_citing': np.repeat(M['SR'], CR.str.len()),
        'ref': [item for sublist in CR for item in sublist]
    })
    
    # Extract publication year (PY) and author (AU) from the citation
    CR['PY'] = CR['ref'].str.extract(r'.*\((\d{4})\).*').astype(float)
    CR['AU'] = CR['ref'].str.extract(r'^(.*?),').apply(lambda x: x.str.replace('.', '').str.strip())
    CR['PP'] = CR['ref'].str.extract(r'PP\. (\d+-\d+)')
    
    # Filter valid citations
    CR = CR.dropna(subset=['PY'])
    print(f"\nFiltered {len(CR)} valid citations...\n")

    # Prepare the M dataframe for the join
    M_merge = M[['AU', 'PY', 'BP', 'EP', 'SR']].copy()
    M_merge['AU'] = M_merge['SR'].str.extract(r'^(.*?),').apply(lambda x: x.str.replace('.', '').str.strip())
    M_merge['BP'] = pd.to_numeric(M_merge['BP'], errors='coerce')
    M_merge['EP'] = pd.to_numeric(M_merge['EP'], errors='coerce')
    M_merge['PP'] = M_merge.apply(lambda row: f"{row['BP']}-{row['EP']}" if pd.notna(row['BP']) else np.nan, axis=1)
    M_merge['Included'] = True
    M_merge.rename(columns={'SR': 'SR_cited'}, inplace=True)
    
    # Join CR with M_merge to find matches
    CR = CR.merge(M_merge, on=['PY', 'AU'], how='left')
    CR = CR[CR['Included'].notna()]
    print(f"\nFound {len(CR)} matching citations...\n")
    
    # Calculate the Local Citation Score (LCS)
    LCS = CR.groupby('SR_cited').size().reset_index(name='LCS')
    
    # Merge LCS scores with M
    M = M.merge(LCS, left_on='SR', right_on='SR_cited', how='left').fillna({'LCS': 0})
    print(f"\nCalculated Local Citation Scores (LCS) for {len(M)} papers...\n")
    
    # Select and rename columns for historical data
    histData = M[['SR_FULL', 'TI', 'DE', 'ID', 'DI', 'PY', 'LCS', 'TC']].copy()
    histData.columns = ['Paper', 'Title', 'Author_Keywords', 'KeywordsPlus', 'DOI', 'Year', 'LCS', 'GCS']
    histData = histData.sort_values(by='Year').reset_index(drop=True)
    
    # Build the co-citation matrix if network is True
    WLCR = None
    if network:
        print("\nBuilding co-citation matrix...\n")
        
        # Add self-citations to ensure each document cites itself
        CRadd = pd.DataFrame({'SR_citing': M['SR'].unique(), 'SR_cited': M['SR'].unique(), 'value': 1})
        
        WLCR = CR[['SR_citing', 'SR_cited']].copy()
        WLCR['value'] = 1
        WLCR = pd.concat([WLCR, CRadd]).drop_duplicates()
        
        WLCR = WLCR.pivot_table(index='SR_citing', columns='SR_cited', values='value', fill_value=0)
        
        # Filter only the rows corresponding to cited documents
        WLCR = WLCR.loc[WLCR.index.isin(CRadd['SR_cited'])]
        print(f"\nCo-citation matrix built with {WLCR.shape[0]} rows and {WLCR.shape[1]} columns...\n")
    
    results = {
        'NetMatrix': WLCR,
        'histData': histData,
        'M': M,
        'LCS': M['LCS'].tolist()
    }

    return results
