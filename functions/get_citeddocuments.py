import pandas as pd
import plotly.graph_objects as go


# Patch rispetto al file fornito:
# - import espliciti invece di `from www.services import *`;
# - `_resolve_dataframe` consente di usare la funzione sia in Biblioshiny sia
#   direttamente sul DataFrame restituito dalla pipeline ETL;
# - rimossa la dipendenza implicita da `metaTagExtraction(df, "SR")`: la traccia
#   richiede di verificare che la standardizzazione produca gia' colonne come
#   `SR`, quindi qui validiamo quel contratto invece di ricostruirlo dentro.
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
        raise ValueError("get_cited_documents requires a non-empty DataFrame.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("get_cited_documents expects a pandas DataFrame or an object with .get().")
    # I calcoli aggiungono colonne temporanee (`TCperYear`, `NormalizedTC`), quindi
    # la copia evita di sporcare il DataFrame usato dal resto della dashboard.
    return data.copy()


def get_cited_documents(df, num_of_cited_docs, cited_docs_measure):
    """
    Individua e visualizza i documenti piu' citati globalmente.

    Usa le colonne standardizzate `SR`, `DI`, `TC` e `PY` per costruire una
    classifica dei documenti per citazioni totali o citazioni per anno. Calcola
    anche `NormalizedTC`, cioe' le citazioni normalizzate rispetto alla media
    degli articoli pubblicati nello stesso anno.

    Args:
        df: `pd.DataFrame` standardizzato oppure reactive.Value di Shiny che
            contiene un DataFrame.
        num_of_cited_docs (int): Numero massimo di documenti da mostrare nel
            grafico.
        cited_docs_measure (str): Metrica di ranking, `total_cit` oppure
            `total_cit_per_year`.

    Returns:
        tuple: `(fig, table)`, dove `fig` e' un `go.FigureWidget` Plotly e
        `table` contiene la classifica completa con DOI, citazioni totali,
        citazioni annue e citazioni normalizzate.

    Raises:
        ValueError: Se il numero richiesto non e' positivo, la metrica non e'
            valida, mancano colonne richieste o non ci sono documenti validi.
        TypeError: Se l'input non puo' essere risolto in un DataFrame pandas.
    """
    df = _resolve_dataframe(df)

    num_of_cited_docs = int(num_of_cited_docs)
    if num_of_cited_docs <= 0:
        raise ValueError("num_of_cited_docs must be greater than zero.")
    # La versione fornita trattava qualunque valore diverso da "total_cit" come
    # citazioni per anno. Qui validiamo il parametro per intercettare errori UI.
    if cited_docs_measure not in {"total_cit", "total_cit_per_year"}:
        raise ValueError("cited_docs_measure must be 'total_cit' or 'total_cit_per_year'.")

    # Queste colonne sono il contratto minimo tra standardizer e funzione:
    # SR identifica il documento, DI il DOI, TC le citazioni, PY l'anno.
    required_columns = {"SR", "DI", "TC", "PY"}
    missing_columns = required_columns.difference(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing_columns))}.")

    # I file importati possono portare anni/citazioni come stringhe; PubMed puo'
    # non fornire citazioni reali, quindi i TC non numerici vengono portati a 0.
    df["PY"] = pd.to_numeric(df["PY"], errors="coerce")
    df["TC"] = pd.to_numeric(df["TC"], errors="coerce").fillna(0)
    df = df.dropna(subset=["SR", "PY"]).copy()
    df = df[df["SR"].astype(str).str.strip() != ""]
    if df.empty:
        raise ValueError("Columns SR and PY do not contain valid cited document data.")
    df["PY"] = df["PY"].astype(int)

    # Prepare the table for ranking documents
    current_year = pd.to_datetime("today").year
    df["TCperYear"] = df["TC"] / (current_year + 1 - df["PY"])
    
    # Normalize within each publication year; years with zero mean citations stay at 0.
    def normalize_year_citations(citations):
        """
        Normalizza le citazioni rispetto alla media dell'anno di pubblicazione.

        Args:
            citations (pd.Series): Citazioni `TC` dei documenti dello stesso
                anno di pubblicazione.

        Returns:
            pd.Series: Valori normalizzati; se la media e' 0 o NaN, restituisce
            zeri per evitare divisioni non interpretabili.
        """
        mean_citations = citations.mean()
        if pd.isna(mean_citations) or mean_citations == 0:
            # Se tutte le citazioni di un anno sono 0, la versione originale
            # produceva divisione per zero/NaN. Restituire 0 mantiene la metrica
            # interpretabile per collezioni senza citazioni, ad esempio PubMed.
            return pd.Series(0.0, index=citations.index)
        return (citations / mean_citations).round(2)

    df["NormalizedTC"] = df.groupby("PY")["TC"].transform(normalize_year_citations)
    
    tab = (
        df.reset_index(drop=True).dropna(subset=["SR"])
        .groupby("SR", as_index=False)
        .agg(DI=("DI", "first"), TotalCitation=("TC", "sum"), TCperYear=("TCperYear", lambda x: round(x.sum(), 1)), NormalizedTC=("NormalizedTC", "sum"))
        .rename(columns={"SR": "Document"})
        .sort_values(by="TotalCitation", ascending=False)
    )

    # Convert columns to numeric to ensure correct calculations
    tab["TotalCitation"] = pd.to_numeric(tab["TotalCitation"])
    tab["TCperYear"] = pd.to_numeric(tab["TCperYear"])
    tab["NormalizedTC"] = pd.to_numeric(tab["NormalizedTC"])
    # Select the appropriate measure based on user input
    if cited_docs_measure == "total_cit":
        tab = tab.sort_values(by="TotalCitation", ascending=False)
        table = tab
        tab = tab.head(num_of_cited_docs)
        tab = tab[["Document", "TotalCitation", "NormalizedTC"]]
        laby = "Global Citations"
    elif cited_docs_measure == "total_cit_per_year":
        tab = tab.sort_values(by="TCperYear", ascending=False)
        table = tab
        tab = tab.head(num_of_cited_docs)[["Document", "TCperYear", "NormalizedTC"]]
        laby = "Global Citations per Year"

    # Create the plot (horizontal scatter with lines, similar to author plot)
    fig = go.Figure()

    # Prepare y-ticks and labels
    y_labels = tab["Document"]
    y_vals = list(range(len(tab)))

    # Add a thick line from each label to its marker
    for i, row in enumerate(tab.itertuples()):
        fig.add_shape(
            type="line",
            x0=0,
            x1=getattr(row, tab.columns[1]),
            y0=i,
            y1=i,
            line=dict(color="#e0e0e0", width=5),
            layer="below",
        )

    metric_column = tab.columns[1]
    metric_values = tab[metric_column]
    max_metric = metric_values.max()
    marker_sizes = (
        [18] * len(tab)
        if pd.isna(max_metric) or max_metric <= 0
        else 18 + 6 * (metric_values / max_metric)
    )
    # Se tutte le citazioni sono 0, dimensione marker e griglia devono comunque
    # essere disegnabili: la versione fornita divideva direttamente per max().

    # Add scatter markers and text
    fig.add_trace(
        go.Scatter(
            x=metric_values,
            y=y_vals,
            mode="markers+text",
            marker=dict(
                size=marker_sizes,
                color=metric_values,
                colorscale=[[0, "#B3D1F2"], [1, "#5567BB"]],
                line=dict(width=1, color="#E0E0E0"),
                opacity=0.95,
                showscale=False,
            ),
            text=metric_values,
            textposition="top center",
            textfont=dict(color="#5567BB", size=13),
            hovertemplate=(
                "<b>Document:</b> %{customdata}<br>"
                "<b>" + laby + ":</b> %{x}<extra></extra>"
            ),
            customdata=tab["Document"],
        )
    )

    # Add horizontal grid lines for each document (lighter)
    grid_max_x = max(float(max_metric), 1.0) if not pd.isna(max_metric) else 1.0
    for i in range(len(tab)):
        fig.add_shape(
            type="line",
            x0=0,
            x1=grid_max_x,
            y0=i,
            y1=i,
            line=dict(color="#E0E0E0", width=2),
            layer="below",
        )

    # Set x-axis ticks
    max_x = grid_max_x
    tick_step = max(1, int(max_x // 6))
    x_ticks = list(range(0, int(max_x) + tick_step, tick_step))
    if x_ticks[-1] < max_x:
        x_ticks.append(int(max_x))

    fig.update_yaxes(
        tickvals=y_vals,
        ticktext=y_labels,
        autorange="reversed",
        showgrid=False,
        title="Document",
        tickfont=dict(size=13),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#F0F0F0",
        zeroline=False,
        tickvals=x_ticks,
        title=laby,
        tickfont=dict(size=13),
    )
    fig.update_layout(
        plot_bgcolor='white',
        font=dict(color="#222222", size=14, family="Segoe UI, Arial"),
        margin=dict(l=0, r=0, t=0, b=0),
        height=50 + 90 * len(tab),
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
    
    return fig, table
