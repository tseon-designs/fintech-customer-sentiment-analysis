"""
db_insert.py
------------
Connects to a local PostgreSQL database (bank_reviews) and inserts
the cleaned and analyzed review data.

Requires:
  - PostgreSQL running locally
  - Database 'bank_reviews' created
  - Schema applied via: psql -U postgres -f scripts/schema.sql
  - .env file with DB credentials (see README)

Author: Omega Consultancy Data Team
Date: 2026-05-18
"""

import logging
import os
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

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
# Configuration
# ---------------------------------------------------------------------------

# Load environment variables from .env file
load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 5432)),
    "dbname":   os.getenv("DB_NAME", "bank_reviews"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
SENTIMENT_CSV = DATA_DIR / "reviews_with_sentiment.csv"


# ---------------------------------------------------------------------------
# Database Connection
# ---------------------------------------------------------------------------

def get_connection():
    """
    Creates and returns a psycopg2 database connection.

    Returns:
        psycopg2 connection object.

    Raises:
        psycopg2.OperationalError: If connection fails.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        logger.info(
            f"Connected to PostgreSQL: {DB_CONFIG['dbname']}@"
            f"{DB_CONFIG['host']}:{DB_CONFIG['port']}"
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        raise


# ---------------------------------------------------------------------------
# Bank ID Lookup
# ---------------------------------------------------------------------------

def get_bank_id_map(conn) -> dict:
    """
    Fetches the bank_id mapping from the banks table.

    Args:
        conn: Active psycopg2 connection.

    Returns:
        Dict mapping bank_name -> bank_id (e.g., {'CBE': 1, 'BOA': 2, ...}).
    """
    with conn.cursor() as cur:
        cur.execute("SELECT bank_name, bank_id FROM banks;")
        rows = cur.fetchall()
    bank_map = {row[0]: row[1] for row in rows}
    logger.info(f"Bank ID map: {bank_map}")
    return bank_map


# ---------------------------------------------------------------------------
# Data Insertion
# ---------------------------------------------------------------------------

def insert_reviews(conn, df: pd.DataFrame, bank_map: dict) -> int:
    """
    Inserts review records into the reviews table using batch inserts.

    Uses execute_values for efficient bulk insertion.
    Skips reviews with unknown bank names or missing text/rating.

    Args:
        conn: Active psycopg2 connection.
        df: DataFrame with sentiment and theme columns.
        bank_map: Dict mapping bank_name -> bank_id.

    Returns:
        Number of rows successfully inserted.
    """
    records = []
    skipped = 0

    for _, row in df.iterrows():
        bank_id = bank_map.get(row.get("bank"))
        if bank_id is None:
            skipped += 1
            continue

        review_text = str(row.get("review", "")).strip()
        rating = row.get("rating")
        if not review_text or pd.isna(rating):
            skipped += 1
            continue

        records.append((
            bank_id,
            review_text,
            int(rating),
            row.get("date") if pd.notna(row.get("date")) else None,
            row.get("sentiment_label") if pd.notna(row.get("sentiment_label")) else None,
            float(row.get("sentiment_score")) if pd.notna(row.get("sentiment_score")) else None,
            row.get("identified_theme") if pd.notna(row.get("identified_theme")) else None,
            "Google Play",
            str(row.get("review_id", "")) or None,
        ))

    if skipped > 0:
        logger.warning(f"Skipped {skipped} rows (missing bank/review/rating).")

    if not records:
        logger.warning("No valid records to insert.")
        return 0

    insert_sql = """
        INSERT INTO reviews (
            bank_id, review_text, rating, review_date,
            sentiment_label, sentiment_score, identified_theme,
            source, raw_review_id
        ) VALUES %s
        ON CONFLICT (raw_review_id) DO NOTHING;
    """

    try:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, records, page_size=200)
        conn.commit()
        logger.info(f"Successfully inserted {len(records)} reviews.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Insertion failed: {e}")
        raise

    return len(records)


# ---------------------------------------------------------------------------
# Verification Queries
# ---------------------------------------------------------------------------

def run_verification_queries(conn) -> None:
    """
    Runs data integrity verification queries and logs results.

    Checks:
      1. Total reviews per bank
      2. Average rating per bank
      3. Null counts in key columns
      4. Sentiment distribution per bank

    Args:
        conn: Active psycopg2 connection.
    """
    logger.info("\n=== Verification Queries ===")

    queries = {
        "Reviews per bank": """
            SELECT b.bank_name, COUNT(r.review_id) AS total_reviews
            FROM reviews r
            JOIN banks b ON r.bank_id = b.bank_id
            GROUP BY b.bank_name
            ORDER BY b.bank_name;
        """,
        "Average rating per bank": """
            SELECT b.bank_name, ROUND(AVG(r.rating)::numeric, 2) AS avg_rating
            FROM reviews r
            JOIN banks b ON r.bank_id = b.bank_id
            GROUP BY b.bank_name
            ORDER BY b.bank_name;
        """,
        "Null checks": """
            SELECT
                COUNT(*) FILTER (WHERE review_text IS NULL)     AS null_texts,
                COUNT(*) FILTER (WHERE rating IS NULL)          AS null_ratings,
                COUNT(*) FILTER (WHERE sentiment_label IS NULL) AS null_sentiments,
                COUNT(*) FILTER (WHERE identified_theme IS NULL) AS null_themes
            FROM reviews;
        """,
        "Sentiment distribution": """
            SELECT b.bank_name, r.sentiment_label, COUNT(*) AS count
            FROM reviews r
            JOIN banks b ON r.bank_id = b.bank_id
            GROUP BY b.bank_name, r.sentiment_label
            ORDER BY b.bank_name, r.sentiment_label;
        """,
    }

    with conn.cursor() as cur:
        for query_name, sql in queries.items():
            logger.info(f"\n-- {query_name} --")
            cur.execute(sql)
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]
            result_df = pd.DataFrame(rows, columns=col_names)
            print(result_df.to_string(index=False))


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main database insertion workflow."""
    logger.info("=" * 60)
    logger.info("Omega Consultancy — PostgreSQL Data Insertion")
    logger.info("=" * 60)

    # Step 1: Load analyzed data
    if not SENTIMENT_CSV.exists():
        raise FileNotFoundError(
            f"Sentiment CSV not found at {SENTIMENT_CSV}. "
            "Please run scripts/analyze_sentiment.py first."
        )
    df = pd.read_csv(SENTIMENT_CSV, encoding="utf-8")
    logger.info(f"Loaded {len(df)} reviews for insertion.")

    # Step 2: Connect to database
    conn = get_connection()

    try:
        # Step 3: Get bank ID mapping
        bank_map = get_bank_id_map(conn)

        # Step 4: Insert reviews
        inserted_count = insert_reviews(conn, df, bank_map)
        logger.info(f"\nTotal rows inserted: {inserted_count}")

        # Step 5: Verify data integrity
        run_verification_queries(conn)

    finally:
        conn.close()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    main()
