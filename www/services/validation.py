"""
Funzioni di supporto per la convalida nella pipeline ETL di Bibliometrix.

Lo schema di destinazione ETL rispecchia i tag di Web of Science utilizzati dalle funzioni analitiche.
Queste funzioni di supporto mantengono la convalida separata dall'estrazione e dalla trasformazione, come richiesto dalla traccia d'esame.
"""

from __future__ import annotations
from typing import Any
import pandas as pd


class ValidationError(Exception):
    """Eccezione sollevata quando l'output standardizzato viola il contratto ETL."""


MULTI_VALUE_COLUMNS: set[str] = {"AU", "AF", "C1", "CR", "DE", "ID"}


def _is_missing(value: Any) -> bool:
    """Riconosce valori mancanti non ammessi nell'output standardizzato.

    Args:
        value: Valore da verificare durante la validazione di record o DataFrame.

    Returns:
        "True" se il valore e' "None", "NaN" pandas oppure una stringa che rappresenta esplicitamente un nullo; "False" altrimenti.

    Notes:
        La stringa vuota non viene considerata mancante: nello schema standardizzato e' il valore di default previsto per molti campi testuali.
    """
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip().lower() in {"nan", "none", "null"}:
        return True
    return False


def validate_record_contract(record: dict[str, Any], contracts: dict[str, type]) -> None:
    """Valida un record bibliografico standardizzato rispetto ai contratti.

    Args:
        record: Dizionario che rappresenta un singolo record nello schema target.
        contracts: Mappa "colonna -> tipo atteso" usata come contratto di validazione.

    Returns:
        "None" se il record rispetta il contratto.

    Raises:
        ValidationError: Se mancano colonne obbligatorie, se un valore è considerato nullo o se il tipo effettivo non coincide con quello atteso.

    Notes:
        Gli errori vengono raccolti tutti prima di sollevare l'eccezione, cosi' il chiamante riceve un report unico dei problemi presenti nel record.
    """
    errors: list[str] = []

    for tag, expected_type in contracts.items():
        if tag not in record:
            errors.append(f"[MISSING_COLUMN] Tag '{tag}' assente.")
            continue

        value = record[tag]
        if _is_missing(value):
            errors.append(f"[NULL_VALUE] Tag '{tag}' contiene un valore nullo.")
            continue

        # Il contratto richiede tipi Python concreti, non solo valori convertibili: la standardizzazione deve aver gia' fatto il cast.
        if not isinstance(value, expected_type):
            errors.append(
                f"[TYPE_ERROR] Tag '{tag}': atteso {expected_type.__name__}, "
                f"trovato {type(value).__name__}."
            )

    if errors:
        raise ValidationError("\n".join(errors))


def validate_dataframe_contract(df: pd.DataFrame, contracts: dict[str, type]) -> None:
    """Valida un DataFrame finale rispetto allo schema Bibliometrix.

    Args:
        df: DataFrame prodotto dalla fase di standardizzazione.
        contracts: Mappa "colonna -> tipo atteso" che definisce colonne obbligatorie e tipi dei valori.

    Returns:
        "None" se il DataFrame rispetta il contratto.

    Raises:
        ValidationError: Se mancano colonne obbligatorie, se sono presenti valori null-like non ammessi o se almeno un valore ha tipo non conforme.

    Notes:
        Il messaggio finale include al massimo i primi 25 errori per mantenere leggibile il report anche su dataset molto grandi.
    """
    errors: list[str] = []

    missing_columns = [col for col in contracts if col not in df.columns]
    if missing_columns:
        errors.append(f"[MISSING_COLUMNS] Colonne assenti: {', '.join(missing_columns)}")

    for col in [c for c in contracts if c in df.columns]:
        expected_type = contracts[col]
        for idx, value in df[col].items():
            # La validazione avviene cella per cella per individuare la riga precisa che rompe il contratto del DataFrame.
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
