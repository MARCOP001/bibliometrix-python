from www.services import *


def get_authors_local_impact(df, num_of_authors_local_impact, author_local_impact):
    """
    Generate a plot and table of the most impactful sources based on the chosen impact measure.

    Args:
        df: A DataFrame object containing the data.
        num_of_sources_local_impact: The number of top impactful sources to display.
        source_local_impact: The impact measure to use for ranking the sources.

    Returns:
        A Plotly figure object and a DataFrame of the most impactful sources.
    """
    df = df.get()
    today = pd.Timestamp.now().year

    # Ensure 'TC' and 'PY' are numeric
    df['TC'] = pd.to_numeric(df['TC'], errors='coerce')
    df['PY'] = pd.to_numeric(df['PY'], errors='coerce')
    df = df.dropna(subset=['TC', 'PY'])

    # Define h-index and g-index calculation functions
    def h_calc(x):
        if len(x) == 0:  # Check for empty array
            return 0
        sorted_x = np.sort(x)[::-1]
        valid_indices = np.where(np.arange(1, len(x) + 1) <= sorted_x)[0]
        if len(valid_indices) == 0:  # Check for empty array after filtering
            return 0
        h = np.max(valid_indices) + 1
        return h

    def g_calc(x):
        if len(x) == 0:  # Check for empty array
            return 0
        sorted_x = np.sort(x)[::-1]
        cummean = np.cumsum(sorted_x) / np.arange(1, len(sorted_x) + 1)
        valid_indices = np.where(np.arange(1, len(sorted_x) + 1) <= cummean)[0]
        if len(valid_indices) == 0:  # No valid values
            return 0
        g = np.max(valid_indices) + 1
        return g

    # Calculate indices
    df = df.explode('AU')
    df['h_index'] = df.groupby('AU')['TC'].transform(h_calc)
    df['g_index'] = df.groupby('AU')['TC'].transform(g_calc)
    df['PY_start'] = df.groupby('AU')['PY'].transform('min')
    df['m_index'] = df['h_index'] / (today - df['PY_start'] + 1)
    df['NP'] = df.groupby('AU')['AU'].transform('size')
    df['TC_sum'] = df.groupby('AU')['TC'].transform(lambda x: x.sum())

    # Select the top sources
    top_sources = df.groupby('AU').first().reset_index()
    #top_sources = top_sources.nlargest(num_of_sources_local_impact, impact_column)

    # Prepare the final table
    source_counts = top_sources[['AU', 'h_index', 'g_index', 'm_index', 'TC_sum', 'NP', 'PY_start']].copy()
    source_counts.rename(columns={
        'AU': 'Element',
        'TC_sum': 'TC'
    }, inplace=True)

    source_counts["Element"] = source_counts["Element"].str[:50]
    source_counts = source_counts.sort_values(by='h_index', ascending=False)

    # Select top sources based on the chosen impact measure
    if author_local_impact == "h_index":
        source_counts_visualization = source_counts.sort_values(by='h_index', ascending=False)
        impact_column = 'h_index'
    elif author_local_impact == "g_index":
        source_counts_visualization = source_counts.sort_values(by='g_index', ascending=False)
        impact_column = 'g_index'
    elif author_local_impact == "m_index":
        source_counts_visualization = source_counts.sort_values(by='m_index', ascending=False)
        impact_column = 'm_index'
    else:
        source_counts_visualization = source_counts.sort_values(by='TC', ascending=False)
        impact_column = 'TC'

    source_counts_visualization = source_counts_visualization.head(num_of_authors_local_impact)

    # Create the plot
    fig = px.scatter(
        source_counts_visualization,
        x=impact_column,
        y="Element",
        text=source_counts_visualization[impact_column].round(2),  # Round values to the second decimal place
        orientation='h',
        labels={"Element": "Sources", impact_column: f"{author_local_impact}"},
        color=impact_column,  # Color scale based on impact
        color_continuous_scale=[(0, "lightblue"), (1, "darkblue")],  # Color scale from light to dark
    )

    # Customize the layout
    fig.update_traces(
        marker=dict(opacity=1, size=np.log1p(source_counts_visualization[impact_column]) * 10 + 20),  # Adjust marker size using log scale and add a minimum size
        textposition="middle center",
        textfont=dict(color="white", size=12),  # Center text in markers
    )

    # Add horizontal lines for each source
    for i, row in source_counts_visualization.iterrows():
        fig.add_shape(
            type="line",
            x0=0,
            x1=row[impact_column],
            y0=row["Element"],
            y1=row["Element"],
            line=dict(color="lightgrey", width=3),  # Light grey lines under markers
            layer="below",  # Lines below markers
        )

    # Final layout configuration
    fig.update_layout(
        yaxis=dict(autorange="reversed", showgrid=True, gridcolor="lightgrey", zeroline=False),
        xaxis=dict(showgrid=True, gridcolor="lightgrey", zeroline=False, title=f"Impact Measure: {author_local_impact}"),
        plot_bgcolor='white',
        title_font_size=24,
        font=dict(color="#444444"),
        margin=dict(l=150, r=40, t=40, b=40),
        height=800,
        coloraxis_showscale=False,
        showlegend=False
    )
    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}

    return fig, source_counts
