"""
preprocess.py
-------------
Cleans and normalizes raw scraped Google Play Store reviews.

Steps:
  1. Load raw reviews CSV
  2. Remove duplicate reviews by review_id
  3. Drop rows with missing review text or rating
  4. Normalize dates to YYYY-MM-DD format
  5. Standardize column names and bank labels
  6. Save cleaned dataset as reviews_clean.csv

Author: Omega Consultancy Data Team
Date: 2026-05-18
"""

import logging
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW_CSV = DATA_DIR / "reviews_raw.csv"
CLEAN_CSV = DATA_DIR / "reviews_clean.csv"


# ---------------------------------------------------------------------------
# Preprocessing Functions
# ---------------------------------------------------------------------------

def load_raw_data(path: Path) -> pd.DataFrame:
    """
    Loads the raw reviews CSV.

    Args:
        path: Path to the raw CSV file.

    Returns:
        DataFrame with raw review data.

    Raises:
        FileNotFoundError: If the raw CSV does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Raw CSV not found at {path}. "
            "Please run scripts/scrape_reviews.py first."
        )
    df = pd.read_csv(path, encoding="utf-8")
    logger.info(f"Loaded {len(df)} raw reviews from {path}")
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes duplicate reviews based on review_id.

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with duplicates removed.
    """
    original_count = len(df)
    df = df.drop_duplicates(subset=["review_id"], keep="first")
    removed = original_count - len(df)
    logger.info(f"Removed {removed} duplicate reviews. Remaining: {len(df)}")
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drops rows with missing review text or rating.
    Documents missing value counts before dropping.

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with missing-value rows removed.
    """
    # Document missing value counts
    missing_counts = df[["review", "rating"]].isnull().sum()
    logger.info(f"Missing values before cleaning:\n{missing_counts.to_string()}")

    original_count = len(df)
    # Drop rows missing critical columns
    df = df.dropna(subset=["review", "rating"])
    # Drop reviews shorter than 3 characters (e.g. "ok", "gd") to remove noise
    df = df[df["review"].astype(str).str.strip().str.len() >= 3]

    removed = original_count - len(df)
    missing_pct = (removed / original_count * 100) if original_count > 0 else 0
    logger.info(
        f"Dropped {removed} rows with missing review/rating "
        f"({missing_pct:.1f}% of total). Remaining: {len(df)}"
    )
    return df


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizes the date column to YYYY-MM-DD string format.

    Args:
        df: Input DataFrame (must contain 'date' column).

    Returns:
        DataFrame with normalized date strings.
    """
    # Convert to datetime, handling multiple possible formats
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True)

    # Count failed conversions
    null_dates = df["date"].isnull().sum()
    if null_dates > 0:
        logger.warning(f"{null_dates} dates could not be parsed and will be NaT.")

    # Format as YYYY-MM-DD
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    logger.info("Dates normalized to YYYY-MM-DD format.")
    return df


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Selects and renames columns to the required output schema.

    Required columns: review, rating, date, bank, source

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with only the required, standardized columns.
    """
    # Ensure bank names are standardized
    bank_map = {
        "CBE": "CBE",
        "BOA": "BOA",
        "Dashen": "Dashen",
    }
    df["bank"] = df["bank"].map(bank_map).fillna(df["bank"])

    # Strip whitespaces and use regular expressions to erase trailing .0 decimals
    df["rating"] = df["rating"].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    # Convert rating to integer
    df["rating"] = pd.to_numeric(df["rating"], errors="coerce").astype("Int64")

    # Select final columns (include review_id for joining later)
    output_cols = ["review_id", "review", "rating", "date", "bank", "source"]
    available_cols = [c for c in output_cols if c in df.columns]
    df = df[available_cols].copy()

    logger.info(f"Final columns: {list(df.columns)}")
    return df


def validate_output(df: pd.DataFrame) -> None:
    """
    Validates the cleaned DataFrame meets quality KPIs.

    Args:
        df: Cleaned DataFrame.

    Raises:
        ValueError: If critical KPIs are not met.
    """
    total = len(df)
    missing_pct = df[["review", "rating"]].isnull().mean().max() * 100

    logger.info(f"\n=== Data Quality Report ===")
    logger.info(f"Total clean reviews: {total}")
    logger.info(f"Missing data: {missing_pct:.2f}%")

    for bank, group in df.groupby("bank"):
        logger.info(f"  {bank}: {len(group)} reviews | "
                    f"Avg rating: {group['rating'].mean():.2f}")

    # KPI checks
    if total < 1200:
        logger.warning(
            f"Total reviews ({total}) below target of 1,200. "
            "Consider expanding scrape date range."
        )
    if missing_pct >= 5.0:
        raise ValueError(
            f"Missing data rate {missing_pct:.1f}% exceeds 5% KPI threshold."
        )
    if total >= 1200 and missing_pct < 5.0:
        logger.info("✓ All KPIs met.")


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main preprocessing workflow."""
    logger.info("=" * 60)
    logger.info("Omega Consultancy — Review Preprocessing Pipeline")
    logger.info("=" * 60)

    # Step 1: Load raw data
    df = load_raw_data(RAW_CSV)

    # Step 2: Remove duplicates
    df = remove_duplicates(df)

    # Step 3: Handle missing values
    df = handle_missing_values(df)

    # Step 4: Normalize dates
    df = normalize_dates(df)

    # Step 5: Standardize columns
    df = standardize_columns(df)

    # Step 6: Validate output
    validate_output(df)

    # Step 7: Save clean CSV
    df.to_csv(CLEAN_CSV, index=False, encoding="utf-8")
    logger.info(f"\nClean dataset saved: {CLEAN_CSV}")
    logger.info(f"Total records: {len(df)}")

    return df


if __name__ == "__main__":
    main()
