from www.services import *


def get_sources_local_impact(df, num_of_sources_local_impact, source_local_impact):
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
    df['h_index'] = df.groupby('SO')['TC'].transform(h_calc)
    df['g_index'] = df.groupby('SO')['TC'].transform(g_calc)
    df['PY_start'] = df.groupby('SO')['PY'].transform('min')
    df['m_index'] = df['h_index'] / (today - df['PY_start'] + 1)
    df['NP'] = df.groupby('SO')['SO'].transform('size')
    df['TC_sum'] = df.groupby('SO')['TC'].transform(lambda x: x.sum())

    # Select the top sources
    top_sources = df.groupby('SO').first().reset_index()
    #top_sources = top_sources.nlargest(num_of_sources_local_impact, impact_column)

    # Prepare the final table
    source_counts = top_sources[['SO', 'h_index', 'g_index', 'm_index', 'TC_sum', 'NP', 'PY_start']].copy()
    source_counts.rename(columns={
        'SO': 'Element',
        'TC_sum': 'TC'
    }, inplace=True)

    #source_counts["Element"] = source_counts["Element"].str[:50]
    source_counts = source_counts.sort_values(by='h_index', ascending=False)

    # Select top sources based on the chosen impact measure
    if source_local_impact == "h_index":
        source_counts_visualization = source_counts.sort_values(by='h_index', ascending=False)
        impact_column = 'h_index'
    elif source_local_impact == "g_index":
        source_counts_visualization = source_counts.sort_values(by='g_index', ascending=False)
        impact_column = 'g_index'
    elif source_local_impact == "m_index":
        source_counts_visualization = source_counts.sort_values(by='m_index', ascending=False)
        impact_column = 'm_index'
    else:
        source_counts_visualization = source_counts.sort_values(by='TC', ascending=False)
        impact_column = 'TC'

    source_counts_visualization = source_counts_visualization.head(num_of_sources_local_impact)

    # Truncate long source names and add line breaks every 50 characters
    def wrap_label(label, width=50):
        return '<br>'.join([label[i:i+width] for i in range(0, len(label), width)])
    source_counts_visualization["Element_wrapped"] = source_counts_visualization["Element"].apply(wrap_label)

    # Create the plot as a horizontal bar chart to avoid overlap
    fig = px.bar(
        source_counts_visualization,
        x=impact_column,
        y="Element_wrapped",
        orientation='h',
        text=impact_column,
        labels={impact_column: f"{source_local_impact.replace('_', ' ').title()}", "Element_wrapped": "Sources"},
        color=impact_column,
        color_continuous_scale=[(0, "#B3D1F2"), (1, "#5567BB")],
    )

    # Customize the layout and tooltips (hover)
    fig.update_traces(
        texttemplate='%{text}',
        textposition='inside',
        insidetextanchor='middle',
        marker=dict(
            opacity=0.95,
            line=dict(width=1, color='white')
        ),
        hovertemplate=(
            "<b>Source:</b> %{y}<br>"
            f"<b>{impact_column.replace('_', ' ').title()}:</b> "+"%{x}<br>"+
            "<b>N. of Documents:</b> %{customdata[0]}<br>"+
            "<b>Start Year:</b> %{customdata[1]}<extra></extra>"
        ),
        customdata=source_counts_visualization[["NP", "PY_start"]].values,
    )

    fig.update_layout(
        yaxis=dict(
            autorange="reversed",
            showgrid=False,
            tickfont=dict(size=13),
            title="Sources",
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor="#F0F0F0",
            zeroline=False,
            title=f"{source_local_impact.replace('_', ' ').title()}",
            tickfont=dict(size=13),
        ),
        plot_bgcolor='white',
        font=dict(color="#222222", size=14, family="Segoe UI, Arial"),
        margin=dict(l=220, r=40, t=60, b=40),
        height=50 + 90 * len(source_counts_visualization),
        coloraxis_showscale=False,
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

    return fig, source_counts
