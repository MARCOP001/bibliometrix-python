import argparse
import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.etl_analysis_common import (
    extract_standardized_dataframe,
    write_standardization_report,
    write_standardized_dataframe,
)


DEFAULT_INPUT = PROJECT_ROOT / "sources" / "Scopus" / "Scopus.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "annual_production"


def load_annual_production_function():
    module_path = PROJECT_ROOT / "functions" / "get_annualproduction.py"
    spec = importlib.util.spec_from_file_location("get_annualproduction", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_annual_production


def write_summary(table, output_file):
    total_documents = int(table["Freq"].sum())
    start_year = int(table["Year"].min())
    end_year = int(table["Year"].max())
    peak = table.sort_values(["Freq", "Year"], ascending=[False, True]).iloc[0]

    lines = [
        "Annual Production Analysis",
        f"Documents with valid year: {total_documents}",
        f"Year range: {start_year}-{end_year}",
        f"Peak year: {int(peak['Year'])} ({int(peak['Freq'])} documents)",
    ]
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Run the ETL chain and then get_annual_production."
    )
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Raw bibliographic CSV/XLSX/TXT/CIW/BIB/ZIP file to extract and standardize.",
    )
    parser.add_argument(
        "--source",
        default="SCOPUS",
        help="Raw source name passed to the ETL dispatcher, e.g. SCOPUS, WEB_OF_SCIENCE, PUBMED.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where CSV, HTML plot, and summary files will be written.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of raw records to process.",
    )
    args = parser.parse_args()

    raw_records, data = extract_standardized_dataframe(
        args.input,
        source=args.source,
        limit=args.limit,
    )
    get_annual_production = load_annual_production_function()
    fig, table = get_annual_production(data)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "annual_production_table.csv"
    html_path = output_dir / "annual_production_plot.html"
    summary_path = output_dir / "annual_production_summary.txt"
    standardized_path = output_dir / "standardized_dataframe.csv"
    contract_path = output_dir / "standardization_report.txt"

    table.to_csv(csv_path, index=False)
    fig.write_html(html_path, include_plotlyjs=True, full_html=True)
    write_summary(table, summary_path)
    write_standardized_dataframe(data, standardized_path)
    write_standardization_report(data, contract_path)

    print(f"Raw records: {len(raw_records)}")
    print(f"Standardized rows: {len(data)}")
    print(f"Standardized DataFrame: {standardized_path}")
    print(f"Standardization report: {contract_path}")
    print(f"Table: {csv_path}")
    print(f"Plot: {html_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
