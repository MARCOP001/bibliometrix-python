from www.services import *


def get_bradford_law(df):
    """
    Generate a plot and table based on Bradford's Law.
    
    Args:
        df: A DataFrame object containing the data.
        
    Returns:
        A Plotly figure object and a DataFrame of the Bradford's Law zones.
    """
    # Sort data by frequency of occurrence (equivalent to R's sort(table(M$SO), decreasing = TRUE))
    data = df.get()
    source_counts = data["SO"].value_counts()
    
    # Total number of sources
    n = source_counts.sum()
    # Cumulative sum of the frequencies (equivalent to cumsum in R)
    cumSO = source_counts.cumsum()
    
    # Define the cut points for Bradford's Law (zones)
    cutpoints = [1, n * 0.33, n * 0.67, float('inf')]
    groups = pd.cut(cumSO, bins=cutpoints, labels=["Zone 1", "Zone 2", "Zone 3"])
    
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
        x0=0,
        x1=np.log(df_bradford["Rank"][a]),
        y0=0,
        y1=df_bradford["Freq"].max(),
        fillcolor="#B3D1F2",
        opacity=0.18,
        line_width=0,
        layer="below"
    )

    # Add the "Core Sources" annotation with smaller font
    fig.add_annotation(
        x=np.log(df_bradford["Rank"][a]) / 2,
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
