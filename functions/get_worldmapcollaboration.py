from www.services import *

import pandas as pd
import geopandas as gpd
import networkx as nx
import plotly.express as px
import plotly.graph_objects as go

def get_world_map_collaboration(df, edges_min=1, edgesize=5):
    # Estrai metadati dai paesi (assumi che tu abbia già AU_CO processato)
    M = df
    df = metaTagExtraction(df, "AU_CO")
    df = df.get()

    # Normalizza e conta le occorrenze dei paesi (come in get_countries_production)
    df["AU_CO"] = df["AU_CO"].apply(lambda x: x if isinstance(x, list) else [x])
    df = df.explode("AU_CO")

    def clean_country_names(country):
        corrections = {
            "USA": "UNITED STATES OF AMERICA",
            "UK": "UNITED KINGDOM",
            "SOUTH KOREA": "KOREA",
        }
        return corrections.get(str(country).upper().strip(), str(country).upper().strip())

    df["AU_CO"] = df["AU_CO"].apply(clean_country_names)

    # Calcola la frequenza dei paesi
    country_counts = df["AU_CO"].value_counts().reset_index()
    country_counts.columns = ["Tab", "Freq"]

    # Costruisci matrice di collaborazione
    net = biblionetwork(M, analysis="collaboration", network="countries")
    net_df = pd.DataFrame(net)

    # Costruisci rete
    G = nx.from_pandas_adjacency(net_df)
    COedges = []
    for u, v, d in G.edges(data=True):
        if u != v:
            COedges.append({'From': u, 'To': v, 'count': net_df.loc[u, v]})
    COedges = pd.DataFrame(COedges)
    if not COedges.empty:
        COedges = COedges[COedges['From'] != COedges['To']]
        COedges['key'] = COedges.apply(lambda x: tuple(sorted([x['From'], x['To']])), axis=1)
        COedges = COedges.groupby('key').agg({'From': 'first', 'To': 'first', 'count': 'sum'}).reset_index(drop=True)
        tab = COedges.copy()
        COedges = COedges[COedges['count'] >= edges_min]
    else:
        tab = pd.DataFrame(columns=['From', 'To', 'count'])

    # Carica geometrie mondo
    url = "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip"
    world = gpd.read_file(url)
    world['Nations'] = world['SOVEREIGNT'].str.upper().str.strip()
    world['Nations'] = world['Nations'].replace({
        "USA": "UNITED STATES OF AMERICA",
        "UK": "UNITED KINGDOM",
        "SOUTH KOREA": "KOREA"
    })
    world = world.dissolve(by="Nations").reset_index()

    # Unisci i dati dei paesi con le frequenze corrette
    country_prod = world.merge(country_counts, how='left', left_on='Nations', right_on='Tab')
    country_prod = country_prod.drop_duplicates(subset=['Nations'])
    country_prod['Freq'] = country_prod['Freq'].fillna(0)

    # Ottieni coordinate centroidi
    countries_coords = world[['Nations', 'geometry']].copy()
    countries_coords['Longitude'] = countries_coords['geometry'].centroid.x
    countries_coords['Latitude'] = countries_coords['geometry'].centroid.y

    # Aggiorna manualmente le coordinate di UNITED KINGDOM e FRANCIA
    countries_coords.loc[countries_coords['Nations'] == 'UNITED KINGDOM', ['Longitude', 'Latitude']] = [-3.4360, 55.3781]
    countries_coords.loc[countries_coords['Nations'] == 'FRANCE', ['Longitude', 'Latitude']] = [2.2137, 46.6034]

    # Aggiungi Singapore manualmente se non presente
    if 'SINGAPORE' not in countries_coords['Nations'].values:
        # Coordinate approssimative per Singapore
        singapore_row = pd.DataFrame([{
            'Nations': 'SINGAPORE',
            'geometry': None,
            'Longitude': 103.8198,
            'Latitude': 1.3521
        }])
        countries_coords = pd.concat([countries_coords, singapore_row], ignore_index=True)

    def fix_country_name_for_merge(country):
        if country == "USA":
            return "UNITED STATES OF AMERICA"
        if country == "UK":
            return "UNITED KINGDOM"
        if country == "SOUTH KOREA":
            return "KOREA"
        return country

    if not COedges.empty:
        COedges['From'] = COedges['From'].apply(fix_country_name_for_merge)
        COedges['To'] = COedges['To'].apply(fix_country_name_for_merge)
        COedges = COedges.merge(countries_coords, left_on='From', right_on='Nations', how='left')
        COedges = COedges.rename(columns={'Longitude': 'Longitude_x', 'Latitude': 'Latitude_x'})
        COedges = COedges.merge(countries_coords, left_on='To', right_on='Nations', how='left', suffixes=('', '_y'))
        COedges = COedges.rename(columns={'Longitude': 'Longitude_y', 'Latitude': 'Latitude_y'})

        # Replace NaN or infinite values in coordinates with 0 (o altro valore di default)
        for col in ['Longitude_x', 'Latitude_x', 'Longitude_y', 'Latitude_y']:
            COedges[col] = COedges[col].replace([float('inf'), float('-inf')], pd.NA)
            COedges[col] = COedges[col].fillna(0)
    country_prod['Freq'] = country_prod['Freq'].replace([float('inf'), float('-inf')], pd.NA).fillna(0)


    # Crea mappa base
    geojson_data = country_prod.__geo_interface__
    fig = px.choropleth(
        country_prod,
        geojson=geojson_data,
        locations='Nations',
        featureidkey="properties.Nations",
        color='Freq',
        hover_name='Nations',
        hover_data={'Freq': True},
        color_continuous_scale=px.colors.sequential.Blues,
    )

    # Aggiungi edges (collaborazioni)
    if not COedges.empty:
        for _, row in COedges.iterrows():
            width = max(0.5, (row['count'] / edges_min) * edgesize)  # garantisce spessore minimo
            fig.add_trace(
                go.Scattergeo(
                    lon=[row['Longitude_x'], row['Longitude_y']],
                    lat=[row['Latitude_x'], row['Latitude_y']],
                    mode='lines',
                    line=dict(width=width, color='firebrick'),
                    opacity=0.4,
                    hoverinfo='text',
                    text=f"Collaboration between {row['From']} and {row['To']}: {row['count']}",
                    showlegend=False
                )
            )

    fig.update_geos(
        showcoastlines=True,
        showland=True,
        landcolor="rgb(250,250,250)",
        showcountries=True,
        countrycolor="gray",
        fitbounds="locations",
        visible=False,
        projection_type="natural earth",  # Imposta una proiezione statica
        lataxis_range=[-60, 85],          # Limita la latitudine per evitare lo scroll verticale
        lonaxis_range=[-180, 180],        # Limita la longitudine per evitare lo scroll orizzontale
        resolution=110,
        center=dict(lat=10, lon=0),       # Centra la mappa
        scope="world"                     # Limita la visualizzazione al mondo
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=850,
        geo=dict(
            lakecolor='white',
            projection_scale=1,
            framecolor='white',
            showcountries=True,
            showframe=False,
            showcoastlines=True,
            showland=True,
            landcolor="rgb(250,250,250)",
            center=dict(lat=10, lon=0),
            lataxis_range=[-60, 85],
            lonaxis_range=[-180, 180],
            scope="world"
        ),
        coloraxis_showscale=True,
        coloraxis=dict(
            colorbar=dict(
                orientation='h',
                yanchor='bottom',
                y=-0.2,
                xanchor='center',
                x=0.5
            )
        ),
        showlegend=False
    )

    fig.update_traces(hovertemplate=None)
    fig = go.FigureWidget(fig)
    fig._config = fig._config | {'modeBarButtonsToRemove': ['pan', 'select', 'lasso2d', 'toImage'],
                                 'displaylogo': False}

    return fig, tab