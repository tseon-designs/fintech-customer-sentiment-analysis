"""
test_preprocessing.py
---------------------
Unit tests for the preprocessing pipeline.

Tests:
  - Duplicate removal
  - Missing value handling
  - Date normalization
  - Column standardization
  - Data quality validation

Author: Omega Consultancy Data Team
Date: 2026-05-18
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from preprocess import (
    remove_duplicates,
    handle_missing_values,
    normalize_dates,
    standardize_columns,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_df():
    """Returns a sample raw reviews DataFrame for testing."""
    return pd.DataFrame({
        "review_id": ["r1", "r2", "r2", "r3", "r4"],
        "review": [
            "Great app!",
            "Very slow transfers",
            "Very slow transfers",  # duplicate
            None,                   # missing review
            "Login issues all the time",
        ],
        "rating": [5, 2, 2, 4, None],  # r4 has missing rating
        "date": [
            "2024-01-15 10:00:00+00:00",
            "2024-02-20 08:30:00+00:00",
            "2024-02-20 08:30:00+00:00",
            "2024-03-01 00:00:00+00:00",
            "2024-04-10 12:00:00+00:00",
        ],
        "bank": ["CBE", "BOA", "BOA", "Dashen", "CBE"],
        "source": ["Google Play"] * 5,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRemoveDuplicates:
    def test_removes_exact_duplicates(self, sample_df):
        """Duplicate review IDs should be reduced to one."""
        result = remove_duplicates(sample_df)
        assert len(result) == 4  # r2 duplicated → 4 unique

    def test_keeps_unique_reviews(self, sample_df):
        """All unique review IDs should remain."""
        result = remove_duplicates(sample_df)
        assert result["review_id"].nunique() == 4


class TestHandleMissingValues:
    def test_drops_missing_review_text(self, sample_df):
        """Rows with null review text should be dropped."""
        df_dedup = remove_duplicates(sample_df)
        result = handle_missing_values(df_dedup)
        assert result["review"].isnull().sum() == 0

    def test_drops_missing_rating(self, sample_df):
        """Rows with null rating should be dropped."""
        df_dedup = remove_duplicates(sample_df)
        result = handle_missing_values(df_dedup)
        assert result["rating"].isnull().sum() == 0

    def test_correct_row_count_after_cleaning(self, sample_df):
        """Should retain only valid rows (r1, r2, r3 — r3 has null review, r4 null rating)."""
        df_dedup = remove_duplicates(sample_df)
        result = handle_missing_values(df_dedup)
        # After dedup: r1, r2, r3(null review), r4(null rating) → 2 valid
        assert len(result) == 2


class TestNormalizeDates:
    def test_dates_are_formatted_correctly(self, sample_df):
        """All parseable dates should be YYYY-MM-DD."""
        df_dedup = remove_duplicates(sample_df)
        df_clean = handle_missing_values(df_dedup)
        result = normalize_dates(df_clean)
        # Check all non-null dates match YYYY-MM-DD pattern
        import re
        pattern = r"^\d{4}-\d{2}-\d{2}$"
        valid_dates = result["date"].dropna()
        assert all(re.match(pattern, d) for d in valid_dates)

    def test_date_column_is_string(self, sample_df):
        """Date column should be string after normalization."""
        df_dedup = remove_duplicates(sample_df)
        df_clean = handle_missing_values(df_dedup)
        result = normalize_dates(df_clean)
        assert result["date"].dtype == object  # object = string in pandas


class TestStandardizeColumns:
    def test_required_columns_present(self, sample_df):
        """Output DataFrame must contain all required columns."""
        df_dedup = remove_duplicates(sample_df)
        df_clean = handle_missing_values(df_dedup)
        df_dated = normalize_dates(df_clean)
        result = standardize_columns(df_dated)
        required = {"review", "rating", "date", "bank", "source"}
        assert required.issubset(set(result.columns))

    def test_bank_names_standardized(self, sample_df):
        """Bank names should map to CBE, BOA, or Dashen only."""
        df_dedup = remove_duplicates(sample_df)
        df_clean = handle_missing_values(df_dedup)
        df_dated = normalize_dates(df_clean)
        result = standardize_columns(df_dated)
        valid_banks = {"CBE", "BOA", "Dashen"}
        assert set(result["bank"].unique()).issubset(valid_banks)
