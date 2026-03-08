from .utils import *
from .plotlydownload import *
from .htmldownload import *


short_analysis_name = {
    "empty_report": "Empty Report",
    "missingdata": "MissingData",
    "maininfo": "MainInfo",
    "annualsciprod": "AnnualSciProd",
    "averagecitperyear": "AverageCitPerYear",
    "threefieldsplot": "ThreeFieldsPlot",
    "mostrelsources": "MostRelSources",
    "mostloccitsources": "MostLocCitSources",
    "bradfordlaw": "BradfordLaw",
    "sourcelocimpact": "SourceLocImpact",
    "sourceprodovertime": "SourceProdOverTime",
    "mostrelauthors": "MostRelAuthors",
    "mostloccitauthors": "MostLocCitAuthors",
    "authorprodovertime": "AuthorProdOverTime",
    "lotkalaw": "LotkaLaw",
    "authorlocimpact": "AuthorLocImpact",
    "mostrelaffiliations": "MostRelAffiliations",
    "affovertime": "AffOverTime",
    "corrauthcountries": "CorrAuthCountries",
    "countrysciprod": "CountrySciProd",
    "countryprodovertime": "CountryProdOverTime",
    "mostcitcountries": "MostCitCountries",
    "mostglobcitdocs": "MostGlobCitDocs",
    "mostloccitdocs": "MostLocCitDocs",
    "mostloccitrefs": "MostLocCitRefs",
    "rpys": "RPYS",
    "mostfreqwords": "MostFreqWords",
    "wordcloud": "WordCloud",
    "treemap": "TreeMap",
    "wordfreqovertime": "WordFreqOverTime",
    "trendtopics": "TrendTopics",
    "couplingmap": "CouplingMap",
    "cowordnet": "CoWordNet",
    "thematicmap": "ThematicMap",
    "thematicevolution": "ThematicEvolution",
    "te_period_1": "TE_Period_1",
    "te_period_2": "TE_Period_2",
    "te_period_3": "TE_Period_3",
    "te_period_4": "TE_Period_4",
    "te_period_5": "TE_Period_5",
    "factorialanalysis": "FactorialAnalysis",
    "cocitnet": "CoCitNet",
    "historiograph": "Historiograph",
    "collabnet": "CollabNet",
    "collabworldmap": "CollabWorldMap"
}

long_analysis_name = {
    "empty_report": "Empty Report",
    "missingdata": "Missing Data Table",
    "maininfo": "Main Information",
    "annualsciprod": "Annual Scientific Production",
    "averagecitperyear": "Average Citations Per Year",
    "threefieldsplot": "Three-Field Plot",
    "mostrelsources": "Most Relevant Sources",
    "mostloccitsources": "Most Local Cited Sources",
    "bradfordlaw": "Bradfords Law",
    "sourcelocimpact": "Sources Local Impact",
    "sourceprodovertime": "Sources Production over Time",
    "mostrelauthors": "Most Relevant Authors",
    "mostloccitauthors": "Most Local Cited Authors",
    "authorprodovertime": "Authors Production over Time",
    "lotkalaw": "Lotkas Law",
    "authorlocimpact": "Authors Local Impact",
    "mostrelaffiliations": "Most Relevant Affiliations",
    "affovertime": "Affiliations Production over Time",
    "corrauthcountries": "Corresponding Authors Countries",
    "countrysciprod": "Countries Scientific Production",
    "countryprodovertime": "Countries Production over Time",
    "mostcitcountries": "Most Cited Countries",
    "mostglobcitdocs": "Most Global Cited Documents",
    "mostloccitdocs": "Most Local Cited Documents",
    "mostloccitrefs": "Most Local Cited References",
    "rpys": "Reference Spectroscopy",
    "mostfreqwords": "Most Frequent Words",
    "wordcloud": "WordCloud",
    "treemap": "TreeMap",
    "wordfreqovertime": "Words Frequency over Time",
    "trendtopics": "Trend Topics",
    "couplingmap": "Clustering by Coupling",
    "cowordnet": "Co-occurence Network",
    "thematicmap": "Thematic Map",
    "thematicevolution": "Thematic Evolution",
    "te_period_1": "TE_Period_1",
    "te_period_2": "TE_Period_2",
    "te_period_3": "TE_Period_3",
    "te_period_4": "TE_Period_4",
    "te_period_5": "TE_Period_5",
    "factorialanalysis": "Factorial Analysis",
    "cocitnet": "Co-citation Network",
    "historiograph": "Historiograph",
    "collabnet": "Collaboration Network",
    "collabworldmap": "Countries Collaboration World Map"
}


