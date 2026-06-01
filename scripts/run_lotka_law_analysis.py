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
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "lotka_law"


def load_lotka_law_function():
    module_path = PROJECT_ROOT / "functions" / "get_lotkalaw.py"
    spec = importlib.util.spec_from_file_location("get_lotkalaw", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_lotka_law


def write_summary(table, output_file):
    single_article_authors = table.loc[table["N.Articles"] == 1, "N.Authors"]
    single_article_count = int(single_article_authors.iloc[0]) if not single_article_authors.empty else 0
    total_authors = int(table["N.Authors"].sum())
    max_articles = int(table["N.Articles"].max())
    single_article_share = round(100 * single_article_count / total_authors, 2) if total_authors else 0

    lines = [
        "Lotka Law Analysis",
        f"Unique authors: {total_authors}",
        f"Maximum articles by one author: {max_articles}",
        f"Authors with one article: {single_article_count}",
        f"Authors with one article share: {single_article_share}%",
        f"Observed frequency sum: {round(float(table['Freq'].sum()), 6)}",
        f"Theoretical frequency sum: {round(float(table['Theoretical'].sum()), 6)}",
    ]
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Run the ETL chain and then get_lotka_law."
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
    get_lotka_law = load_lotka_law_function()
    fig, table = get_lotka_law(data)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "lotka_law_table.csv"
    html_path = output_dir / "lotka_law_plot.html"
    summary_path = output_dir / "lotka_law_summary.txt"
    standardized_path = output_dir / "standardized_dataframe.csv"
    contract_path = output_dir / "standardization_report.txt"

    table.to_csv(csv_path, index=False)
    write_plot_html(fig, html_path)
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
