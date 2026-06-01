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
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "relevant_sources"


def load_relevant_sources_function():
    module_path = PROJECT_ROOT / "functions" / "get_relevantsources.py"
    spec = importlib.util.spec_from_file_location("get_relevantsources", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_relevant_sources


def write_summary(table, num_sources, output_file):
    total_documents = int(table["N. of Documents"].sum())
    unique_sources = len(table)
    top_source = table.iloc[0]
    top_n = table.head(num_sources)
    top_n_share = round(100 * top_n["N. of Documents"].sum() / total_documents, 2)

    lines = [
        "Relevant Sources Analysis",
        f"Documents with valid source: {total_documents}",
        f"Unique sources: {unique_sources}",
        f"Top source: {top_source['Sources']} ({int(top_source['N. of Documents'])} documents)",
        f"Top {len(top_n)} sources share: {top_n_share}%",
    ]
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Run the ETL chain and then get_relevant_sources."
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
        "--num-sources",
        type=int,
        default=10,
        help="Number of top sources to show in the plot.",
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
    get_relevant_sources = load_relevant_sources_function()
    fig, table = get_relevant_sources(data, num_of_sources=args.num_sources)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    full_csv_path = output_dir / "relevant_sources_table.csv"
    top_csv_path = output_dir / f"relevant_sources_top_{args.num_sources}.csv"
    html_path = output_dir / "relevant_sources_plot.html"
    summary_path = output_dir / "relevant_sources_summary.txt"
    standardized_path = output_dir / "standardized_dataframe.csv"
    contract_path = output_dir / "standardization_report.txt"

    table.to_csv(full_csv_path, index=False)
    table.head(args.num_sources).to_csv(top_csv_path, index=False)
    fig.write_html(html_path, include_plotlyjs=True, full_html=True)
    write_summary(table, args.num_sources, summary_path)
    write_standardized_dataframe(data, standardized_path)
    write_standardization_report(data, contract_path)

    print(f"Raw records: {len(raw_records)}")
    print(f"Standardized rows: {len(data)}")
    print(f"Standardized DataFrame: {standardized_path}")
    print(f"Standardization report: {contract_path}")
    print(f"Full table: {full_csv_path}")
    print(f"Top table: {top_csv_path}")
    print(f"Plot: {html_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()
