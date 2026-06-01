from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIST_COLUMNS = {"AU", "AF", "C1", "CR", "DE", "ID"}


def extract_standardized_dataframe(input_file, source, limit=None):
    """Run the real ETL chain: extract raw records, convert them, validate them."""
    from www.services.file_extractor import extract_from_file
    from www.services.standardizer import convert2df

    input_file = Path(input_file)
    raw_records = extract_from_file(str(input_file), source=source)
    if limit is not None:
        raw_records = raw_records[:limit]

    standardized_df = convert2df(
        raw_records,
        source=source,
        file_type=input_file.suffix.lower(),
        validate=True,
    )
    return raw_records, standardized_df


def column_type_contracts():
    from www.services.standardizer import COLUMN_TYPE_CONTRACTS

    return COLUMN_TYPE_CONTRACTS


def dataframe_for_csv(df):
    export_df = df.copy()
    for column in LIST_COLUMNS.intersection(export_df.columns):
        export_df[column] = export_df[column].apply(
            lambda value: ";".join(value) if isinstance(value, list) else value
        )
    return export_df


def write_standardized_dataframe(df, output_file):
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    dataframe_for_csv(df).to_csv(output_file, index=False)


def write_standardization_report(df, output_file):
    contracts = column_type_contracts()
    missing_columns = [column for column in contracts if column not in df.columns]
    type_errors = []

    for column, expected_type in contracts.items():
        if column not in df.columns:
            continue
        invalid_count = sum(
            not isinstance(value, expected_type)
            for value in df[column]
        )
        if invalid_count:
            type_errors.append(f"{column}: {invalid_count} invalid values")

    lines = [
        "Standardization Contract Report",
        f"Rows: {len(df)}",
        f"Columns: {len(df.columns)}",
        f"Missing required columns: {', '.join(missing_columns) if missing_columns else 'none'}",
        f"Type errors: {', '.join(type_errors) if type_errors else 'none'}",
        "",
        "Column types expected by the ETL contract:",
    ]

    for column, expected_type in contracts.items():
        present = "present" if column in df.columns else "missing"
        lines.append(f"- {column}: {expected_type.__name__} ({present})")

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
