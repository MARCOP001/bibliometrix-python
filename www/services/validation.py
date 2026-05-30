"""Validation helpers for the Bibliometrix ETL pipeline.

The ETL target schema mirrors the Web of Science tags used by the analytical
functions.  These helpers keep validation separate from extraction and
transformation, as required by the exam trace.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class ValidationError(Exception):
    """Raised when a standardized record or DataFrame violates the ETL contract."""


MULTI_VALUE_COLUMNS: set[str] = {"AU", "AF", "C1", "CR", "DE", "ID"}


def _is_missing(value: Any) -> bool:
    """Return True for values that must not survive in standardized output."""
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip().lower() in {"nan", "none", "null"}:
        return True
    return False


def validate_record_contract(record: dict[str, Any], contracts: dict[str, type]) -> None:
    """Validate one standardized bibliographic record against type contracts."""
    errors: list[str] = []

    for tag, expected_type in contracts.items():
        if tag not in record:
            errors.append(f"[MISSING_COLUMN] Tag '{tag}' assente.")
            continue

        value = record[tag]
        if _is_missing(value):
            errors.append(f"[NULL_VALUE] Tag '{tag}' contiene un valore nullo.")
            continue

        if not isinstance(value, expected_type):
            errors.append(
                f"[TYPE_ERROR] Tag '{tag}': atteso {expected_type.__name__}, "
                f"trovato {type(value).__name__}."
            )

    if errors:
        raise ValidationError("\n".join(errors))


def validate_dataframe_contract(df: pd.DataFrame, contracts: dict[str, type]) -> None:
    """Validate the finalized standardized DataFrame."""
    errors: list[str] = []

    missing_columns = [col for col in contracts if col not in df.columns]
    if missing_columns:
        errors.append(f"[MISSING_COLUMNS] Colonne assenti: {', '.join(missing_columns)}")

    for col in [c for c in contracts if c in df.columns]:
        expected_type = contracts[col]
        for idx, value in df[col].items():
            if _is_missing(value):
                errors.append(f"[NULL_VALUE] Riga {idx}, colonna '{col}' contiene un nullo.")
                continue
            if not isinstance(value, expected_type):
                errors.append(
                    f"[TYPE_ERROR] Riga {idx}, colonna '{col}': atteso "
                    f"{expected_type.__name__}, trovato {type(value).__name__}."
                )

    if errors:
        raise ValidationError("\n".join(errors[:25]))
