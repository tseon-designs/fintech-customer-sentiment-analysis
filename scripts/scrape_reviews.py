"""
scrape_reviews.py
-----------------
Scrapes Google Play Store reviews for three Ethiopian banks:
  - Commercial Bank of Ethiopia (CBE)
  - Bank of Abyssinia (BOA)
  - Dashen Bank

Uses the `google-play-scraper` library to collect reviews, ratings,
dates, and app names. Saves raw data as JSON per bank and a combined
raw CSV file.

Author: Omega Consultancy Data Team
Date: 2026-05-18
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from google_play_scraper import reviews, Sort

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Bank app IDs on Google Play Store
BANK_APPS = {
    "CBE": {
        "app_id": "com.combanketh.mobilebanking",
        "app_name": "CBE Mobile Banking",
    },
    "BOA": {
        "app_id": "com.boa.boaMobileBanking",
        "app_name": "Bank of Abyssinia Mobile Banking",
    },
    "Dashen": {
        "app_id": "com.dashen.dashensuperapp",
        "app_name": "Dashen Bank Super App",
    },
}

# Target minimum reviews per bank
MIN_REVIEWS_PER_BANK = 400

# Output directory
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Scraping Functions
# ---------------------------------------------------------------------------

def scrape_bank_reviews(bank_name: str, app_id: str, min_count: int = 400) -> list[dict]:
    """
    Scrapes reviews for a single bank app from the Google Play Store.

    Args:
        bank_name: Human-readable bank identifier (e.g., 'CBE').
        app_id: Google Play Store application ID.
        min_count: Minimum number of reviews to collect.

    Returns:
        List of review dictionaries with standardized fields.
    """
    all_reviews = []
    continuation_token = None
    batch_size = 200  # Max per request

    logger.info(f"Starting scrape for {bank_name} (app_id={app_id})")

    while len(all_reviews) < min_count:
        try:
            result, continuation_token = reviews(
                app_id,
                lang="en",
                country="et",
                sort=Sort.NEWEST,
                count=batch_size,
                continuation_token=continuation_token,
            )

            if not result:
                logger.warning(
                    f"{bank_name}: No more reviews returned. "
                    f"Collected {len(all_reviews)} total."
                )
                break

            for r in result:
                all_reviews.append({
                    "review_id": r.get("reviewId", ""),
                    "review": r.get("content", ""),
                    "rating": r.get("score", None),
                    "date": r.get("at", None),
                    "bank": bank_name,
                    "app_name": BANK_APPS[bank_name]["app_name"],
                    "source": "Google Play",
                    "thumbs_up": r.get("thumbsUpCount", 0),
                })

            logger.info(
                f"{bank_name}: Collected {len(all_reviews)} reviews so far..."
            )

            # Respect rate limits
            time.sleep(1.5)

            # Stop if no more pages
            if continuation_token is None:
                logger.info(f"{bank_name}: Reached end of available reviews.")
                break

        except Exception as e:
            logger.error(f"{bank_name}: Error during scraping — {e}")
            time.sleep(5)  # Back off on error
            break

    logger.info(
        f"{bank_name}: Finished. Total reviews collected: {len(all_reviews)}"
    )
    return all_reviews


def scrape_all_banks() -> pd.DataFrame:
    """
    Scrapes reviews for all configured bank apps and combines into a DataFrame.

    Returns:
        Combined DataFrame with all reviews.
    """
    all_data = []

    for bank_name, bank_info in BANK_APPS.items():
        bank_reviews_list = scrape_bank_reviews(
            bank_name=bank_name,
            app_id=bank_info["app_id"],
            min_count=MIN_REVIEWS_PER_BANK,
        )

        if len(bank_reviews_list) < MIN_REVIEWS_PER_BANK:
            logger.warning(
                f"{bank_name}: Only {len(bank_reviews_list)} reviews collected. "
                f"Target was {MIN_REVIEWS_PER_BANK}. "
                "Consider expanding date range or checking app availability."
            )

        # Save per-bank raw JSON
        json_path = DATA_DIR / f"{bank_name.lower()}_reviews_raw.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(bank_reviews_list, f, ensure_ascii=False, indent=2, default=str)
        logger.info(f"Saved raw JSON: {json_path}")

        all_data.extend(bank_reviews_list)

    df = pd.DataFrame(all_data)
    logger.info(f"Total reviews collected across all banks: {len(df)}")
    return df


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main scraping workflow."""
    logger.info("=" * 60)
    logger.info("Omega Consultancy — Play Store Review Scraper")
    logger.info("=" * 60)

    # Scrape all banks
    df = scrape_all_banks()

    # Save combined raw CSV
    raw_csv_path = DATA_DIR / "reviews_raw.csv"
    df.to_csv(raw_csv_path, index=False, encoding="utf-8")
    logger.info(f"Raw combined CSV saved: {raw_csv_path}")

    # Summary stats
    logger.info("\n=== Scraping Summary ===")
    summary = df.groupby("bank").agg(
        total_reviews=("review_id", "count"),
        avg_rating=("rating", "mean"),
        date_min=("date", "min"),
        date_max=("date", "max"),
    )
    print(summary.to_string())

    return df


if __name__ == "__main__":
    main()
