from www.services import *


def get_corresponding_author_countries(df, top_k_countries):
    """
    Generate a plot and table of the most common corresponding author countries.
    
    Args:
        df: A DataFrame object containing the data.
        top_k_countries: The number of top countries to display.
    
    Returns:
        A Plotly figure object and a DataFrame of the most common corresponding author countries.
    """
    # Estrai i metadati "AU_CO" e "AU1_CO" e verifica il tipo di dati
    df = metaTagExtraction(df, Field="AU_CO")  # Assumendo che `metaTagExtraction` sia già definita
    df = metaTagExtraction(df, Field="AU1_CO")
    data = df.get()  # Se `df` è un oggetto reattivo

    # Assicurati che le colonne siano di tipo stringa e rimuovi righe con valori mancanti
    data = data.dropna(subset=["AU1_CO", "AU_CO"])
    data["AU_CO"] = data["AU_CO"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))
    data["AU"] = data["AU"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x))

    # Determina il numero di collaborazioni per riga
    data["nCO"] = data["AU_CO"].apply(lambda x: 1 if len(set(x.split(", "))) > 1 else 0)

    # Conta il numero di articoli, SCP e MCP per paese
    country_counts = data.groupby("AU1_CO").agg(
        Articles=("AU", "count"),
        SCP=("nCO", lambda x: (x == 0).sum()),
        MCP=("nCO", lambda x: (x == 1).sum())
    ).reset_index()

    # Rinomina la colonna "AU1_CO" in "Country"
    country_counts = country_counts.rename(columns={"AU1_CO": "Country"})

    # Ordina i paesi per numero totale di articoli e seleziona i primi `top_k_countries`
    top_countries = country_counts.sort_values(by="Articles", ascending=False)
    top_country_names = top_countries["Country"].tolist()

    # Filtra i dati per includere solo i paesi selezionati
    filtered_country_counts = country_counts[country_counts["Country"].isin(top_country_names)]

    # Prepara i dati per il grafico
    filtered_country_counts["Country"] = pd.Categorical(
        filtered_country_counts["Country"], categories=top_country_names, ordered=True
    )

    filtered_country_counts = filtered_country_counts.sort_values(by="Articles", ascending=False)
    table = filtered_country_counts

    # Calcola la frequenza degli articoli e il rapporto MCP
    total_articles = filtered_country_counts["Articles"].sum()
    filtered_country_counts["Article_Freq"] = filtered_country_counts["Articles"] / total_articles
    filtered_country_counts["MCP_Ratio"] = filtered_country_counts["MCP"] / filtered_country_counts["Articles"]

    # Rimuovi righe con valori mancanti nella colonna "Country"
    filtered_country_counts = filtered_country_counts.dropna(subset=["Country"])
    filtered_country_counts = filtered_country_counts.head(top_k_countries)
    filtered_country_counts = filtered_country_counts.sort_values(by="Articles", ascending=True)

    # Crea il grafico
    fig = px.bar(
        filtered_country_counts.melt(id_vars="Country", value_vars=["SCP", "MCP"], var_name="Collaboration", value_name="Freq"),
        x="Freq",
        y="Country",
        color="Collaboration",
        orientation="h",
        labels={"Country": "Countries", "Freq": "N. of Documents", "Collaboration": "Collaboration"},
        template="simple_white"
    )

    fig.update_layout(
        height=600,
        xaxis=dict(title="N. of Documents", showgrid=True, gridcolor="lightgrey"),
        yaxis=dict(title="Countries", showgrid=True, gridcolor="lightgrey"),
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            title="Collaboration",
            orientation="h",
            x=0.5,
            xanchor="center",
            y=1.1
        )
    )
    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}

    return fig, table
