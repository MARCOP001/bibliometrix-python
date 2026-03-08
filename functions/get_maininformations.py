from www.services import *


def get_main_informations(df, log=False):
    """
    Calculate various filters and metrics for the DataFrame.

    Args:
        df: A DataFrame object containing the data.
        log: A boolean value indicating whether to save the unique authors, keywords, and references to text files.

    Returns:
        A DataFrame with additional columns for filters and metrics.
    """
    data = df.get()

    #### Min and Max Year ####
    start_time = time.time()
    # Calculate the minimum and maximum publication years
    data["Min_Year"] = data["PY"].min()
    data["Max_Year"] = data["PY"].max()
    print(f"Min and Max Year calculation time: {time.time() - start_time:.4f} seconds")

    #### Unique Sources ####
    start_time = time.time()
    data["Unique_SO"] = data["SO"].nunique()
    print(f"Unique Sources calculation time: {time.time() - start_time:.4f} seconds")

    #### Annual Growth Rate (CAGR) ####
    start_time = time.time()
    # Calculate the number of publications per year
    publications_per_year = data["PY"].value_counts().sort_index()

    # Calculate the number of years in the range
    ny = data["PY"].max() - data["PY"].min()

    # Calculate the Compound Annual Growth Rate (CAGR)
    if len(publications_per_year) > 1:
        cagr = round(((publications_per_year.iloc[-1] / publications_per_year.iloc[0]) ** (1 / ny) - 1) * 100, 2)
    else:
        cagr = 0  # If there's only one year of data, CAGR is 0

    data["CAGR"] = cagr
    print(f"CAGR calculation time: {time.time() - start_time:.4f} seconds")

    #### Unique Authors ####
    start_time = time.time()
    # Ensure the 'AU' column exists
    if "AU" not in data.columns:
        data["AU"] = ""
    else:
        data["AU"] = data["AU"].fillna("")

    # Assume that data["AU"] is a list of strings already split
    AU_list = data["AU"] 

    # Remove empty spaces and empty strings
    listAU = [author for sublist in AU_list for author in sublist if author]

    # Remove duplicates
    listAU = list(set(listAU))

    # Save the list of authors to a text file
    if log:
        with open("authors_list.txt", "w", encoding="utf-8") as file:
            for authors in listAU:
                file.write(f"{authors}\n")

    # Count the number of unique authors
    count_AU = len(listAU)

    # Save the count of unique authors in the data structure (optional)
    data["Unique_AU"] = count_AU
    print(f"Unique Authors calculation time: {time.time() - start_time:.4f} seconds")

    #### Authors of single-authored docs ####
    start_time = time.time()
    def count_authors(entry):
        if isinstance(entry, list):  # If it's a list, calculate the length directly
            return len(entry)
        elif isinstance(entry, str):  # If it's a string, split by the delimiter ";"
            return len(entry.split(';'))
        else:
            return 0  # In case of NaN values or other types, return 0

    # Apply the function and get the number of authors for each document
    nAU = data['AU'].apply(count_authors)

    # Filter documents with a single author and get the number of unique authors
    single_authored_docs = len(data[nAU == 1]['AU'].apply(lambda x: x[0] if isinstance(x, list) else x.split(';')[0]).unique())

    # Add the count to the dataset
    data["Authors_of_single_authored_docs"] = single_authored_docs
    print(f"Authors of single-authored docs calculation time: {time.time() - start_time:.4f} seconds")

    #### International Co-Authorship ####
    start_time = time.time()
    # Ensure the 'AU_CO' column exists
    if "AU_CO" not in data.columns:
        # Extract the required metadata
        df = metaTagExtraction(df, "AU_CO")
        data = df.get()
        
    # Calculate "Country_Count" with a vectorized function
    data["Country_Count"] = data["AU_CO"].apply(lambda x: len(set(x)))
    
    # Calculate "International_Co_Authorship" without loop
    coll = data[data["Country_Count"] > 1].shape[0]
    data["International_Co_Authorship"] = 100 * coll / data.shape[0]
    
    # Save the list of international co-authors to a text file
    if log:
        with open("international_co_authorship.txt", "w", encoding="utf-8") as file:
            file.write("\n".join(data["AU_CO"]))
    print(f"International Co-Authorship calculation time: {time.time() - start_time:.4f} seconds")

    #### Co-Authors per Doc ####
    start_time = time.time()
    data["Co_Authors_per_Doc"] = round(nAU.mean(), 2)
    print(f"Co-Authors per Doc calculation time: {time.time() - start_time:.4f} seconds")

    #### Author's Keywords (DE) ####
    start_time = time.time()
    # Ensure the 'DE' column exists
    if "DE" not in data.columns:
        data["DE"] = ""
    else:
        data["DE"] = data["DE"].fillna("")

    # Split the 'DE' column by ';' and flatten the list
    DE = pd.Series([item.upper() for sublist in data["DE"] for item in sublist])

    # Remove extra spaces, periods, and commas, and keep only unique values
    DE = DE.str.replace(r"\s+|\.|,", " ", regex=True).str.strip().unique()

    # Remove any NaN values
    DE = DE[~pd.isna(DE)]
    DE = DE[DE != "NAN"]
    
    # Save the unique keywords to a text file
    if log:
        with open("unique_keywords.txt", "w", encoding="utf-8") as file:
            for keyword in DE:
                file.write(f"{keyword}\n")

    # Add the count of unique keywords to the dataset
    data["Authors_Keywords_DE"] = len(DE)
    print(f"Author's Keywords (DE) calculation time: {time.time() - start_time:.4f} seconds")

    #### References per Doc ####
    start_time = time.time()
    # Ensure the 'CR' column exists
    if "CR" not in data.columns:
        data["CR"] = ""
    else:
        data["CR"] = data["CR"].fillna("")

    # Split the 'CR' and flatten the list
    CR = pd.Series([item.upper() for sublist in data["CR"] for item in sublist])

    # Remove extra spaces, periods, and commas, and keep only unique values
    CR = CR.str.replace(r"\s+|\|,", " ", regex=True).str.strip().unique()

    # Remove any NaN values
    CR = CR[~pd.isna(CR)]
    
    # Save the unique references to a text file
    if log:
        with open("unique_references.txt", "w", encoding="utf-8") as file:
            for reference in CR:
                file.write(f"{reference}\n")

    # Count the number of unique references
    nCR = len(CR)
    if nCR == 1:
        nCR = 0

    # Add the count of unique references to the dataset
    data["References_per_Doc"] = nCR
    print(f"References per Doc calculation time: {time.time() - start_time:.4f} seconds")

    #### Document Average Age ####
    start_time = time.time()
    # Calculate the average age of the documents
    current_year = pd.Timestamp.now().year
    data["Document_Age"] = current_year - data["PY"]
    data["Document_Average_Age"] = round(data["Document_Age"].mean(), 2)
    print(f"Document Average Age calculation time: {time.time() - start_time:.4f} seconds")

    #### Average citations per doc ####
    start_time = time.time()
    data["Average_Citations_per_Doc"] = round(data["TC"].mean(), 2)
    print(f"Average citations per doc calculation time: {time.time() - start_time:.4f} seconds")

    return data
