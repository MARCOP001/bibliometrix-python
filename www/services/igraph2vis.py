from .utils import *
from .networkplot import *


def igraph2vis(graph, cluster_obj, cm_clusters, community_repulsion, node_opacity=0.3):
    """
    Convert igraph object to vis.js format.

    Args:
        graph (igraph.Graph): The igraph graph object to convert.
        cluster_obj (object): Clustering object containing membership information.
        cm_clusters (DataFrame): DataFrame containing cluster information including colors.
        community_repulsion (bool): Whether to apply community repulsion.
        node_opacity (float): Opacity for nodes, default is 0.3.

    Returns:
        dict: Dictionary containing nodes and edges.
    """
    # Convert igraph to vis.js format
    # Initialize Pyvis network with matching R settings
    net = Network(height="800px", width="100%", notebook=True, cdn_resources="in_line")
    net.toggle_physics(False)

    # Use colors from df['adjusted_color']
    unique_clusters = set(cluster_obj.membership)
    cluster_colors = {}
    
    # Get unique cluster IDs and their colors
    for i, cluster_id in enumerate(unique_clusters):
        if i < len(cm_clusters):
            # Get hex color from DataFrame and convert to rgba
            hex_color = cm_clusters['adjusted_color'].iloc[i]
            # Convert hex to rgb format
            hex_color = hex_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            cluster_colors[cluster_id] = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{node_opacity})"
        else:
            # Fallback for any additional clusters
            cluster_colors[cluster_id] = f"rgba(128,128,128,0.3)"  # Default gray

    # Generate layout
    graph_layout = switch_layout(graph, type='fruchterman', community_repulsion=community_repulsion)
    layout = graph_layout['l']
    # Get coordinates from layout
    coords = np.array([[pos[0], pos[1]] for pos in layout])
    
    # Scale coordinates to fit 800px height
    # First normalize to [-1,1] range
    # coords = coords / np.abs(coords).max()
    
    # Then scale to target dimensions
    # Width will be proportional to maintain aspect ratio
    # coords[:, 0] *= 1000  # Scale x coordinates 
    # coords[:, 1] *= 400   # Scale y coordinates to fit 800px (centered)

    # Prepare for avoid_net_overlaps
    node_labels = [v["name"] if "name" in v.attributes() else f"Node {v.index}" for v in graph.vs]
    node_sizes = []
    nodes = []
    
    # Add nodes with matching R visNetwork settings
    for idx, vertex in enumerate(graph.vs):
        cluster_id = cluster_obj.membership[vertex.index]
        node_color = cluster_colors[cluster_id]

        # Normalize node sizes
        min_deg, max_deg = min(graph.degree()), max(graph.degree())
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
                'vadjust': -10
            },
            'shadow': True,
            'shape': 'dot',
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
    edge_weights = [e.attributes().get('weight', 1) for e in graph.es]
    max_weight = max(edge_weights) if edge_weights else 1
    
    for edge in graph.es:
        source, target = edge.tuple
        cluster_source = cluster_obj.membership[source]
        cluster_target = cluster_obj.membership[target]
        
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
    net.set_options("""
        var options = {
            "nodes": {
                "shadow": true
            },
            "edges": {
                "smooth": {"type": "horizontal"}
            },
            "interaction": {
                "dragNodes": true,
                "hideEdgesOnDrag": true,
                "navigationButtons": false,
                "zoomSpeed": 0.4
            },
            "physics": {
                "enabled": false
            },
            "manipulation": {
                "enabled": false
            }
        }
    """)

    # Save network to HTML
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    html_path = tmp.name
    with open(html_path, 'w', encoding="utf-8") as f:
        f.write(net.generate_html())

    return html_path, nodes


def avoid_net_overlaps(coords, labels, sizes, threshold=0.10):
    """Function to avoid label overlapping
    Args:
        coords: numpy array of x,y coordinates
        labels: list of node labels
        sizes: list of node sizes (dotSizes)
        threshold: distance threshold for overlap detection
    Returns:
        list of labels to remove to avoid overlap
    """
    
    # Create dataframe of nodes with labels
    df = pd.DataFrame({
        'x': coords[:, 0],
        'y': coords[:, 1] / 2,  # Normalize y coordinates
        'label': labels,
        'size': sizes
    })
    
    # Calculate pairwise manhattan distances
    distances = squareform(pdist(df[['x', 'y']], metric='cityblock'))
    
    # Create dataframe of overlapping pairs
    overlaps = []
    n = len(labels)
    for i in range(n):
        for j in range(i+1, n):
            if distances[i,j] < threshold:
                overlaps.append({
                    'from': labels[i],
                    'to': labels[j],
                    'dist': distances[i,j],
                    'w_from': sizes[i],
                    'w_to': sizes[j]
                })
    
    if not overlaps:
        return []
    
    # Convert to dataframe
    overlaps_df = pd.DataFrame(overlaps)
    
    labels_to_remove = []
    i = 0
    
    while len(overlaps_df) > 0:
        row = overlaps_df.iloc[0]
        
        if row['w_from'] > row['w_to'] and row['dist'] < threshold:
            label = row['to']
        elif row['w_from'] <= row['w_to'] and row['dist'] < threshold:
            label = row['from']
        else:
            overlaps_df = overlaps_df.iloc[1:]
            continue
        
        # Remove rows containing this label
        overlaps_df = overlaps_df[
            (overlaps_df['from'] != label) & 
            (overlaps_df['to'] != label)
        ]
        labels_to_remove.append(label)
    
    return labels_to_remove
