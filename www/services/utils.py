import os
import io
import re
import ast
import time
import json
import time
import math
import prince
import random
import requests
import tempfile
import requests
import functools 
import numpy as np
import pandas as pd
import igraph as ig
import faicons as fa
import networkx as nx
import geopandas as gpd
import plotly.express as px
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.figure_factory as ff
import matplotlib.colors as mcolors
import scipy.cluster.hierarchy as sch

from prince import CA
from PIL import Image
from prince import MCA
from numpy import triu
from io import StringIO
from scipy import stats
from pathlib import Path
from matplotlib import cm
from shiny.express import ui
from functools import partial
from datetime import datetime
from shiny.types import FileInfo
from pyvis.network import Network
from sklearn.cluster import KMeans
from plotly.colors import n_colors
from shiny import reactive, render
from scipy.spatial import ConvexHull
from nltk.stem import SnowballStemmer
from itables import JavascriptFunction
from plotly.subplots import make_subplots
from itables.shiny import DT, init_itables
from sklearn.manifold import MDS as SK_MDS
from collections import Counter, defaultdict
from scipy.cluster.hierarchy import fcluster
from openpyxl import load_workbook, Workbook
from openpyxl.utils import get_column_letter
from bibtexparser.bparser import BibTexParser
from sklearn.preprocessing import MinMaxScaler
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import StandardScaler
from scipy.sparse import lil_matrix, csr_matrix
from nltk.corpus import stopwords as nltk_stopwords
from openpyxl.drawing.image import Image as XLImage
from scipy.spatial.distance import pdist, squareform
from sklearn.metrics.pairwise import cosine_similarity
from matplotlib.colors import to_hex, to_rgba, Normalize
from typing import Dict, List, Optional, Sequence, Union
from openpyxl.worksheet.table import Table, TableStyleInfo
from sklearn.feature_extraction.text import CountVectorizer
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from networkx.algorithms.community import greedy_modularity_communities


columns = ['AB', 'AF', 'AU', 'AU1_UN', 'AU_UN', 'BP', 'C1', 'CR', 'DB', 'DE', 
           'DI', 'DT', 'EM', 'EP', 'FU', 'FX', 'ID', 'IS', 'JI', 'LA', 'OA', 
           'OI', 'PMID', 'PU', 'PY', 'RP', 'SC', 'SN', 'SO', 'SR', 'TC', 'TI', 
           'UT', 'VL']


