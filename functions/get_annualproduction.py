import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def _resolve_dataframe(df):
    """Accept both a Shiny reactive value and a plain pandas DataFrame."""
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
    return data.copy()


def _annual_publications_table(data):
    if "PY" not in data.columns:
        raise ValueError("Missing required column: PY.")

    years = pd.to_numeric(data["PY"], errors="coerce").dropna().astype(int)
    if years.empty:
        raise ValueError("Column PY does not contain valid publication years.")

    publications_per_year = years.value_counts().sort_index().reset_index()
    publications_per_year.columns = ["Year", "Freq"]

    min_year = int(publications_per_year["Year"].min())
    max_year = int(publications_per_year["Year"].max())
    all_years = pd.DataFrame({"Year": range(min_year, max_year + 1)})

    publications_per_year = all_years.merge(
        publications_per_year, on="Year", how="left"
    ).fillna({"Freq": 0})
    publications_per_year["Freq"] = publications_per_year["Freq"].astype(int)
    return publications_per_year


def get_annual_production(df):
    """
    Generate a plot of annual scientific production.
    
    Args:
        df: A pandas DataFrame or a Shiny reactive value containing the data.
        
    Returns:
        A Plotly figure object and a DataFrame with annual publication counts.
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
