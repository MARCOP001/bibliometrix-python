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
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "cited_documents"
MEASURE_LABELS = {
    "total_cit": "Total Citations",
    "total_cit_per_year": "Total Citations per Year",
}


def load_cited_documents_function():
    module_path = PROJECT_ROOT / "functions" / "get_citeddocuments.py"
    spec = importlib.util.spec_from_file_location("get_citeddocuments", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_cited_documents


def write_summary(table, num_documents, measure, output_file):
    metric = "TotalCitation" if measure == "total_cit" else "TCperYear"
    metric_label = MEASURE_LABELS[measure]
    top_document = table.iloc[0]
    top_n = table.head(num_documents)

    lines = [
        "Cited Documents Analysis",
        f"Unique documents: {len(table)}",
        f"Documents with citations: {int((table['TotalCitation'] > 0).sum())}",
        f"Total citations: {int(table['TotalCitation'].sum())}",
        f"Ranking metric: {metric_label}",
        f"Top document: {top_document['Document']}",
        f"Top document {metric_label}: {top_document[metric]}",
        f"Top {len(top_n)} documents total citations: {int(top_n['TotalCitation'].sum())}",
    ]
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Run the ETL chain and then get_cited_documents."
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
        "--num-documents",
        type=int,
        default=10,
        help="Number of top cited documents to show in the plot.",
    )
    parser.add_argument(
        "--measure",
        choices=sorted(MEASURE_LABELS),
        default="total_cit",
        help="Citation measure to rank documents.",
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
    get_cited_documents = load_cited_documents_function()
    fig, table = get_cited_documents(
        data,
        num_of_cited_docs=args.num_documents,
        cited_docs_measure=args.measure,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    full_csv_path = output_dir / "cited_documents_table.csv"
    top_csv_path = output_dir / f"cited_documents_top_{args.num_documents}.csv"
    html_path = output_dir / "cited_documents_plot.html"
    summary_path = output_dir / "cited_documents_summary.txt"
    standardized_path = output_dir / "standardized_dataframe.csv"
    contract_path = output_dir / "standardization_report.txt"

    table.to_csv(full_csv_path, index=False)
    table.head(args.num_documents).to_csv(top_csv_path, index=False)
    write_plot_html(fig, html_path)
    write_summary(table, args.num_documents, args.measure, summary_path)
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