ICONS = {
    "mail": fa.icon_svg("envelope", "solid"),
    "mail_colored": fa.icon_svg("envelope", "solid", fill="#5567BB"),
    "mail_open": fa.icon_svg("envelope-open", "solid"),
    "api": fa.icon_svg("plug", "solid"),
    "api_colored": fa.icon_svg("plug", "solid", fill="#5567BB"),
    "merge": fa.icon_svg("code-merge", "solid"),
    "merge_colored": fa.icon_svg("code-merge", "solid", fill="#5567BB"),
    "question": fa.icon_svg("question", "solid"),
    "question_colored": fa.icon_svg("question", "solid", fill="#5567BB"),
    "donate": fa.icon_svg("circle-dollar-to-slot", "solid"),
    "donate_colored": fa.icon_svg("circle-dollar-to-slot", "solid", fill="#5567BB"),
    "credits": fa.icon_svg("coins", "solid"),
    "credits_colored": fa.icon_svg("coins", "solid", fill="#5567BB"),
    "play": fa.icon_svg("play", "solid"),
    "play_colored": fa.icon_svg("play", "solid", fill="#5567BB"),
    "database": fa.icon_svg("database", "solid"),
    "database_colored": fa.icon_svg("database", "solid", fill="#5567BB"),
    "info": fa.icon_svg("info", "solid"),
    "info_colored": fa.icon_svg("info", "solid", fill="#5567BB"),
    "download": fa.icon_svg("download", "solid"),
    "download_colored": fa.icon_svg("download", "solid", fill="#5567BB"),
    "book": fa.icon_svg("book", "solid"),
    "book_colored": fa.icon_svg("book", "solid", fill="#5567BB"),
    "timespan": fa.icon_svg("calendar", "solid"),
    "timespan_colored": fa.icon_svg("calendar", "solid", fill="#5567BB"),
    "sources": fa.icon_svg("book-open", "solid"),
    "sources_colored": fa.icon_svg("book-open", "solid", fill="#5567BB"),
    "documents": fa.icon_svg("file", "solid"),
    "documents_colored": fa.icon_svg("file", "solid", fill="#5567BB"),
    "annual_growth_rate": fa.icon_svg("chart-line", "solid"),
    "annual_growth_rate_colored": fa.icon_svg("chart-line", "solid", fill="#5567BB"),
    "authors": fa.icon_svg("user", "solid"),
    "authors_colored": fa.icon_svg("user", "solid", fill="#5567BB"),
    "authors_single_authored_docs": fa.icon_svg("pen-fancy", "solid"),
    "authors_single_authored_docs_colored": fa.icon_svg("pen-fancy", "solid", fill="#5567BB"),
    "international_co_authorship": fa.icon_svg("globe", "solid"),
    "international_co_authorship_colored": fa.icon_svg("globe", "solid", fill="#5567BB"),
    "co_authors_per_doc": fa.icon_svg("users", "solid"),
    "co_authors_per_doc_colored": fa.icon_svg("users", "solid", fill="#5567BB"),
    "authors_keywords_de": fa.icon_svg("key", "solid"),
    "authors_keywords_de_colored": fa.icon_svg("key", "solid", fill="#5567BB"),
    "references": fa.icon_svg("book", "solid"),
    "references_colored": fa.icon_svg("book", "solid", fill="#5567BB"),
    "document_average_age": fa.icon_svg("hourglass-half", "solid"),
    "document_average_age_colored": fa.icon_svg("hourglass-half", "solid", fill="#5567BB"),
    "average_citations_per_doc": fa.icon_svg("quote-right", "solid"),
    "average_citations_per_doc_colored": fa.icon_svg("quote-right", "solid", fill="#5567BB"),
    "home": fa.icon_svg("house", "solid"),
    "home_colored": fa.icon_svg("house", "solid", fill="#5567BB"),
    "data": fa.icon_svg("file-export", "solid"),
    "data_colored": fa.icon_svg("file-export", "solid", fill="#5567BB"),
    "filters": fa.icon_svg("filter", "solid"),
    "filters_colored": fa.icon_svg("filter", "solid", fill="#5567BB"),
    "overview": fa.icon_svg("table-cells", "solid"),
    "overview_colored": fa.icon_svg("table-cells", "solid", fill="#5567BB"),
    "clustering": fa.icon_svg("share-nodes", "solid"),
    "clustering_colored": fa.icon_svg("share-nodes", "solid", fill="#5567BB"),
    "conceptual_structure": fa.icon_svg("sitemap", "solid"),
    "conceptual_structure_colored": fa.icon_svg("sitemap", "solid", fill="#5567BB"),
    "intellectual_structure": fa.icon_svg("gem", "solid"),
    "intellectual_structure_colored": fa.icon_svg("gem", "solid", fill="#5567BB"),
    "social_structure": fa.icon_svg("users", "solid"),
    "social_structure_colored": fa.icon_svg("users", "solid", fill="#5567BB"),
    "report": fa.icon_svg("file-lines", "solid"),
    "report_colored": fa.icon_svg("file-lines", "solid", fill="#5567BB"),
    "settings": fa.icon_svg("gear", "solid"),
    "settings_colored": fa.icon_svg("gear", "solid", fill="#5567BB"),
    "plus": fa.icon_svg("plus", "solid"),
    "minus": fa.icon_svg("minus", "solid"),
    "delete": fa.icon_svg("trash", "solid"),
    "github": fa.icon_svg("github", "brands"),
    "save": fa.icon_svg("floppy-disk", "solid"),
}


def empty_plot(message="Click RUN to generate analysis"):
    """
    Create an empty plotly figure with a message for placeholder display.
    
    Args:
        message (str): Message to display in the empty plot
    
    Returns:
        plotly.graph_objects.Figure: Empty figure with message
    """
    fig = go.Figure()
    
    # Add a text annotation in the center
    fig.add_annotation(
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        text=message,
        showarrow=False,
        font=dict(size=20, color="gray", family="Arial"),
        xanchor="center",
        yanchor="middle",
        align="center"
    )
    
    # Set layout with minimal margins and proper sizing
    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            visible=False
        ),
        yaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            visible=False
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        height=400,
        autosize=True
    )
    
    return fig