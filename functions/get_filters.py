from www.services import *
from functions.get_table import *


def get_filters(df):
    """
    Calculate various filters and metrics for the DataFrame.

    Args:
        df: A DataFrame object containing the data.

    Returns:
        A DataFrame with additional columns for filters and metrics.
    """
    data = df.get()

    # Calculate the minimum and maximum publication years
    data["Min_Year"] = data["PY"].min()
    data["Max_Year"] = data["PY"].max()
    
    # Calculate the number of years since publication
    current_year = pd.Timestamp.now().year
    data["Years_Since_Publication"] = current_year - data["PY"] + 1

    # Calculate the average citations per year
    data["Average_Citations_Per_Year"] = data["TC"] / data["Years_Since_Publication"]

    # Calculate the minimum and maximum average citations per year
    data["Min_Citations"] = np.floor(data["Average_Citations_Per_Year"].min())
    data["Max_Citations"] = np.ceil(data["Average_Citations_Per_Year"].max())

    # Calculate Bradford Law Zones
    SO_counts = data['SO'].value_counts()  # Count occurrences of each source
    n = SO_counts.sum()  # Total number of occurrences
    cum_freq = SO_counts.cumsum()  # Cumulative frequency of occurrences

    # Define cutpoints for Bradford Law Zones
    cutpoints = np.array([1, n * 0.33, n * 0.67, n + 1]).astype(int)

    # Assign zones based on cumulative frequency
    groups = pd.cut(cum_freq, bins=cutpoints, labels=["Zone 1", "Zone 2", "Zone 3"], right=False)

    # Create a DataFrame for zones
    zone_df = pd.DataFrame({
        'SO': SO_counts.index,
        'Freq': SO_counts.values,
        'cumFreq': cum_freq.values,
        'Zone': groups
    })
    zone_df.reset_index(drop=True, inplace=True)

    # Merge the zone information back into the original data
    data = data.merge(zone_df[['SO', 'Zone']], on='SO', how='left')
    return data


def get_filtered_table(input, database, df_filters, df_filtered):
    """
    Display a filtered table based on user-selected criteria.
    
    Args:
        input: An object that provides user input methods.
        database: The name of the database.
        df_filters: A DataFrame object containing the data with filters applied.
        df_filtered: A DataFrame object to store the filtered data.
        
    Returns:
        The result of the show_table function with the filtered data.
    """
    # Get the data from the df_filters DataFrame
    data = df_filters.get()
    
    # Apply filters based on user input
    filtered_data = data[
        (data["PY"] >= input.year_slider()[0]) &  # Filter by publication year range
        (data["PY"] <= input.year_slider()[1]) & 
        (data["LA"].isin(input.languages())) &  # Filter by selected languages
        (data["DT"].isin(input.document_types())) &  # Filter by selected document types
        (data["Average_Citations_Per_Year"] >= input.average_citations_slider()[0]) &  # Filter by average citations per year range
        (data["Average_Citations_Per_Year"] <= input.average_citations_slider()[1])
    ]

    # Apply Bradford Law Zone filter based on user selection
    selected_zone = input.bradford()
    if selected_zone == "Z1":
        filtered_data = filtered_data[filtered_data['Zone'] == "Zone 1"]
    elif selected_zone == "Z2":
        filtered_data = filtered_data[filtered_data['Zone'].isin(["Zone 1", "Zone 2"])]
    
    # Drop unnecessary columns
    filtered_data.drop(columns=["Years_Since_Publication", "Average_Citations_Per_Year"], inplace=True)

    # Set the filtered data to df_filtered DataFrame
    data = df_filtered.set(filtered_data)
    
    # Display the filtered table
    return get_table(database, df_filtered, filter=True)
