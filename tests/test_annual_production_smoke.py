import importlib.util
import unittest
from pathlib import Path

import pandas as pd

from scripts.etl_analysis_common import (
    column_type_contracts,
    extract_standardized_dataframe,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_SCOPUS_FILE = PROJECT_ROOT / "sources" / "Scopus" / "Scopus.csv"
_SCOPUS_ETL_DF = None


def load_function(module_name, function_name):
    module_path = PROJECT_ROOT / "functions" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, function_name)


get_annual_production = load_function("get_annualproduction", "get_annual_production")
get_average_citations = load_function("get_averagecitations", "get_average_citations")
get_bradford_law = load_function("get_bradfordlaw", "get_bradford_law")
get_cited_documents = load_function("get_citeddocuments", "get_cited_documents")
get_relevant_sources = load_function("get_relevantsources", "get_relevant_sources")
get_relevant_authors = load_function("get_relevantauthors", "get_relevant_authors")
get_lotka_law = load_function("get_lotkalaw", "get_lotka_law")


class DataFrameBox:
    """Minimal stand-in for Shiny reactive.Value used by the app."""

    def __init__(self, data):
        self._data = data

    def get(self):
        return self._data


def load_scopus_etl_dataframe():
    global _SCOPUS_ETL_DF
    if _SCOPUS_ETL_DF is None:
        raw_records, standardized_df = extract_standardized_dataframe(
            RAW_SCOPUS_FILE,
            source="SCOPUS",
            limit=50,
        )
        if not raw_records:
            raise AssertionError("The raw Scopus fixture did not produce records.")
        _SCOPUS_ETL_DF = standardized_df
    return _SCOPUS_ETL_DF.copy(deep=True)


class ScopusEtlContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def test_etl_output_matches_bibliometrix_contract(self):
        contracts = column_type_contracts()
        self.assertEqual(list(self.standardized_df.columns), list(contracts))

        for column, expected_type in contracts.items():
            invalid_values = [
                value for value in self.standardized_df[column]
                if not isinstance(value, expected_type)
            ]
            self.assertEqual(invalid_values, [], f"{column} violates {expected_type.__name__}")


class AnnualProductionSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def assert_valid_annual_result(self, fig, table):
        valid_years = pd.to_numeric(self.standardized_df["PY"], errors="coerce").dropna()
        self.assertEqual(list(table.columns), ["Year", "Freq"])
        self.assertTrue(table["Year"].is_monotonic_increasing)
        self.assertEqual(int(table["Freq"].sum()), len(valid_years))
        self.assertGreater(len(fig.data), 0)

    def test_accepts_plain_standardized_dataframe(self):
        fig, table = get_annual_production(self.standardized_df)
        self.assert_valid_annual_result(fig, table)

    def test_accepts_shiny_like_dataframe_wrapper(self):
        fig, table = get_annual_production(DataFrameBox(self.standardized_df))
        self.assert_valid_annual_result(fig, table)


class AverageCitationsSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def assert_valid_average_citations_result(self, fig, table):
        valid_years = pd.to_numeric(self.standardized_df["PY"], errors="coerce").dropna()

        self.assertEqual(
            list(table.columns),
            ["Year", "MeanTCperArt", "N", "MeanTCperYear", "CitableYears"],
        )
        self.assertFalse(table.empty)
        self.assertTrue(table["Year"].is_monotonic_increasing)
        self.assertEqual(int(table["N"].sum()), len(valid_years))
        self.assertTrue((table["CitableYears"] > 0).all())
        self.assertGreater(len(fig.data), 0)

    def test_accepts_plain_standardized_dataframe(self):
        fig, table = get_average_citations(self.standardized_df)
        self.assert_valid_average_citations_result(fig, table)

    def test_accepts_shiny_like_dataframe_wrapper(self):
        fig, table = get_average_citations(DataFrameBox(self.standardized_df))
        self.assert_valid_average_citations_result(fig, table)


class BradfordLawSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def assert_valid_bradford_result(self, fig, table):
        valid_sources = self.standardized_df["SO"].dropna()
        valid_sources = valid_sources[valid_sources.astype(str).str.strip() != ""]

        self.assertEqual(list(table.columns), ["SO", "Rank", "Freq", "cumFreq", "Zone"])
        self.assertFalse(table.empty)
        self.assertEqual(int(table["Freq"].sum()), len(valid_sources))
        self.assertEqual(table["Rank"].tolist(), list(range(1, len(table) + 1)))
        self.assertTrue(table["cumFreq"].is_monotonic_increasing)
        self.assertTrue(set(table["Zone"]).issubset({"Zone 1", "Zone 2", "Zone 3"}))
        self.assertGreater(len(fig.data), 0)

    def test_accepts_plain_standardized_dataframe(self):
        fig, table = get_bradford_law(self.standardized_df)
        self.assert_valid_bradford_result(fig, table)

    def test_accepts_shiny_like_dataframe_wrapper(self):
        fig, table = get_bradford_law(DataFrameBox(self.standardized_df))
        self.assert_valid_bradford_result(fig, table)


class CitedDocumentsSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def assert_valid_cited_documents_result(self, fig, table, measure):
        source_data = self.standardized_df.copy()
        source_data["PY"] = pd.to_numeric(source_data["PY"], errors="coerce")
        source_data["TC"] = pd.to_numeric(source_data["TC"], errors="coerce").fillna(0)
        source_data = source_data.dropna(subset=["SR", "PY"])
        source_data = source_data[source_data["SR"].astype(str).str.strip() != ""]

        self.assertEqual(
            list(table.columns),
            ["Document", "DI", "TotalCitation", "TCperYear", "NormalizedTC"],
        )
        self.assertFalse(table.empty)
        self.assertAlmostEqual(
            float(table["TotalCitation"].sum()),
            float(source_data["TC"].sum()),
            places=6,
        )
        if measure == "total_cit":
            self.assertTrue(table["TotalCitation"].is_monotonic_decreasing)
        else:
            self.assertTrue(table["TCperYear"].is_monotonic_decreasing)
        self.assertGreater(len(fig.data), 0)

    def test_accepts_plain_standardized_dataframe(self):
        fig, table = get_cited_documents(
            self.standardized_df,
            num_of_cited_docs=10,
            cited_docs_measure="total_cit",
        )
        self.assert_valid_cited_documents_result(fig, table, "total_cit")

    def test_accepts_shiny_like_dataframe_wrapper(self):
        fig, table = get_cited_documents(
            DataFrameBox(self.standardized_df),
            num_of_cited_docs=10,
            cited_docs_measure="total_cit_per_year",
        )
        self.assert_valid_cited_documents_result(fig, table, "total_cit_per_year")


class RelevantSourcesSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def assert_valid_relevant_sources_result(self, fig, table):
        valid_sources = self.standardized_df["SO"].dropna()
        valid_sources = valid_sources[valid_sources.astype(str).str.strip() != ""]

        self.assertEqual(list(table.columns), ["Sources", "N. of Documents"])
        self.assertFalse(table.empty)
        self.assertEqual(int(table["N. of Documents"].sum()), len(valid_sources))
        self.assertTrue(table["N. of Documents"].is_monotonic_decreasing)
        self.assertGreater(len(fig.data), 0)

    def test_accepts_plain_standardized_dataframe(self):
        fig, table = get_relevant_sources(self.standardized_df, num_of_sources=10)
        self.assert_valid_relevant_sources_result(fig, table)

    def test_accepts_shiny_like_dataframe_wrapper(self):
        fig, table = get_relevant_sources(DataFrameBox(self.standardized_df), num_of_sources=10)
        self.assert_valid_relevant_sources_result(fig, table)


class RelevantAuthorsSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def assert_valid_relevant_authors_result(self, fig, table):
        valid_authors = [
            author
            for authors in self.standardized_df["AU"]
            if isinstance(authors, list)
            for author in authors
            if author
        ]

        self.assertEqual(list(table.columns), ["Authors", "N. of Documents"])
        self.assertFalse(table.empty)
        self.assertEqual(int(table["N. of Documents"].sum()), len(valid_authors))
        self.assertTrue(table["N. of Documents"].is_monotonic_decreasing)
        self.assertGreater(len(fig.data), 0)

    def test_accepts_plain_standardized_dataframe(self):
        fig, table = get_relevant_authors(
            self.standardized_df,
            num_of_authors=10,
            frequency="n_docs",
        )
        self.assert_valid_relevant_authors_result(fig, table)

    def test_accepts_shiny_like_dataframe_wrapper(self):
        fig, table = get_relevant_authors(
            DataFrameBox(self.standardized_df),
            num_of_authors=10,
            frequency="n_docs",
        )
        self.assert_valid_relevant_authors_result(fig, table)


class LotkaLawSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.standardized_df = load_scopus_etl_dataframe()

    def assert_valid_lotka_result(self, fig, table):
        valid_authors = [
            author
            for authors in self.standardized_df["AU"]
            if isinstance(authors, list)
            for author in authors
            if author
        ]

        self.assertEqual(list(table.columns), ["N.Articles", "N.Authors", "Freq", "Theoretical"])
        self.assertFalse(table.empty)
        self.assertTrue(table["N.Articles"].is_monotonic_increasing)
        self.assertEqual(int(table["N.Authors"].sum()), len(set(valid_authors)))
        self.assertAlmostEqual(float(table["Freq"].sum()), 1.0, places=6)
        self.assertAlmostEqual(float(table["Theoretical"].sum()), 1.0, places=6)
        self.assertGreaterEqual(len(fig.data), 2)

    def test_accepts_plain_standardized_dataframe(self):
        fig, table = get_lotka_law(self.standardized_df)
        self.assert_valid_lotka_result(fig, table)

    def test_accepts_shiny_like_dataframe_wrapper(self):
        fig, table = get_lotka_law(DataFrameBox(self.standardized_df))
        self.assert_valid_lotka_result(fig, table)


if __name__ == "__main__":
    unittest.main()
