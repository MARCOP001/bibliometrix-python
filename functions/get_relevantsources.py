import pandas as pd
import plotly.graph_objects as go


# Patch rispetto al file fornito:
# - import espliciti al posto di `from www.services import *`, per rendere chiaro
#   che la funzione dipende solo da pandas/plotly;
# - `_resolve_dataframe` permette di usare sia `df.get()` di Biblioshiny sia un
#   DataFrame pandas ottenuto direttamente dalla pipeline ETL;
# - sono stati aggiunti controlli sulla colonna `SO`, perche' "Relevant Sources"
#   ha senso solo se la standardizzazione ha prodotto i nomi delle riviste/fonti.
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
        raise ValueError("get_relevant_sources requires a non-empty DataFrame.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("get_relevant_sources expects a pandas DataFrame or an object with .get().")
    # La copia protegge il DataFrame caricato in app da eventuali filtri locali.
    return data.copy()


def get_relevant_sources(df, num_of_sources):
    """
    Individua e visualizza le fonti piu' rilevanti della collezione.

    Conta i documenti per valore della colonna standardizzata `SO` (source,
    journal o venue) e restituisce sia la tabella completa sia il grafico delle
    prime `num_of_sources` fonti.

    Args:
        df: `pd.DataFrame` standardizzato oppure reactive.Value di Shiny che
            contiene un DataFrame.
        num_of_sources (int): Numero massimo di fonti da mostrare nel grafico.

    Returns:
        tuple: `(fig, table_relevant_sources)`, dove `fig` e' un
        `go.FigureWidget` Plotly e `table_relevant_sources` contiene tutte le
        fonti ordinate per `N. of Documents`.

    Raises:
        ValueError: Se manca `SO` o se non contiene nomi di fonti validi.
        TypeError: Se l'input non puo' essere risolto in un DataFrame pandas.
    """
    data = _resolve_dataframe(df)

    if "SO" not in data.columns:
        raise ValueError("Missing required column: SO.")

    # La versione fornita eliminava solo i NaN. Qui scartiamo anche stringhe
    # vuote/spazi: altrimenti una fonte vuota puo' comparire tra le piu' rilevanti.
    data = data.dropna(subset=["SO"])
    data = data[data["SO"].astype(str).str.strip() != ""]
    if data.empty:
        raise ValueError("Column SO does not contain valid source names.")

    # Count the occurrences of each source
    source_counts = data["SO"].value_counts().reset_index()
    source_counts.columns = ["Sources", "N. of Documents"]
    # Truncate source names to 50 characters
    # source_counts["Sources"] = source_counts["Sources"].str[:50]
    table_relevant_sources = source_counts

    # Limit the number of sources to display
    if num_of_sources > len(source_counts):
        num_of_sources = len(source_counts)
    # `.copy()` e' necessario perche' `head()` restituisce una slice: subito dopo
    # aggiungiamo `Sources_wrapped` e vogliamo evitare SettingWithCopyWarning/errori.
    source_counts = source_counts.head(num_of_sources).copy()

    # Truncate long source names and add line breaks every 50 characters
    def wrap_label(label, width=50):
        """
        Spezza una label lunga in piu' righe HTML per renderla leggibile.

        Args:
            label (str): Testo della fonte da visualizzare sull'asse.
            width (int): Numero massimo di caratteri per riga.

        Returns:
            str: Label con tag `<br>` inseriti a intervalli regolari.
        """
        return '<br>'.join([label[i:i+width] for i in range(0, len(label), width)])
    source_counts["Sources_wrapped"] = source_counts["Sources"].apply(wrap_label)

    # Create the plot (use scatter instead of scatter with orientation='h')
    fig = go.Figure()

    # Add a thick line from each label to its marker
    for i, row in source_counts.iterrows():
        fig.add_shape(
            type="line",
            x0=0,
            x1=row["N. of Documents"],
            y0=i,
            y1=i,
            line=dict(color="#e0e0e0", width=5),
            layer="below",
        )

    fig.add_trace(
        go.Scatter(
            x=source_counts["N. of Documents"],
            y=list(range(len(source_counts))),
            mode="markers+text",
            marker=dict(
                size=18 + 6 * (source_counts["N. of Documents"] / source_counts["N. of Documents"].max()),
                color=source_counts["N. of Documents"],
                colorscale=[[0, "#B3D1F2"], [1, "#5567BB"]],
                line=dict(width=1, color="#E0E0E0"),
                opacity=0.95,
                showscale=False,
            ),
            text=source_counts["N. of Documents"],
            textposition="top center",  
            textfont=dict(color="#5567BB", size=13),  
            hovertemplate=(
                "<b>Source:</b> %{y}<br>"
                "<b>N. of Documents:</b> %{x}<extra></extra>"
            ),
        )
    )

    # Add horizontal grid lines for each source (lighter)
    for i in range(len(source_counts)):
        fig.add_shape(
            type="line",
            x0=0,
            x1=source_counts["N. of Documents"].max(),
            y0=i,
            y1=i,
            line=dict(color="#E0E0E0", width=2),
            layer="below",
        )

    # Set x-axis ticks to 0, 5, 10, etc.
    max_x = source_counts["N. of Documents"].max()
    tick_step = 5
    x_ticks = list(range(0, int(max_x) + tick_step, tick_step))
    if x_ticks[-1] < max_x:
        x_ticks.append(int(max_x))

    fig.update_yaxes(
        tickvals=list(range(len(source_counts))),
        ticktext=source_counts["Sources_wrapped"],
        autorange="reversed",
        showgrid=False,
        title="Sources",
        tickfont=dict(size=13),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#F0F0F0",
        zeroline=False,
        tickvals=x_ticks,
        title="N. of Documents",
        tickfont=dict(size=13),
    )
    fig.update_layout(
        plot_bgcolor='white',
        font=dict(color="#222222", size=14, family="Segoe UI, Arial"),
        margin=dict(l=220, r=40, t=60, b=40),
        height=50 + 90 * len(source_counts),
        showlegend=False,
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Segoe UI, Arial",
            bordercolor="#5567BB"
        ),
    )
    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}

    return fig, table_relevant_sources
