import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# Patch rispetto al file fornito:
# - gli import sono espliciti invece di `from www.services import *`, perche' la
#   funzione usa solo pandas/plotly e non deve dipendere da oggetti globali;
# - e' stato aggiunto `_resolve_dataframe` per poter usare la stessa funzione sia
#   in Biblioshiny, dove arriva un reactive.Value con `.get()`, sia nei controlli
#   diretti sulla pipeline ETL, dove arriva un normale pd.DataFrame;
# - il calcolo della tabella annuale e' stato isolato in un helper per validare
#   `PY` prima del plot: la versione originale assumeva anni gia' numerici.
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
        raise ValueError("get_annual_production requires a non-empty DataFrame.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("get_annual_production expects a pandas DataFrame or an object with .get().")
    # La copia evita che conversioni/filtri interni modifichino il DataFrame
    # condiviso dalla dashboard.
    return data.copy()


def _annual_publications_table(data):
    """
    Costruisce la tabella della produzione scientifica per anno.

    Args:
        data (pd.DataFrame): DataFrame standardizzato contenente la colonna
            `PY` con l'anno di pubblicazione.

    Returns:
        pd.DataFrame: Tabella con colonne `Year` e `Freq`, includendo anche
        gli anni senza pubblicazioni con frequenza pari a 0.

    Raises:
        ValueError: Se `PY` manca o non contiene anni validi.
    """
    if "PY" not in data.columns:
        raise ValueError("Missing required column: PY.")

    # Dopo la standardizzazione `PY` puo' arrivare come stringa; senza questa
    # conversione `range(min_year, max_year + 1)` puo' fallire o ordinare male.
    years = pd.to_numeric(data["PY"], errors="coerce").dropna().astype(int)
    if years.empty:
        raise ValueError("Column PY does not contain valid publication years.")

    publications_per_year = years.value_counts().sort_index().reset_index()
    publications_per_year.columns = ["Year", "Freq"]

    min_year = int(publications_per_year["Year"].min())
    max_year = int(publications_per_year["Year"].max())
    all_years = pd.DataFrame({"Year": range(min_year, max_year + 1)})

    # Come in bibliometrix, gli anni senza pubblicazioni vengono mantenuti a 0:
    # cosi' il grafico mostra anche i buchi temporali della collezione.
    publications_per_year = all_years.merge(
        publications_per_year, on="Year", how="left"
    ).fillna({"Freq": 0})
    publications_per_year["Freq"] = publications_per_year["Freq"].astype(int)
    return publications_per_year


def get_annual_production(df):
    """
    Calcola e visualizza la produzione scientifica annuale.

    Usa la colonna standardizzata `PY` per contare quanti documenti sono stati
    pubblicati in ciascun anno. E' pensata per funzionare sia dalla dashboard
    Biblioshiny sia passando direttamente il DataFrame prodotto dalla pipeline
    ETL.

    Args:
        df: `pd.DataFrame` standardizzato oppure reactive.Value di Shiny che
            contiene un DataFrame.

    Returns:
        tuple: `(fig, publications_per_year)`, dove `fig` e' un
        `go.FigureWidget` Plotly e `publications_per_year` e' una tabella con
        colonne `Year` e `Freq`.

    Raises:
        ValueError: Se il DataFrame e' vuoto o non contiene anni validi in `PY`.
        TypeError: Se l'input non puo' essere risolto in un DataFrame pandas.
    """
    data = _resolve_dataframe(df)
    publications_per_year = _annual_publications_table(data)

    # Create the plot
    fig = px.line(
        publications_per_year, x="Year", y="Freq",
        labels={"Year": "Year", "Freq": "Articles"},
        markers=True
    )

    # Customize the layout and tooltips (hover)
    fig.update_traces(
        line=dict(color='#5567BB', width=3),
        marker=dict(size=8, color='#1f77b4', line=dict(width=1, color='white')),
        hovertemplate=(
            "<b>Year:</b> %{x}<br>"
            "<b>Articles:</b> %{y}<extra></extra>"
        )
    )

    fig.update_layout(
        xaxis=dict(
            tickmode='array',
            tickvals=publications_per_year["Year"][::2],  # Show every second year
            showline=True,
            linewidth=1,
            linecolor='#CCCCCC',
            mirror=True,
            ticks='outside',
            tickfont=dict(size=13)
        ),
        yaxis=dict(
            title="Articles",
            showline=True,
            linewidth=1,
            linecolor='#CCCCCC',
            mirror=True,
            ticks='outside',
            tickfont=dict(size=13),
            zeroline=True,
            zerolinecolor='#E0E0E0'
        ),
        xaxis_title="Year",
        plot_bgcolor='white',
        font=dict(color="#222222", size=14, family="Segoe UI, Arial"),
        margin=dict(l=50, r=30, t=60, b=50),
        height=600,
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Segoe UI, Arial",
            bordercolor="#1f77b4"
        )
    )

    # Customize the grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#EFEFEF')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#EFEFEF')
    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}

    return fig, publications_per_year
