import pandas as pd
import plotly.graph_objects as go


# Patch rispetto al file fornito:
# - import espliciti invece di `from www.services import *`;
# - aggiunto `_resolve_dataframe`, per usare la funzione sia con reactive.Value
#   di Biblioshiny sia con DataFrame pandas prodotti direttamente dalla ETL;
# - aggiunta normalizzazione dei nomi delle metriche, perche' la dashboard passa
#   valori tecnici (`n_docs`, `percentage`, `freq_measure`) mentre la tabella usa
#   etichette leggibili.
FREQUENCY_LABELS = {
    "n_docs": "N. of Documents",
    "percentage": "Percentage",
    "freq_measure": "Fractionalized Frequency",
}


def _resolve_dataframe(df):
    """
    Risolve l'input dati accettando sia Biblioshiny sia test diretti.

    Args:
        df: Un `pd.DataFrame` gia' standardizzato oppure un oggetto reattivo
            Shiny che espone il metodo `.get()`.

    Returns:
        pd.DataFrame: Copia del DataFrame da usare nei calcoli.

    Raises:
        ValueError: Se il valore reattivo non contiene dati.
        TypeError: Se l'input risolto non e' un DataFrame pandas.
    """
    if isinstance(df, pd.DataFrame):
        data = df
    elif hasattr(df, "get"):
        data = df.get()
    else:
        data = df

    if data is None:
        raise ValueError("get_relevant_authors requires a non-empty DataFrame.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("get_relevant_authors expects a pandas DataFrame or an object with .get().")
    # Le trasformazioni successive toccano `AU`; la copia evita side effect sul
    # DataFrame globale della dashboard.
    return data.copy()


def _normalize_frequency(frequency):
    """
    Converte il valore tecnico della dashboard nel nome colonna leggibile.

    Args:
        frequency (str): Valore selezionato nella UI o nome gia' leggibile.

    Returns:
        str: Etichetta da usare come colonna e titolo dell'asse.
    """
    # La versione fornita confrontava direttamente stringhe come "percentage" e
    # usava poi quella stessa stringa come nome colonna. Questo rendeva output e
    # grafico meno coerenti con la dashboard/table.
    return FREQUENCY_LABELS.get(frequency, frequency)


def get_relevant_authors(df, num_of_authors, frequency="N. of Documents"):
    """
    Individua e visualizza gli autori piu' rilevanti della collezione.

    Usa la colonna standardizzata `AU`, attesa come lista di autori per
    documento. La metrica puo' essere numero di documenti, percentuale o
    frequenza frazionata.

    Args:
        df: `pd.DataFrame` standardizzato oppure reactive.Value di Shiny che
            contiene un DataFrame.
        num_of_authors (int): Numero massimo di autori da mostrare nel grafico.
        frequency (str): Metrica da usare. Accetta valori UI come `n_docs`,
            `percentage`, `freq_measure` oppure etichette leggibili.

    Returns:
        tuple: `(fig, table_relevant_authors)`, dove `fig` e' un
        `go.FigureWidget` Plotly e la tabella contiene gli autori ordinati per
        la metrica selezionata.

    Raises:
        ValueError: Se manca `AU` o se non contiene liste di autori valide.
        TypeError: Se l'input non puo' essere risolto in un DataFrame pandas.
    """
    data = _resolve_dataframe(df)
    frequency = _normalize_frequency(frequency)

    if "AU" not in data.columns:
        raise ValueError("Missing required column: AU.")

    # `AU` deve essere una lista di autori prodotta dallo standardizer. I valori
    # non-lista vengono ignorati per evitare di iterare stringhe carattere per
    # carattere o di rompere il calcolo fractional.
    data = data.dropna(subset=["AU"]).copy()

    # Ensure all values in the "AU" column are lists
    data["AU"] = data["AU"].apply(lambda x: x if isinstance(x, list) else [])
    data = data[data["AU"].apply(len) > 0].copy()
    if data.empty:
        raise ValueError("Column AU does not contain valid author lists.")

    # Flatten the list of authors and calculate occurrences
    all_authors = [author for sublist in data["AU"] for author in sublist]
    author_counts = pd.Series(all_authors).value_counts()

    # Apply the selected frequency calculation
    if frequency == "Percentage":
        author_counts = (author_counts / len(data) * 100).round(1)
    elif frequency == "Fractionalized Frequency":
        # Calculate fractional counts
        fractional_counts = data["AU"].apply(lambda authors: 1 / len(authors) if authors else 0)
        # Dopo i filtri l'indice del DataFrame puo' non essere 0..n. La versione
        # fornita usava `fractional_counts[i]` con enumerate e poteva associare
        # pesi errati o generare KeyError. `zip` mantiene allineate righe e pesi.
        fractional_authors = [
            (author, weight)
            for authors, weight in zip(data["AU"], fractional_counts)
            for author in authors
        ]
        fractional_df = pd.DataFrame(fractional_authors, columns=["Author", "Weight"])
        author_counts = fractional_df.groupby("Author")["Weight"].sum().sort_values(ascending=False).round(1)
    
    author_counts = author_counts.reset_index()
    author_counts.columns = ["Authors", frequency]
    
    # Truncate author names to 50 characters
    author_counts["Authors"] = author_counts["Authors"].str[:50]
    table_relevant_authors = author_counts

    # Limit the number of authors to display
    if num_of_authors > len(author_counts):
        num_of_authors = len(author_counts)
    author_counts = author_counts.head(num_of_authors).copy()

    # Create the plot (use scatter instead of scatter with orientation='h')
    fig = go.Figure()

    # Add a thick line from each label to its marker
    for i, row in author_counts.iterrows():
        fig.add_shape(
            type="line",
            x0=0,
            x1=row[frequency],
            y0=i,
            y1=i,
            line=dict(color="#e0e0e0", width=5),
            layer="below",
        )

    fig.add_trace(
        go.Scatter(
            x=author_counts[frequency],
            y=list(range(len(author_counts))),
            mode="markers+text",
            marker=dict(
                size=18 + 6 * (author_counts[frequency] / author_counts[frequency].max()),
                color=author_counts[frequency],
                colorscale=[[0, "#B3D1F2"], [1, "#5567BB"]],
                line=dict(width=1, color="#E0E0E0"),
                opacity=0.95,
                showscale=False,
            ),
            text=author_counts[frequency],
            textposition="top center",  
            textfont=dict(color="#5567BB", size=13),  
            hovertemplate=(
                "<b>Author:</b> %{customdata}<br>"
                "<b>" + frequency + ":</b> %{x}<extra></extra>"
            ),
            customdata=author_counts["Authors"],
        )
    )

    # Add horizontal grid lines for each author (lighter)
    for i in range(len(author_counts)):
        fig.add_shape(
            type="line",
            x0=0,
            x1=author_counts[frequency].max(),
            y0=i,
            y1=i,
            line=dict(color="#E0E0E0", width=2),
            layer="below",
        )

    # Set x-axis ticks to 0, 5, 10, etc.
    max_x = author_counts[frequency].max()
    tick_step = 5
    x_ticks = list(range(0, int(max_x) + tick_step, tick_step))
    if x_ticks[-1] < max_x:
        x_ticks.append(int(max_x))

    fig.update_yaxes(
        tickvals=list(range(len(author_counts))),
        ticktext=author_counts["Authors"],
        autorange="reversed",
        showgrid=False,
        title="Authors",
        tickfont=dict(size=13),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#F0F0F0",
        zeroline=False,
        tickvals=x_ticks,
        title=frequency,
        tickfont=dict(size=13),
    )
    fig.update_layout(
        plot_bgcolor='white',
        font=dict(color="#222222", size=14, family="Segoe UI, Arial"),
        margin=dict(l=0, r=0, t=0, b=0),
        height=50 + 90 * len(author_counts),
        showlegend=False,
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Segoe UI, Arial",
            bordercolor="#5567BB"
        ),
        coloraxis_showscale=False,
    )
    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}

    return fig, table_relevant_authors
