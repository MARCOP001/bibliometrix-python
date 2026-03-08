from www.services import *


def get_database(input):
    """
    Determine the database based on the user's selection.
    
    Args:
        input: An object that provides user input methods.
        
    Returns:
        A string representing the name of the database.
    """
    if input.select() == "1A":  # Bibliographic databases
        
        database = input.database()
        
        if database == "wos":
            database = "Web of Science"
        elif database == "scopus":
            database = "Scopus"
        elif database == "dimensions":
            database = "Dimensions"
        elif database == "lens":
            database = "Lens.org"
        elif database == "pubmed":
            database = "PubMed"
        elif database == "cochrane":
            database = "Cochrane Library"
    
    elif input.select() == "1B":  # Bibliometrix database
        database = "Bibliometrix"
    
    elif input.select() == "1C":  # Sample database
        database = "Sample"
    
    return database
