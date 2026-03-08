from .utils import *
from .networkplot import *


def delete_isolates2(graph, mode="ALL"):
    # Se è igraph
    if hasattr(graph, "vs"):
        isolates = [v.index for v in graph.vs if graph.degree(v, mode=mode) == 0]
        graph.delete_vertices(isolates)
        return graph
    # Se è networkx
    elif isinstance(graph, nx.Graph):
        isolates = list(nx.isolates(graph))
        graph.remove_nodes_from(isolates)
        return graph
    else:
        raise TypeError("Unsupported graph type in delete_isolates()")


def histPlot(histResults, n=20, size=5, labelsize=5, remove_isolates=True, title_as_label=False, label="short", verbose=True):

    # Color list (replace with your colorlist function if available)
    colorlist = [
        "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999",
        "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494", "#b3b3b3",
        "#a6cee3", "#1f78b4", "#b2df8a", "#33a02c", "#fb9a99", "#e31a1c", "#fdbf6f", "#ff7f00", "#cab2d6", "#6a3d9a",
        "#ffff99", "#b15928"
    ]

    LCS = histResults['NetMatrix'].sum(axis=0)

    # Selezioniamo il valore di soglia s
    sorted_LCS = LCS.sort_values(ascending=False)
    s = sorted_LCS.iloc[min(n, len(sorted_LCS))]

    # Troviamo gli indici (etichette) che soddisfano la condizione LCS >= s
    selected_columns = sorted_LCS[sorted_LCS >= s].index.tolist()

    # Filtriamo NET per mantenere solo le righe e le colonne corrispondenti agli indici selezionati
    NET = histResults['NetMatrix'].copy()
    NET = NET.loc[selected_columns, selected_columns]

    # Aggiorniamo LCS per includere solo i valori corrispondenti agli indici selezionati
    LCS = LCS[selected_columns]

    num_ones = (NET.values == 1).sum()

    # Create directed graph
    G = nx.from_pandas_adjacency(NET, create_using=nx.DiGraph)

    # Node names for matching
    node_names = []
    for node in G.nodes:
        parts = node.split(',')
        if len(parts) >= 2:
            node_new = f"{parts[0]},{parts[1]}"
        else:
            node_new = node
        node_names.append(node_new)

    # Add node attributes
    histData = histResults['histData'].set_index('Paper')
    for i, node in enumerate(G.nodes):
        node_new = node_names[i]
        G.nodes[node]['title'] = histData.loc[node_new, 'Title'] if node_new in histData.index else ""
        G.nodes[node]['keywords'] = histData.loc[node_new, 'Author_Keywords'] if node_new in histData.index else ""
        G.nodes[node]['keywordsplus'] = histData.loc[node_new, 'KeywordsPlus'] if node_new in histData.index else ""

    # Node labels
    if label == "title":
        def split_title(t):
            words = t.title().split()
            nwords = len(words)
            n = nwords // 2 if nwords > 1 else 1
            return " ".join(words[:n]) + ("\n" if n < nwords else "") + " ".join(words[n:])
        for node in G.nodes:
            G.nodes[node]['id'] = split_title(G.nodes[node]['title'])
    elif label == "keywords":
        def split_kw(kw):
            if pd.isna(kw) or not kw: return "Not Available"
            kws = [k.strip().title() for k in kw.split(';')]
            n = len(kws) // 2 if len(kws) > 1 else 1
            return "; ".join(kws[:n]) + ("\n" if n < len(kws) else "") + "; ".join(kws[n:])
        for node in G.nodes:
            G.nodes[node]['id'] = split_kw(G.nodes[node]['keywords'])
    elif label == "keywordsplus":
        def split_kwp(kw):
            if pd.isna(kw) or not kw: return "Not Available"
            kws = [k.strip().title() for k in kw.split(';')]
            n = len(kws) // 2 if len(kws) > 1 else 1
            return "; ".join(kws[:n]) + ("\n" if n < len(kws) else "") + "; ".join(kws[n:])
        for node in G.nodes:
            G.nodes[node]['id'] = split_kwp(G.nodes[node]['keywordsplus'])
    else:
        for i, node in enumerate(G.nodes):
            G.nodes[node]['id'] = node_names[i].lower()

    # Node size
    for node in G.nodes:
        G.nodes[node]['size'] = size

    # Extract year from node name (assuming year is at end)
    for i, node in enumerate(G.nodes):
        match = re.search(r'(\d{4})$', node_names[i])
        G.nodes[node]['years'] = int(match.group(1)) if match else np.nan

    # Remove loops and isolates
    G.remove_edges_from(nx.selfloop_edges(G))
    if remove_isolates:
        G = delete_isolates2(G)

    # Decompose into connected components and layout
    components = [G.subgraph(c).copy() for c in nx.weakly_connected_components(G)]
    layout_m = {}
    y_offset = 0
    cluster = 0
    for comp in components:
        pos = nx.spring_layout(comp, seed=42)
        min_y = min([p[1] for p in pos.values()])
        for node, (x, y) in pos.items():
            year = G.nodes[node]['years']
            layout_m[node] = {
                'x': year,
                'y': y + y_offset,
                'cluster': cluster
            }
        max_y = max([p[1] for p in pos.values()])
        y_offset += max_y - min_y + 1
        cluster += 1

    # Community detection (infomap/greedy modularity)
    try:
        communities = list(greedy_modularity_communities(G.to_undirected()))
        node_color = {}
        for i, comm in enumerate(communities):
            color = colorlist[i % len(colorlist)]
            for node in comm:
                node_color[node] = color
    except Exception:
        node_color = {n: "#1f77b4" for n in G.nodes}

    # Prepare DataFrame for plotting
    df = pd.DataFrame({
        'x': [layout_m[n]['x'] for n in G.nodes],
        'y': [layout_m[n]['y'] for n in G.nodes],
        'id': [G.nodes[n]['id'] for n in G.nodes],
        'size': [G.nodes[n]['size'] for n in G.nodes],
        'color': [node_color[n] for n in G.nodes],
        'title': [G.nodes[n]['title'] for n in G.nodes],
        'years': [G.nodes[n]['years'] for n in G.nodes],
        'name': list(G.nodes)
    }, index=G.nodes)


    # Edges DataFrame for plotting
    edges = []
    for u, v in G.edges:
        edges.append({
            'from': u,
            'to': v,
            'from_x': layout_m[u]['x'],
            'from_y': layout_m[u]['y'],
            'to_x': layout_m[v]['x'],
            'to_y': layout_m[v]['y'],
            'color': "slategray"
        })
    df_edges = pd.DataFrame(edges)

    # Normalize x/y for plotting
    if not df.empty:
        df['x_norm'] = (df['x'] - df['x'].min()) / (df['x'].max() - df['x'].min()) if df['x'].max() != df['x'].min() else 0
        df['y_norm'] = (df['y'] - df['y'].min()) / (df['y'].max() - df['y'].min()) if df['y'].max() != df['y'].min() else 0


    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    for _, row in df_edges.iterrows():
        ax.plot([row['from_x'], row['to_x']], [row['from_y'], row['to_y']], color=row['color'], alpha=0.4, linewidth=0.4)
    sc = ax.scatter(df['x'], df['y'], s=df['size']*20, c=df['color'], alpha=0.5)
    for i, row in df.iterrows():
        ax.text(row['x'], row['y']+0.02, row['id'], fontsize=labelsize, ha='center', va='bottom', alpha=0.7)
    ax.set_xlabel('Year')
    ax.set_ylabel('')
    xticks = sorted(df['x'].unique())
    ax.set_xticks(xticks)
    ax.set_xticklabels([str(int(x)) for x in xticks], rotation=90, fontsize=labelsize+4, fontweight='bold')
    ax.set_yticks([])
    ax.set_title('Historical Direct Citation Network')
    ax.set_facecolor('white')
    plt.tight_layout()

    results = {
        'net': G,
        'fig': fig,
        'graph_data': histResults['histData'],
        'layout': df,
        'axis': {'label': [str(int(x)) for x in xticks], 'values': xticks},
    }
    return results
