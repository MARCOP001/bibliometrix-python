from www.services import *


def get_co_occurence_network(df, field_cn, ngram, network_layout, clustering_algorithm_cn, normalization_cn, color_by_year, num_of_nodes, 
                            repulsion_force, remove_isolated, min_edges, node_opacity, num_of_labels, node_shape, label_size_ls,
                            edge_size, node_shadow, edit_nodes, label_cex, file_upload_terms, file_upload_synonyms):
    
    M = df

    # Load stopwords and synonyms (matching R's behavior)
    remove_terms = None
    if file_upload_terms:
        with open(file_upload_terms[0]['datapath'], 'r', encoding='utf-8') as file:
            remove_terms = [line.strip() for line in file]

    synonyms = None
    if file_upload_synonyms:
        with open(file_upload_synonyms[0]['datapath'], 'r', encoding='utf-8') as file:
            syn_dict = {}
            for line in file:
                terms = [term.strip() for term in line.split(';')]  # Changed to ; separator as in R
                if terms:
                    key = terms[0]
                    syn_dict[key] = terms[1:]
            synonyms = syn_dict if syn_dict else None

    # Set ngrams based on word_type
    ngrams = int(ngram) if field_cn in ['TI', 'AB'] else 1

    # Adjust number of labels if exceeds nodes
    if num_of_labels > num_of_nodes:
        num_of_labels = num_of_nodes

    # Create network based on field type (matching R's switch statement)
    network_data = None
    title = ""
    
    if field_cn == 'ID':
        network_data = biblionetwork(M, "co-occurrences", "keywords", num_of_nodes, 
                                    sep=";", remove_terms=remove_terms, synonyms=synonyms)
        title = "Keywords Plus Network"
    elif field_cn == 'DE':
        network_data = biblionetwork(M, "co-occurrences", "author_keywords", num_of_nodes,
                                    sep=";", remove_terms=remove_terms, synonyms=synonyms)
        title = "Authors' Keywords network"
    elif field_cn == 'TI':
        M = term_extraction(M, "TI", ngrams=ngrams,
                          remove_terms=remove_terms, synonyms=synonyms)
        network_data = biblionetwork(M, "co-occurrences", "titles", num_of_nodes, sep=";")
        title = "Title Words network"
    elif field_cn == 'AB':
        M = term_extraction(M, "AB", ngrams=ngrams,
                          remove_terms=remove_terms, synonyms=synonyms)
        network_data = biblionetwork(M, "co-occurrences", "abstracts", num_of_nodes, sep=";")
        title = "Abstract Words network"
    elif field_cn == 'WC':
        wsc = cocMatrix(M, "WC", binary=False)
        network_data = np.matmul(wsc.T, wsc)
        title = "Subject Categories network"

    if network_data is None:
        return None, None, None, None
    
    # Normalize if specified
    if normalization_cn == "none":
        normalize = None
    else:
        normalize = normalization_cn

    cocnet = network_plot(
        NetMatrix=network_data,
        normalize=normalize,
        Title=title,
        type=network_layout,
        size_cex=True,
        size=5,
        remove_multiple=False,
        edgesize=edge_size,
        labelsize=label_size_ls,
        label_cex=label_cex,
        label_n=num_of_labels,
        edges_min=min_edges,
        label_color=False,
        curved=True,
        alpha=node_opacity,
        cluster=clustering_algorithm_cn,
        remove_isolates=remove_isolated,
        community_repulsion=repulsion_force/2,
        verbose=False
    )

    # Color nodes by year if selected
    if color_by_year:
        Y = field_by_year(M, field_cn)
        g = cocnet['graph']
        labels = [v['name'] for v in g.vs]
        Y_df = Y['df']
        
        # Find matching items in year data
        mask = Y_df['item'].str.lower().isin(labels)
        df = Y_df[mask].copy()
        
        # Create color gradient
        year_range = df['year_med'].max() - df['year_med'].min() + 1
        colors = plt.cm.Blues(np.linspace(0, 1, int(year_range * 10)))
        
        # Assign colors to vertices based on year
        vertex_colors = []
        for label in labels:
            year = df[df['item'].str.lower() == label.lower()]['year_med'].iloc[0]
            color_idx = int((max(df['year_med']) - year + 1) * 10 - 1)
            vertex_colors.append(colors[color_idx])
        
        # Update graph properties
        g.vs['color'] = vertex_colors
        g.vs['year_med'] = [df[df['item'].str.lower() == label.lower()]['year_med'].iloc[0] for label in labels]
        cocnet['graph'] = g

    ################################## NETWORK VISUALIZATION ##################################
    net = Network(height="98vh", width="100%", notebook=True, cdn_resources="in_line")
    net.toggle_physics(False)

    # Use colors from df['adjusted_color']
    unique_clusters = set(cocnet['cluster_obj'].membership)
    cluster_colors = {}
    cm_clusters = cocnet['cluster_res']

    # Get unique cluster IDs and their colors
    for cluster_id in unique_clusters:
        # Generate random RGB values
        r = np.random.randint(0, 255)
        g = np.random.randint(0, 255) 
        b = np.random.randint(0, 255)
        # Create rgba color with 0.3 opacity
        cluster_colors[cluster_id] = f"rgba({r},{g},{b},{node_opacity})"

    # Generate layout
    # Using default igraph layout
    layout = cocnet['graph']['layout']
    print("Layout:", layout)
    # Get coordinates from layout
    coords = np.array([[pos[0], pos[1]] for pos in layout])
    
    # Scale coordinates to fit 800px height
    # First normalize to [-1,1] range
    coords = coords / np.abs(coords).max()
    
    # Then scale to target dimensions
    # Width will be proportional to maintain aspect ratio
    coords[:, 0] *= 1000  # Scale x coordinates 
    coords[:, 1] *= 400   # Scale y coordinates to fit 800px (centered)

    # Prepare for avoid_net_overlaps
    node_labels = [v["name"] if "name" in v.attributes() else f"Node {v.index}" for v in cocnet['graph'].vs]
    node_sizes = []
    nodes = []
    
    # Add nodes with matching R visNetwork settings
    for idx, vertex in enumerate(cocnet['graph'].vs):
        cluster_id = cocnet['cluster_obj'].membership[vertex.index]
        node_color = cluster_colors[cluster_id]

        # Normalize node sizes
        min_deg, max_deg = min(cocnet['graph'].degree()), max(cocnet['graph'].degree())
        node_size = 10 if max_deg == min_deg else (15 * (vertex.degree() - min_deg) / (max_deg - min_deg) + 10)
        node_size = max(10, min(130, node_size))
        font_size = node_size * 2
        node_sizes.append(node_size)
        
        # Calculate font opacity using R-like formula
        min_font_size = 10   # Minimum node size 
        max_font_size = 130  # Maximum node size 
        font_opacity = np.sqrt((font_size - min_font_size) / (max_font_size - min_font_size))*node_opacity + 0.3
        font_opacity = max(0.1, min(1, font_opacity))  # Clamp between 0.1 and 1
        
        nodes.append({
            'id': vertex.index,
            'label': vertex["name"] if "name" in vertex.attributes() else f"Node {vertex.index}",
            'title': vertex["name"] if "name" in vertex.attributes() else f"Node {vertex.index}",
            'color': node_color,
            'size': node_size,
            'font': {
                'size': font_size, 
                'color': f'rgba(0,0,0,{font_opacity})', 
                'vadjust': -0.7*font_size if node_shape.lower() in ['dot', 'square'] else 0
            },
            'shadow': node_shadow,
            'shape': node_shape,
            'x': layout[idx][0] * 1000,
            'y': layout[idx][1] * 1000
        })

    # Remove overlapping labels
    noOverlap = True
    if noOverlap:
        threshold = 0.05
        ymax = np.ptp(coords[:, 1])  # equivalent to diff(range())
        xmax = np.ptp(coords[:, 0])
        threshold2 = threshold * np.mean([xmax, ymax])
        
        # Create data structure for overlap checking
        labels_to_remove = avoid_net_overlaps(coords, node_labels, node_sizes, threshold=threshold2)
    else:
        labels_to_remove = []
    #labels_to_remove = avoid_net_overlaps(coords, node_labels, node_sizes, threshold=0.05)
    
    # Add nodes to network
    unique_nodes = {node['id']: node for node in nodes}.values()
    for node in unique_nodes:
        if node['label'] in labels_to_remove:
            node['label'] = ''
        net.add_node(node['id'], **node)

    # Add edges with improved styling matching R implementation
    added_edges = set()
    edge_weights = [e.attributes().get('weight', 1) for e in cocnet['graph'].es]
    max_weight = max(edge_weights) if edge_weights else 1
    
    for edge in cocnet['graph'].es:
        source, target = edge.tuple
        cluster_source = cocnet['cluster_obj'].membership[source]
        cluster_target = cocnet['cluster_obj'].membership[target]
        
        # Set edge color with proper opacity
        if cluster_source == cluster_target:
            base_color = cluster_colors[cluster_source]
            # Convert rgba to hex with opacity
            rgba_values = [int(x) for x in base_color[5:-1].split(',')[:-1]]
            edge_color = f"rgba({rgba_values[0]},{rgba_values[1]},{rgba_values[2]},0.56)"
        else:
            # Use darker gray for inter-cluster edges (equivalent to #69696960 in R)
            edge_color = "rgba(105,105,105,0.38)"
        
        # Calculate edge width similar to R implementation
        edge_weight = edge.attributes().get('weight', 1)
        normalized_weight = (edge_weight ** 2 / (max_weight ** 2)) * (10 + 2.5)  # 2.5 is base edge size
        
        edge_tuple = (source, target) if source < target else (target, source)
        
        # Add edge if not already added
        if edge_tuple not in added_edges:
            net.add_edge(
                source, 
                target, 
                color=edge_color,
                width=normalized_weight,
                smooth={'type': 'horizontal'},
                dashes=False  # Set to True if you have line type information
            )
            added_edges.add(edge_tuple)

    # Configure network options to match R visNetwork
    net.set_options(f"""
        var options = {{
            "nodes": {{
                "shadow": {"true" if node_shadow else "false"}
            }},
            "edges": {{
                "smooth": {{"type": "horizontal"}}
            }},
            "interaction": {{
                "dragNodes": true,
                "hideEdgesOnDrag": true,
                "navigationButtons": false,
                "zoomSpeed": 0.4
            }},
            "physics": {{
                "enabled": false
            }},
            "manipulation": {{
                "enabled": {"true" if edit_nodes else "false"}
            }}
        }}
    """)

    # Save network to HTML
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    html_path = tmp.name
    with open(html_path, 'w', encoding="utf-8") as f:
        html = net.generate_html()
        new_css = "     .card {\n                 border: none;\n             }"
        updated_html = html.replace("</style>", new_css + "\n        </style>")
        updated_html = updated_html.replace("1px solid lightgray", "none")
        
        f.write(updated_html)

    ################################################################################################

    ##################################### Density Plot #####################################
    # Crea il dataframe originale e correggi le coordinate y
    nodes_df_orig = pd.DataFrame(nodes)
    nodes_df_orig['y'] = nodes_df_orig['y'] * -1

    # Calcola la dimensione del font seguendo la formula: (((font.size - min(font.size)) / diff(range(font.size)))*20)+10
    font_sizes = nodes_df_orig['font'].apply(lambda x: x.get('size', 75))
    min_font = font_sizes.min()
    max_font = font_sizes.max()
    nodes_df_orig['font_size'] = ((font_sizes - min_font) / (max_font - min_font) * 20) + 10

    # Crea il dataframe replicato per il density plot:
    nodes_df = nodes_df_orig.copy()
    nodes_df['log'] = np.ceil(np.log(nodes_df['size']))
    nodes_df = nodes_df.loc[nodes_df.index.repeat(nodes_df['log'].astype(int))]

    # Definisci la colorscale "Reds" con transizioni armoniose
    reds_colors = [
        [0.0, 'rgb(255,255,255)'],
        [0.05, 'rgb(238,238,238)'],
        [0.125, 'rgb(254,224,210)'],
        [0.25, 'rgb(252,187,161)'],
        [0.375, 'rgb(252,146,114)'],
        [0.5, 'rgb(251,106,74)'],
        [0.625, 'rgb(239,59,44)'],
        [0.75, 'rgb(203,24,29)'],
        [0.875, 'rgb(165,15,21)'],
        [1.0, 'rgb(103,0,13)']
    ]

    # Crea il grafico 2D histogram
    fig = go.Figure()
    fig.add_trace(go.Histogram2d(
        x=nodes_df['x'],
        y=nodes_df['y'],
        histnorm='density',
        colorscale=reds_colors,
        showscale=False,
        zsmooth='best'  # Migliora la qualità della densità
    ))

    # Aggiungi le annotazioni (usando i dati originali)
    for _, row in nodes_df.iterrows():
        # Extract font color from node properties and adjust opacity
        fig.add_annotation(
            xref='x1',
            yref='y',
            x=row['x'],
            y=row['y'],
            text=row['label'],
            showarrow=False,
            font=dict(
                family='Arial',
                size=row['font_size'],
                color='black'
            )
        )

    # Update layout to match R implementation
    fig.update_layout(
        xaxis=dict(
            title="",
            showgrid=False,
            zeroline=False,
            showline=False,
            showticklabels=False,
            domain=[0, 1],
            gridcolor='#FFFFFF',
            tickvals=[]
        ),
        yaxis=dict(
            title="",
            showgrid=False,
            zeroline=False,
            showline=False,
            showticklabels=False, 
            domain=[0, 1],
            gridcolor='#FFFFFF',
            tickvals=[]
        ),
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        showlegend=False,
        hovermode=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
    )

    # Remove hover info
    fig.update_traces(hoverinfo='none')
    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}

    ####################### Table #########################
    # Create cluster results dataframe with renamed columns
    cluster_data = pd.DataFrame({
        'Node': [v['name'] if 'name' in v.attributes() else f'Node {v.index}' for v in cocnet['graph'].vs],
        'Cluster': cocnet['cluster_obj'].membership,
        'Betweenness': cocnet['graph'].betweenness(),
        'Closeness': cocnet['graph'].closeness(),
        'PageRank': cocnet['graph'].pagerank()
    })

    # Round numeric columns to 3 decimal places
    numeric_cols = ['Betweenness', 'Closeness', 'PageRank']
    cluster_data[numeric_cols] = cluster_data[numeric_cols].round(3)
    
    cocnet['cluster_res'] = cluster_data

    ######################## degree plot ########################
    # Create degree plot with normalized degrees between 0 and 1
    # Calculate node degrees and sort them
    node_degrees = pd.DataFrame({
        'node': [v['name'] if 'name' in v.attributes() else f'Node {v.index}' for v in cocnet['graph'].vs],
        'degree': cocnet['graph'].degree()
    })
    
    # Sort by degree in descending order (like in R)
    node_degrees = node_degrees.sort_values('degree', ascending=False)
    
    # Add row numbers after sorting (equivalent to R's row_number())
    node_degrees['x'] = range(1, len(node_degrees) + 1)
    
    # Normalize degrees between 0 and 1 
    max_degree = node_degrees['degree'].max()
    node_degrees['degree'] = node_degrees['degree'] / max_degree

    degree_plot = go.Figure()
    
    # Add scatter plot with line
    degree_plot.add_trace(go.Scatter(
        x=node_degrees['x'],
        y=node_degrees['degree'],
        mode='lines+markers',
        line=dict(color='#5567BB', width=1),
        marker=dict(size=6),
        hovertemplate='%{text}<extra></extra>',
        text=[f"{node} - Degree {degree:.3f}" for node, degree in zip(node_degrees['node'], node_degrees['degree'])]
    ))

    # Update layout
    degree_plot.update_layout(
        xaxis_title='Node',
        yaxis_title='Cumulative Degree',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(color='#444444'),
        title_font_size=24,
        xaxis=dict(
            showgrid=True,
            gridcolor='#EFEFEF',
            title_font=dict(size=14, color='#555555'),
            showline=True,
            linewidth=0.5,
            linecolor='black'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#EFEFEF',
            title_font=dict(size=14, color='#555555'),
            title_standoff=25,
            showline=True,
            linewidth=0.5,
            linecolor='black'
        ),
        height=600,
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_family="Segoe UI, Arial",
            bordercolor="#5567BB"
        ),
    )
    degree_plot = go.FigureWidget(degree_plot)
    degree_plot._config = degree_plot._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                                 'displaylogo': False}

    return html_path.split(os.sep)[-1], fig, cocnet['cluster_res'], degree_plot


