import numpy as np
import pandas as pd
import plotly.graph_objects as go


# Patch rispetto al file fornito:
# - import espliciti invece di `from www.services import *`;
# - `_resolve_dataframe` consente di usare la funzione sia in Biblioshiny sia
#   nei controlli diretti sul DataFrame standardizzato dalla pipeline ETL;
# - aggiunti controlli su `AU`, perche' Lotka richiede una lista di autori per
#   documento e la funzione originale assumeva che il formato fosse sempre valido.
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
        raise ValueError("get_lotka_law requires a non-empty DataFrame.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("get_lotka_law expects a pandas DataFrame or an object with .get().")
    # Lavoriamo su una copia per non normalizzare/filtrare `AU` nel DataFrame
    # condiviso dalla dashboard.
    return data.copy()


def get_lotka_law(df):
    """
    Calcola la legge di Lotka sulla produttivita' degli autori.

    La funzione usa la colonna standardizzata `AU`, attesa come lista di autori
    per documento. Conta quanti articoli ha scritto ogni autore, aggrega gli
    autori per numero di articoli e confronta la distribuzione osservata con una
    distribuzione teorica di Lotka.

    Args:
        df: `pd.DataFrame` standardizzato oppure reactive.Value di Shiny che
            contiene un DataFrame.

    Returns:
        tuple: `(fig, author_prod)`, dove `fig` e' un `go.FigureWidget` Plotly e
        `author_prod` contiene `N.Articles`, `N.Authors`, `Freq` e
        `Theoretical`.

    Raises:
        ValueError: Se manca `AU` o se non contiene autori validi.
        TypeError: Se l'input non puo' essere risolto in un DataFrame pandas.
    """
    
    # Calculate Lotka's Law
    data = _resolve_dataframe(df)

    if "AU" not in data.columns:
        raise ValueError("Missing required column: AU.")

    # La versione fornita faceva direttamente:
    #   for sublist in data["AU"] for author in sublist
    # Questo funziona solo se ogni cella e' gia' una lista. Dopo ETL reali e'
    # possibile trovare NaN/stringhe: vengono filtrati per evitare risultati falsi.
    data = data.dropna(subset=["AU"]).copy()
    data["AU"] = data["AU"].apply(lambda x: x if isinstance(x, list) else [])
    data = data[data["AU"].apply(len) > 0].copy()
    if data.empty:
        raise ValueError("Column AU does not contain valid author lists.")
    
    # Author Productivity (Lotka's Law)
    authors = pd.Series([author.strip() for sublist in data['AU'] for author in sublist if author])
    if authors.empty:
        raise ValueError("Column AU does not contain valid author names.")

    author_prod = authors.value_counts().reset_index()
    author_prod.columns = ['Author', 'N.Articles']
    author_prod = author_prod.groupby('N.Articles').size().reset_index(name='N.Authors')
    author_prod['Freq'] = author_prod['N.Authors'] / author_prod['N.Authors'].sum()
    
    # Calculate theoretical values
    if len(author_prod) > 1:
        lotka_law = np.polyfit(np.log10(author_prod['N.Articles']), np.log10(author_prod['Freq']), 1)
        author_prod['Theoretical'] = 10**(lotka_law[1] - 2 * np.log10(author_prod['N.Articles']))
        author_prod['Theoretical'] = author_prod['Theoretical'] / author_prod['Theoretical'].sum()
    else:
        # `np.polyfit` richiede almeno due punti. Con dataset piccoli o molto
        # uniformi esiste un solo livello di produttivita', quindi usiamo 1.0
        # invece di far fallire il plot.
        author_prod['Theoretical'] = 1.0
    
    # Create the plot with improved hover
    fig = go.Figure()

    # Observed line
    fig.add_trace(
        go.Scatter(
            x=author_prod['N.Articles'],
            y=author_prod['Freq'],
            mode='lines+markers',
            name='Observed',
            marker=dict(
                size=10 + 8 * (author_prod['Freq'] / author_prod['Freq'].max()),
                color=author_prod['Freq'],
                colorscale=[[0, "#B3D1F2"], [1, "#5567BB"]],
                line=dict(width=1, color="#E0E0E0"),
                opacity=0.95,
                showscale=False,
            ),
            line=dict(color="#5567BB", width=2),
            hovertemplate=(
                "<span style='color:white'><b>Documents written:</b> %{x}<br>"
                "<b>% of Authors:</b> %{y:.2%}<br>"
                "<b>N. Authors:</b> %{customdata}</span><extra></extra>"
            ),
            customdata=author_prod['N.Authors'],
        )
    )

    # Theoretical line
    fig.add_trace(
        go.Scatter(
            x=author_prod['N.Articles'],
            y=author_prod['Theoretical'],
            mode='lines+markers',
            name='Theoretical',
            marker=dict(
                size=10,
                color="#888888",
                line=dict(width=1, color="#E0E0E0"),
                opacity=0.7,
            ),
            line=dict(dash='dash', color='black', width=2),
            hovertemplate=(
                "<span style='color:white'><b>Documents written:</b> %{x}<br>"
                "<b>Theoretical % of Authors:</b> %{y:.2%}</span><extra></extra>"
            ),
        )
    )

    # Customize the layout
    fig.update_layout(
        xaxis_title='Documents written',
        yaxis_title='% of Authors',
        plot_bgcolor='white',
        title_font_size=24,
        font=dict(color="#444444"),
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5),
        height=600,
    )

    # Customize the grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#EFEFEF')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#EFEFEF', tickformat=".0%")

    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}
    
    return fig, author_prod
