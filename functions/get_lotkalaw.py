import numpy as np
import pandas as pd
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
        raise ValueError("get_lotka_law requires a non-empty DataFrame.")
    if not isinstance(data, pd.DataFrame):
        raise TypeError("get_lotka_law expects a pandas DataFrame or an object with .get().")
    return data.copy()


def get_lotka_law(df):
    """
    Calculates Lotka's Law for a given dataset and generates a line plot comparing observed and theoretical author productivity distributions.

    Args:
        df (pd.DataFrame): Dataset containing at least the "AU" (authors) column as lists of author names.

    Returns:
        fig: Plotly figure showing the observed and theoretical Lotka's Law distributions.
        author_prod (pd.DataFrame): Table summarizing the number of articles per author and their frequencies.
    """
    
    # Calculate Lotka's Law
    data = _resolve_dataframe(df)

    if "AU" not in data.columns:
        raise ValueError("Missing required column: AU.")

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
