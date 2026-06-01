import argparse
import importlib.util
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.etl_analysis_common import (
    extract_standardized_dataframe,
    write_plot_html,
    write_standardization_report,
    write_standardized_dataframe,
)


DEFAULT_INPUT = PROJECT_ROOT / "sources" / "Scopus" / "Scopus.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "relevant_authors"
FREQUENCY_CHOICES = {
    "n_docs": "N. of Documents",
    "percentage": "Percentage",
    "freq_measure": "Fractionalized Frequency",
}


def load_relevant_authors_function():
    module_path = PROJECT_ROOT / "functions" / "get_relevantauthors.py"
    spec = importlib.util.spec_from_file_location("get_relevantauthors", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_relevant_authors


def output_column_name(frequency):
    return FREQUENCY_CHOICES.get(frequency, frequency)


def write_summary(table, num_authors, frequency, output_file):
    metric_column = output_column_name(frequency)
    top_author = table.iloc[0]
    top_n = table.head(num_authors)

    lines = [
        "Relevant Authors Analysis",
        f"Unique authors: {len(table)}",
        f"Metric: {metric_column}",
        f"Top author: {top_author['Authors']} ({top_author[metric_column]} {metric_column})",
        f"Top {len(top_n)} authors total: {round(top_n[metric_column].sum(), 2)}",
    ]
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Run the ETL chain and then get_relevant_authors."
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
        "--num-authors",
        type=int,
        default=10,
        help="Number of top authors to show in the plot.",
    )
    parser.add_argument(
        "--frequency",
        choices=sorted(FREQUENCY_CHOICES),
        default="n_docs",
        help="Frequency measure to compute.",
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
    get_relevant_authors = load_relevant_authors_function()
    fig, table = get_relevant_authors(
        data,
        num_of_authors=args.num_authors,
        frequency=args.frequency,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    full_csv_path = output_dir / "relevant_authors_table.csv"
    top_csv_path = output_dir / f"relevant_authors_top_{args.num_authors}.csv"
    html_path = output_dir / "relevant_authors_plot.html"
    summary_path = output_dir / "relevant_authors_summary.txt"
    standardized_path = output_dir / "standardized_dataframe.csv"
    contract_path = output_dir / "standardization_report.txt"

    table.to_csv(full_csv_path, index=False)
    table.head(args.num_authors).to_csv(top_csv_path, index=False)
    write_plot_html(fig, html_path)
    write_summary(table, args.num_authors, args.frequency, summary_path)
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
