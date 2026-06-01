import numpy as np
import pandas as pd
import plotly.graph_objects as go


# Patch rispetto al file fornito:
# - import espliciti invece di `from www.services import *`;
# - `_resolve_dataframe` rende la funzione usabile sia dalla dashboard Shiny sia
#   da un DataFrame pandas gia' prodotto dalla ETL;
# - sono stati aggiunti controlli su `SO`, perche' la legge di Bradford si basa
#   sulla frequenza delle fonti e fallisce se la standardizzazione non la produce.
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
        raise ValueError("get_bradford_law requires a non-empty DataFrame.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("get_bradford_law expects a pandas DataFrame or an object with .get().")
    # Usiamo una copia per non filtrare/modificare il DataFrame condiviso in app.
    return data.copy()


def get_bradford_law(df):
    """
    Calcola e visualizza la distribuzione delle fonti secondo Bradford.

    Usa la colonna standardizzata `SO` per ordinare le fonti per frequenza,
    calcolare la frequenza cumulata e assegnare le zone di Bradford. Il grafico
    evidenzia il nucleo di fonti piu' produttive della collezione.

    Args:
        df: `pd.DataFrame` standardizzato oppure reactive.Value di Shiny che
            contiene un DataFrame.

    Returns:
        tuple: `(fig, df_bradford)`, dove `fig` e' un grafico Plotly e
        `df_bradford` contiene `SO`, `Rank`, `Freq`, `cumFreq` e `Zone`.

    Raises:
        ValueError: Se manca `SO` o se non contiene fonti valide.
        TypeError: Se l'input non puo' essere risolto in un DataFrame pandas.
    """
    # Sort data by frequency of occurrence (equivalent to R's sort(table(M$SO), decreasing = TRUE))
    data = _resolve_dataframe(df)

    if "SO" not in data.columns:
        raise ValueError("Missing required column: SO.")

    # La versione iniziale assumeva fonti sempre presenti. Con file reali/ETL e'
    # meglio rimuovere NaN e stringhe vuote prima di calcolare le zone Bradford.
    data = data.dropna(subset=["SO"]).copy()
    data = data[data["SO"].astype(str).str.strip() != ""]
    if data.empty:
        raise ValueError("Column SO does not contain valid source names.")

    source_counts = data["SO"].value_counts()
    
    # Total number of sources
    n = source_counts.sum()
    # Cumulative sum of the frequencies (equivalent to cumsum in R)
    cumSO = source_counts.cumsum()
    
    # Define the cut points for Bradford's Law (zones)
    cutpoints = [1, n * 0.33, n * 0.67, float('inf')]
    _ = pd.cut(cumSO, bins=cutpoints, labels=["Zone 1", "Zone 2", "Zone 3"])
    
    # Find the cut points for "Core" sources
    a = (cumSO < n * 0.33).sum() + 1
    b = (cumSO < n * 0.67).sum() + 1
    Z = ["Zone 1"] * a + ["Zone 2"] * (b - a) + ["Zone 3"] * (len(cumSO) - b)
    
    # Create a DataFrame for Bradford's Law table
    df_bradford = pd.DataFrame({
        "SO": cumSO.index.str[:25],  # Shorten the source names to 25 characters if necessary
        "Rank": range(1, len(cumSO) + 1),
        "Freq": source_counts.values,
        "cumFreq": cumSO.values,
        "Zone": Z
    })
    
    # Create the Plotly figure
    fig = go.Figure()

    # Add the line plot without text above the points
    fig.add_trace(go.Scatter(
        x=np.log(df_bradford["Rank"]),
        y=df_bradford["Freq"],
        mode='lines+markers',
        name='Articles per Source',
        marker=dict(
            color='#5567BB',
            size=10,
            line=dict(width=1, color='white'),
            opacity=0.95
        ),
        line=dict(color='#5567BB', width=2, shape='spline'),
        hovertemplate=(
            "<b>Source:</b> %{customdata[0]}<br>"
            "<b>Rank:</b> %{x:.2f}<br>"
            "<b>N. of Documents:</b> %{y}<br>"
            "<b>Zone:</b> %{customdata[1]}<extra></extra>"
        ),
        customdata=np.stack([df_bradford["SO"], df_bradford["Zone"]], axis=-1)
    ))

    # Add the "Core Sources" area with the rectangle
    fig.add_shape(
        type="rect",
        # Nelle collezioni piccole `a` puo' indicare oltre l'ultimo indice.
        # Il `min(...)` evita IndexError mantenendo il core sull'ultima fonte valida.
        x0=0,
        x1=np.log(df_bradford["Rank"].iloc[min(a - 1, len(df_bradford) - 1)]),
        y0=0,
        y1=df_bradford["Freq"].max(),
        fillcolor="#B3D1F2",
        opacity=0.18,
        line_width=0,
        layer="below"
    )

    # Add the "Core Sources" annotation with smaller font
    fig.add_annotation(
        # Stessa protezione dell'area: la versione fornita usava Rank[a] e
        # poteva andare fuori indice quando il dataset aveva poche fonti.
        x=np.log(df_bradford["Rank"].iloc[min(a - 1, len(df_bradford) - 1)]) / 2,
        y=df_bradford["Freq"].max() * 0.85,
        text="<b>Core<br>Sources</b>",
        showarrow=False,
        font=dict(size=15, color="#5567BB", family="Segoe UI, Arial"),
        align="center",
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="#B3D1F2",
        borderpad=4,
        borderwidth=1,
    )

    # Customize the X axis labels (log scale) with smaller font
    fig.update_layout(
        xaxis=dict(
            title="Source log(Rank)",
            tickmode='array',
            tickvals=np.log(df_bradford["Rank"][:a]),
            ticktext=df_bradford["SO"][:a],
            tickangle=90,
            showgrid=True,
            gridcolor="#F0F0F0",
            zeroline=False,
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            title="N. of Documents",
            showgrid=True,
            gridcolor="#F0F0F0",
            zeroline=False,
            tickfont=dict(size=10),
        ),
        plot_bgcolor='white',
        font=dict(color="#222222", size=11, family="Segoe UI, Arial"),
        margin=dict(l=80, r=40, t=40, b=120),
        height=800,
        showlegend=False,
        hoverlabel=dict(
            bgcolor="white",
            font_size=11,
            font_family="Segoe UI, Arial",
            bordercolor="#5567BB"
        ),
    )
    
    return fig, df_bradford
