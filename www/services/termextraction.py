from .utils import *


def term_extraction(df, field="TI", ngrams=1, stemming=False, language="english", remove_numbers=True, remove_terms=None, keep_terms=None, synonyms=None, verbose=False):
    """
    Extract terms from a specified field in the DataFrame.

    Args:
        df: A DataFrame object containing the data.
        field: The field from which to extract terms.
        ngrams: The number of n-grams to extract.
        stemming: Whether to apply stemming.
        language: The language for stopwords and stemming.
        remove_numbers: Whether to remove numbers.
        remove_terms: Terms to remove from the text.
        keep_terms: Terms to keep in the text.
        synonyms: Synonyms to merge into a single term.
        verbose: Whether to print the results.

    Returns:
        A DataFrame with the extracted terms.
    """
    M = df.get()

    # Load and update stopwords
    overall_start_time = time.time()

    # Load and update stopwords
    stop_words = set(nltk_stopwords.words(language))
    custom_stopwords = {"elsevier", "springer", "mdpi", "using", "however", "-", "present", "proposes",
                        "used", "proposed", "reserved", "recent", "years", "research", "study", "aims", 
                        "paper", "papers", "article", "based", "literature", "matter", "articles",
                        "published", "aims", "limitations"}
    
    stop_words.update(custom_stopwords)
    stop_words = list(stop_words)  # Convert to list for compatibility with CountVectorizer

    # Convert text to lowercase and remove special characters
    M[f"{field}_TM"] = M[field].astype(str).str.lower()
    M[f"{field}_TM"] = M[f"{field}_TM"].str.replace(r"[^a-z\s-]", " ", regex=True)

    # Replace hyphens with underscores
    M[f"{field}_TM"] = M[f"{field}_TM"].str.replace("-", "__")

    # Remove numbers (if requested)
    if remove_numbers:
        M[f"{field}_TM"] = M[f"{field}_TM"].str.replace(r"\d+", "", regex=True)

    # Replace terms to keep
    if keep_terms:
        keep_terms = [term.lower().replace(" ", "_").replace("-", "__") for term in keep_terms]
        for term in keep_terms:
            M[f"{field}_TM"] = M[f"{field}_TM"].str.replace(term.replace(" ", "_"), term)

    # Remove specific terms
    if remove_terms:
        remove_terms = [term.lower() for term in remove_terms]
        for term in remove_terms:
            M[f"{field}_TM"] = M[f"{field}_TM"].str.replace(term, "")

    # Apply stemming (if requested)
    if stemming:
        stemmer = SnowballStemmer(language)
        M[f"{field}_TM"] = M[f"{field}_TM"].apply(lambda x: " ".join([stemmer.stem(word) for word in x.split()]))

    # Count terms with CountVectorizer
    vectorizer = CountVectorizer(ngram_range=(ngrams, ngrams), stop_words=stop_words, token_pattern=r"(?u)\b\w\w+\b")
    X = vectorizer.fit_transform(M[f"{field}_TM"])
    terms = vectorizer.get_feature_names_out()

    # Handle synonyms
    if synonyms:
        print("Handling synonyms...")
        synonyms_dict = {key.lower(): [s.lower() for s in values] for key, values in synonyms.items()}
        terms = [next((k for k, v in synonyms_dict.items() if term in v), term) for term in terms]

    # Create DataFrame of extracted terms
    terms_df = pd.DataFrame(X.toarray(), columns=terms, index=M.index)

    # Combine extracted terms into a list for each document
    start_time = time.time()

    # Get a boolean matrix for terms present (saves operations) (OPTIMIZATION BY GPT from 30 seconds to 0.1 seconds)
    non_zero_mask = terms_df.values > 0  # Mask for values > 0
    # Create a list of lists with the actual terms for each document
    extracted_terms = [
        [terms_df.columns[i].replace("__", "-").replace("_", " ").replace("-", " ")
         for i in np.where(non_zero_mask[row_idx])[0]]
        for row_idx in range(non_zero_mask.shape[0])
    ]

    # Assign the result to the destination column
    M[f"{field}_TM"] = extracted_terms
    print(f"Term combination into lists per document done in {time.time() - start_time:.4f} seconds")

    # Show results (if verbose is True)
    if verbose:
        print(terms_df.sum().sort_values(ascending=False).head(25))

    # Finalize the output
    df.set(M)

    return df
