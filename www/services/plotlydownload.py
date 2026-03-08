from .utils import *


def plotly_download(plotly_figure, title="", width=14, height=7, dpi=300):
    """
    Download a Plotly figure as an image.

    Args:
        plotly_figure: A Plotly figure object to be downloaded.

    Returns:
        A BytesIO object containing the image data.
    """
    plot_download = go.Figure(plotly_figure)

    plot_download.add_layout_image(
        dict(
            source="https://raw.githubusercontent.com/massimoaria/bibliometrix/master/logo.png", 
            xref="paper", yref="paper",
            x=1, y=0.05,  # in basso a destra
            sizex=0.1, sizey=0.1,
            xanchor="right", yanchor="bottom"
        )
    )

    plot_download.update_layout(
        title_text=title,
        title_font_size=0.18 * dpi,
        title_yanchor='top',
        width=width * dpi,
        height=height * dpi,
        margin=dict(l=50, r=50, t=80, b=50)
    )
    
    plot_download.update_xaxes(
        title_font_size=0.12 * dpi,   # aumenta la dimensione del titolo asse x
        tickfont_size=0.08 * dpi      # aumenta la dimensione dei valori asse x
    )
    plot_download.update_yaxes(
        title_font_size=0.12 * dpi,   # aumenta la dimensione del titolo asse y
        tickfont_size=0.08 * dpi      # aumenta la dimensione dei valori asse y
    )

    with io.BytesIO() as buffer:
        buffer = plot_download.to_image(format="png", scale=1)
        return buffer