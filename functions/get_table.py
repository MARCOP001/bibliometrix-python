from www.services import *
from functions.get_status import *


# Function to create a Plotly table visualization for metadata completeness
def create_plotly_table(sorted_columns, dpi=300):
    # Extract column values for the table
    metadata = [col for col, _, _, _, _ in sorted_columns]
    descriptions = [desc for _, desc, _, _, _ in sorted_columns]
    counts = [cnt for _, _, cnt, _, _ in sorted_columns]
    percentages = [f"{pct:.2f}%" for _, _, _, pct, _ in sorted_columns]
    statuses = [status for _, _, _, _, status in sorted_columns]

    # Define colors for each status
    status_colors = {
        "Excellent": "lightgreen",
        "Good": "yellow",
        "Fair": "orange",
        "Poor": "red"
    }
    color_cells = [status_colors.get(s, "white") for s in statuses]

    # Create the Plotly table figure
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=["<b>Metadata</b>", "<b>Description</b>", "<b>Missing Counts</b>", "<b>Missing %</b>", "<b>Status</b>"],
            line_color='darkslategray',
            fill_color='#5567BB',
            align='center',
            font=dict(color='black', size=13)
        ),
        cells=dict(
            values=[metadata, descriptions, counts, percentages, statuses],
            line_color='darkslategray',
            fill_color=[["white"] * len(metadata)] * 4 + [color_cells],
            align='center',
            font=dict(color='black', size=12),
            height=30
        )
    )])

    # Set dynamic height: 30px per row plus header (120px)
    table_height = 120 + len(metadata) * 30

    fig.update_layout(
        title_text="Missing Data Table",
        title_font_size=0.08 * dpi,
        title_font_color="black",
        title_yanchor='top',
        width=1400,
        height=table_height,
        margin=dict(l=10, r=10, t=70, b=10),  # Reduced margins
        paper_bgcolor="white",  # White background without border
    )

    fig.add_layout_image(
        dict(
            source="https://raw.githubusercontent.com/massimoaria/bibliometrix/master/logo.png", 
            xref="paper", yref="paper",
            x=1, y=1,  # Top right corner
            sizex=0.07, sizey=0.07,
            xanchor="right", yanchor="bottom"
        )
    )

    return fig