def save_report(report, tables, plots, sheet_name):
    """
    Save a report with tables and plots in an Excel file.

    Args:
        report (io.BytesIO()): File object to save the report.
        tables (list): List of DataFrames da salvare come tabelle.
        plots (list): List of Plotly figures da salvare come grafici.
        analysis_name (str): Name of the analysis to be used as the sheet name.
    
    Returns:
        bytes: Content of the Excel file.
    """
    # === Writing the report ===
    if report.getbuffer().nbytes > 0:
        wb = load_workbook(report, rich_text=True)
    else:
        wb = Workbook()
        wb.remove(wb.active)

    base_sheet_name = sheet_name.split("-") if "-" in sheet_name else [sheet_name, 0]
    sheet_name = f"{short_analysis_name[base_sheet_name[0]]}({base_sheet_name[1]})" if base_sheet_name[1] != 0 else short_analysis_name[base_sheet_name[0]]
    if sheet_name in wb.sheetnames:
        raise ValueError(f"The sheet name '{sheet_name}' already exists. Please choose a different name.")

    ws = wb.create_sheet(title=sheet_name)

    start_row = 0
    for idx, df in enumerate(tables):
        header = list(df.columns)
        data = df.values.tolist()
        rows = [header] + data
        first_row = start_row + 1
        last_col = len(header)
        last_row = first_row + len(data)

        for r_idx, row in enumerate(rows, start=first_row):
            for c_idx, value in enumerate(row, start=1):
                ws.cell(row=r_idx, column=c_idx, value=str(value) if isinstance(value, list) else value)

        # Table style
        tab_name = f"Table_{sheet_name}_{idx + 1}"
        table_range = f"A{first_row}:{get_column_letter(last_col)}{last_row}"
        tab = Table(displayName=tab_name, ref=table_range)

        style = TableStyleInfo(
            name="TableStyleMedium9", showFirstColumn=False,
            showLastColumn=False, showRowStripes=True, showColumnStripes=False
        )
        tab.tableStyleInfo = style
        ws.add_table(tab)

        start_row = last_row + 2  # Leave one empty row after each table

    # Calculate starting column for plots after the last table
    max_columns = max((df.shape[1] for df in tables), default=0)
    col_offset = max_columns + 2  # One empty column after the last table

    # Insert plots vertically starting from row 1
    current_col = col_offset
    first_row = 1
    for fig in plots:
        if isinstance(fig, str):
            img_bytes = html_download(fig, title=long_analysis_name[base_sheet_name[0]], dpi=225)
        else:
            img_bytes = plotly_download(fig, title=long_analysis_name[base_sheet_name[0]], dpi=75)
        image = Image.open(io.BytesIO(img_bytes))
        img = XLImage(image)

        # Convert column index to Excel letter (A, B, C, ...)
        col_letter = get_column_letter(current_col)
        img.anchor = f"{col_letter}{first_row}"
        ws.add_image(img)

        image_height = image.height  # in pixel
        row_increment = int(image_height / 15 / 1.33) + 1
        first_row += row_increment + 2  # Vertical space + 1 empty row

    # Save the final Excel file
    wb.save(report)
    wb.close()
    
    return report


def add_to_report(report_choices, report_excel, tables, plots, analysis_name):
    """
    Add tables and plots to an existing report.

    Args:
        report (io.BytesIO()): File object to save the report.
        tables (list): List of DataFrames to save as tables.
        plots (list): List of Plotly figures to save as plots.
        analysis_name (str): Name of the analysis to be used as the sheet name.
    
    Returns:
        bytes: Content of the updated Excel file.
    """
    add_choices = report_choices.get()
    count = sum(1 for k in add_choices if k.startswith(analysis_name))
    if count == 0:
        add_choices[analysis_name] = long_analysis_name[analysis_name]
        sheet_name = analysis_name
    else:
        add_choices[f"{analysis_name}-{count+1}"] = f"{long_analysis_name[analysis_name]}({count+1})"
        sheet_name = analysis_name + f"-{count+1}"
    report_choices.set(add_choices)
    report_excel = report_excel.get()

    return save_report(report_excel, tables, plots, sheet_name)
