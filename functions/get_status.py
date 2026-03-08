from www.services import *


def get_status(missing_percentage):
    """
    Assign status based on the percentage of missing values.
    
    Args:
        missing_percentage: A list of percentages of missing values for each column.
        
    Returns:
        A list of status strings corresponding to each percentage.
    """
    conditions = []
    
    for x in missing_percentage:
        if x == 0:
            conditions.append("Excellent")              # Excellent missing values
        elif 0 < x <= 10:
            conditions.append("Good")                   # Good missing values
        elif 10 < x <= 20:
            conditions.append("Acceptable")             # Acceptable missing values
        elif 20 < x <= 50:
            conditions.append("Poor")                   # Poor missing values
        elif 50 < x < 100:
            conditions.append("Critical")               # Critical missing values
        elif x == 100 or pd.isna(x):
            conditions.append("Completely missing")     # Completely missing values
        else:
            conditions.append("Unknown")                # Fallback case
    
    return conditions


def get_status_color(status):
    """
    Returns a background color based on the status.
    
    Args:
        status: A string representing the status.
        
    Returns:
        A string containing CSS styles for the background color.
    """
    if status == "Excellent":
        return "background-color: #00C851; color: white;"  # Green for Excellent
    elif status == "Good":
        return "background-color: #A5D6A7; color: black;"  # Light green for Good
    elif status == "Acceptable":
        return "background-color: #FFEB3B; color: black;"  # Yellow for Acceptable
    elif status == "Poor":
        return "background-color: #BDBDBD; color: black;"  # Gray for Poor
    elif status == "Critical":
        return "background-color: #F44336; color: white;"  # Red for Critical
    elif status == "Completely missing":
        return "background-color: #B71C1C; color: white;"  # Dark red for Completely missing
    else:
        return "background-color: gray; color: white;"     # Default gray for unknown statuses