def field_by_year(df, field_cn, timespan=None, min_freq=2, n_items=5, remove_terms=None, synonyms=None):
    """
    Analyzes field frequency by year, matching R's fieldByYear function.
    
    Parameters:
    -----------
    M : DataFrame
        The bibliographic data
    field_cn : str
        The field to analyze ('ID', 'DE', 'TI', 'AB', 'WC')
    """
    # Get the field data
    M = df.get()
    
    # Create co-occurrence matrix
    A = cocMatrix(df, field_cn, binary=False, remove_terms=remove_terms, synonyms=synonyms)
    
    # Calculate frequencies
    n = np.sum(A, axis=0)
    
    # Calculate year quantiles for each term
    trend_med = []
    years = M['PY'].values
    print("Years:", years)
    
    for col_idx in range(A.shape[1]):
        # Get years where term appears (with repetition based on frequency)
        term_years = np.repeat(years, A.iloc[:, col_idx].astype(int))
        if len(term_years) > 0:
            q1, med, q3 = np.percentile(term_years, [25, 50, 75])
            trend_med.append({
                'item': A.columns[col_idx],
                'freq': n[col_idx],
                'year_q1': q1,
                'year_med': med,
                'year_q3': q3
            })
    
    # Convert to DataFrame
    trend_med = pd.DataFrame(trend_med)
    
    # Set timespan if not provided
    if timespan is None:
        timespan = [trend_med['year_med'].min(), trend_med['year_med'].max()]
    
    # Filter and sort data
    df = (trend_med
          .assign(item=lambda x: x['item'].str.lower())
          .sort_values(['year_med', 'freq', 'item'], ascending=[False, False, True])
          .groupby('year_med')
          .head(n_items)
          .query('freq >= @min_freq')
          .query('@timespan[0] <= year_med <= @timespan[1]')
          .copy())
    
    # Sort items by frequency
    df['item'] = pd.Categorical(df['item'], 
                               categories=df.sort_values('freq', ascending=True)['item'].unique(),
                               ordered=True)
    
    results = {
        'df': trend_med,
        'df_graph': df
    }
    
    return results