# Function to generate and display the completeness table for bibliographic metadata
def get_table(database, df, dpi=300, filter=False, modal=True):
    """
    Display a table showing the completeness of bibliographic metadata.

    Args:
        database: The name of the database.
        df: A DataFrame object containing the data.
        filter: A boolean indicating whether to filter the data.

    Returns:
        A DataTable object if data is available, otherwise a message indicating no data.
    """
    # Retrieve the data from the DataFrame
    data = df.get()

    table_html = ""
    fig = None
    if not filter:
        # Get the total number of rows in the dataset
        total_rows = len(data)

        # Dictionary mapping column codes to their descriptions
        column_descriptions = {
            "AB": "Abstract",
            "AU": "Authors",
            "AU_UN": "Authors University",
            "DB": "Source",
            "DE": "Keywords",
            "DT": "Document Type",
            "LA": "Language",
            "PU": "Publisher",
            "PY": "Publication Year",
            "RP": "Correspondence Address",
            "SC": "Fields of Study",
            "SO": "Journal",
            "SR": "Authors, Publication Year and Journal",
            "TC": "Time Cited",
            "TI": "Title",
            "UT": "Publication ID",
            "C1": "Authors Affiliations",
            "CR": "Cited References",
            "OI": "Author's ORCID",
            "AU1_UN": "First Author University",
            "EM": "Author Email",
            "DI": "DOI",
            "BP": "Begin Page",
            "EP": "End Page",
            "SN": "ISSN",
            "VL": "Volume",
            "ID": "Index Keywords",
            "FU": "Funding Details",
            "FX": "Acknowledgements",
            "JI": "Abbreviated Source Title",
            "OA": "Open Access",
            "IS": "Issue",
            "PMID": "PubMed ID",
        }

        # Count missing values (NaN), empty strings, and empty lists in each column
        missing_counts = data.isna().sum() + (data == "").sum() + (data == " ").sum() + (
            data.map(lambda x: x == [])).sum()

        # Calculate the percentage of missing values for each column
        missing_percentage = (missing_counts / total_rows) * 100

        # Get the status for each column based on missing percentage
        missing_status = get_status(missing_percentage)

        # Sort columns by the number of missing values
        sorted_columns = sorted(
            zip(
                missing_counts.index,  # Column names
                [column_descriptions.get(col, col) for col in missing_counts.index],  # Descriptions
                missing_counts,  # Missing values count
                missing_percentage,  # Missing percentage
                missing_status  # Status
            ),
            key=lambda x: x[2]  # Sort by missing count
        )

        # Create and return the Plotly table
        fig = create_plotly_table(sorted_columns, dpi)

        # HTML table header
        table_header = """
        <table style="width:100%; border-collapse: collapse;">
            <thead>
                <tr style="border-bottom: 2px solid #dddddd;">
                    <th style="text-align: center; padding: 8px;">Metadata</th>
                    <th style="text-align: center; padding: 8px;">Description</th>
                    <th style="text-align: center; padding: 8px;">Missing Counts</th>
                    <th style="text-align: center; padding: 8px;">Missing %</th>
                    <th style="text-align: center; padding: 8px;">Status</th>
                </tr>
            </thead>
            <tbody>
        """

        # HTML table rows for each column
        table_rows = ""
        for col, description, count, percent, status_z in sorted_columns:
            status_style = get_status_color(status_z)

            table_rows += f"""
            <tr style="border-bottom: 1px solid #dddddd;">
                <td style="text-align: center; padding: 8px;">{col}</td>
                <td style="text-align: center; padding: 8px;">{description}</td>
                <td style="text-align: center; padding: 8px;">{count}</td>
                <td style="text-align: center; padding: 8px;">{percent:.2f}%</td>
                <td style="text-align: center; padding: 8px; {status_style}">{status_z}</td>
            </tr>
            """

        # HTML table footer
        table_footer = "</tbody></table>"

        # Combine header, rows, and footer to form the complete HTML table
        table_html = table_header + table_rows + table_footer

        # If modal is True, create and show a modal dialog with the table
        if modal:
            m = ui.modal(
                ui.HTML(f"""{table_html}"""),
                title=f"Completeness of bibliographic metadata - {len(data)} documents from {database}",
                easy_close=False,
                footer=ui.div(
                    ui.input_action_button("advice_modal_completeness", "Advice", icon=ICONS["info"], style="background: #5865B9; color: white"),
                    ui.input_action_button("report_modal_completeness", "Report", icon=ICONS["plus"], style="background: #5865B9; color: white"),
                    ui.input_action_button("save_modal_completeness", "Save", icon=ICONS["download"], style="background: #5865B9; color: white"),
                    ui.modal_button("Close", style="background: #5865B9; color: white")
                ),
                size="l"
            )
            ui.modal_show(m)

    if data is not None:
        # Return a DataTable object with the data and the HTML/Plotly tables
        return ui.HTML(
            DT(
                df.get(),
                maxBytes="10MB",
                classes="display compact stripe",
                style="text-transform: uppercase; font-size: small; table-layout: auto;",
                buttons=["pageLength",
                        {"extend": "csvHtml5", "title": f"{database}_Bibliometrix"},
                        {"extend": "excelHtml5", "title": f"{database}_Bibliometrix"}
                ],
                columnDefs=[
                    {
                        "targets": "_all",  # Apply to all columns
                        "createdCell": JavascriptFunction("""
                            function (td, cellData, rowData, row, col) {
                                // If the cell data is a string and longer than 200 characters, truncate and add tooltip
                                if (typeof cellData === 'string' && cellData.length > 200) {
                                    const truncatedText = cellData.substring(0, 200) + '...';
                                    $(td).text(truncatedText); // Set truncated text
                                    $(td).attr('title', cellData); // Add full text as tooltip
                                    $(td).css('overflow', 'hidden');
                                    $(td).css('text-overflow', 'ellipsis'); // Add ellipsis
                                    $(td).css('vertical-align', 'top'); // Align text to top
                                } else {
                                    // For all other cells, align text to top
                                    $(td).css('vertical-align', 'top');
                                }
                            }
                        """)
                    }
                ],
                eval_functions=True
            )
        ), table_html, fig
    else:
        # Show a message if no data is available
        return ui.h5("No data available. Please upload a file."), "", None
