"""
analyze_sentiment.py
---------------------
Performs sentiment analysis and thematic analysis on cleaned reviews.

Sentiment Analysis:
  - Uses distilbert-base-uncased-finetuned-sst-2-english (Hugging Face)
  - Classifies each review as POSITIVE, NEGATIVE, or NEUTRAL
  - Produces a confidence score (0.0 – 1.0)
  - Rationale: DistilBERT outperforms lexicon-based methods (VADER, TextBlob)
    on short, informal, domain-specific text like mobile app reviews.

Thematic Analysis:
  - Extracts top n-grams per bank using TF-IDF (sklearn)
  - Maps keywords to 5 predefined business themes:
      1. Account Access Issues
      2. Transaction Performance
      3. UI & Design
      4. Customer Support
      5. Feature Requests
  - Falls back to "General Feedback" if no theme matches

Author: Omega Consultancy Data Team
Date: 2026-05-18
"""

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from transformers import pipeline

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
# Paths & Constants
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
CLEAN_CSV = DATA_DIR / "reviews_clean.csv"
SENTIMENT_CSV = DATA_DIR / "reviews_with_sentiment.csv"

# DistilBERT model for sentiment classification
SENTIMENT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"

# Batch size for transformer inference (reduce if OOM)
BATCH_SIZE = 32

# Maximum token length the model can handle
MAX_TOKEN_LENGTH = 512

# ---------------------------------------------------------------------------
# Theme Keyword Mapping
# ---------------------------------------------------------------------------

# Each theme is defined by a set of keywords/phrases.
# Reviews are matched to the first theme whose keywords appear in the text.
THEME_KEYWORDS = {
    "Account Access Issues": [
        "login", "log in", "password", "otp", "one time password",
        "pin", "fingerprint", "biometric", "locked", "lock", "unlock",
        "account", "access", "sign in", "authentication", "verify",
        "verification", "not working", "cannot login", "can't login",
        "session", "expired", "blocked", "suspended",
    ],
    "Transaction Performance": [
        "transfer", "transaction", "slow", "fast", "speed", "loading",
        "delay", "delayed", "pending", "failed", "failure", "timeout",
        "freeze", "frozen", "crash", "crashes", "error", "hung",
        "payment", "send money", "receive money", "balance", "withdraw",
        "deposit", "processing", "stuck",
    ],
    "UI & Design": [
        "ui", "interface", "design", "layout", "navigation", "menu",
        "look", "beautiful", "ugly", "confusing", "easy to use",
        "user friendly", "user experience", "ux", "button", "screen",
        "dark mode", "update", "updated", "new version", "version",
        "simple", "clean", "modern", "outdated",
    ],
    "Customer Support": [
        "support", "customer service", "helpline", "call center", "agent",
        "response", "reply", "feedback", "complaint", "complain",
        "contact", "help", "assist", "assistance", "resolve", "resolved",
        "ignored", "no response", "waiting", "wait",
    ],
    "Feature Requests": [
        "feature", "add", "wish", "want", "need", "request", "please add",
        "would like", "budget", "budgeting", "notification", "statement",
        "qr", "qr code", "schedule", "recurring", "loan", "saving",
        "investment", "currency", "exchange", "more options",
    ],
}


# ---------------------------------------------------------------------------
# Sentiment Analysis
# ---------------------------------------------------------------------------

def load_sentiment_model() -> pipeline:
    """
    Loads the DistilBERT sentiment classification pipeline.

    Returns:
        Hugging Face text-classification pipeline.
    """
    logger.info(f"Loading sentiment model: {SENTIMENT_MODEL}")
    clf = pipeline(
        "text-classification",
        model=SENTIMENT_MODEL,
        truncation=True,
        max_length=MAX_TOKEN_LENGTH,
        device=-1,  # Use CPU; set to 0 for GPU
    )
    logger.info("Sentiment model loaded successfully.")
    return clf


def classify_label(label: str, score: float) -> str:
    """
    Maps DistilBERT binary labels to ternary sentiment.

    DistilBERT only predicts POSITIVE/NEGATIVE. We add a NEUTRAL
    category for low-confidence predictions (score < 0.65).

    Args:
        label: Raw model label ('POSITIVE' or 'NEGATIVE').
        score: Confidence score (0.0 – 1.0).

    Returns:
        Final label: 'positive', 'negative', or 'neutral'.
    """
    if score < 0.65:
        return "neutral"
    return label.lower()


def run_sentiment_analysis(
    df: pd.DataFrame, clf: pipeline
) -> pd.DataFrame:
    """
    Runs sentiment classification on all reviews in batches.

    Args:
        df: DataFrame with 'review' column.
        clf: Hugging Face classification pipeline.

    Returns:
        DataFrame with 'sentiment_label' and 'sentiment_score' columns added.
    """
    texts = df["review"].astype(str).tolist()
    labels = []
    scores = []

    logger.info(f"Running sentiment analysis on {len(texts)} reviews...")

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i: i + BATCH_SIZE]
        try:
            results = clf(batch)
            for r in results:
                raw_label = r["label"]
                raw_score = r["score"]
                labels.append(classify_label(raw_label, raw_score))
                scores.append(round(raw_score, 4))
        except Exception as e:
            logger.error(f"Batch {i//BATCH_SIZE} failed: {e}")
            # Fill with neutral on error
            labels.extend(["neutral"] * len(batch))
            scores.extend([0.5] * len(batch))

        if (i // BATCH_SIZE) % 10 == 0:
            logger.info(f"  Processed {min(i + BATCH_SIZE, len(texts))}/{len(texts)} reviews...")

    df["sentiment_label"] = labels
    df["sentiment_score"] = scores
    logger.info("Sentiment analysis complete.")
    return df


# ---------------------------------------------------------------------------
# Thematic Analysis
# ---------------------------------------------------------------------------

def assign_theme(text: str) -> str:
    """
    Assigns a business theme to a review based on keyword matching.

    Iterates through THEME_KEYWORDS in priority order and returns
    the first matching theme. Defaults to 'General Feedback'.

    Args:
        text: Review text string.

    Returns:
        Theme name string.
    """
    text_lower = text.lower()
    for theme, keywords in THEME_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return theme
    return "General Feedback"


def extract_tfidf_keywords(
    df: pd.DataFrame, bank: str, top_n: int = 20
) -> list[str]:
    """
    Extracts top TF-IDF keywords for a specific bank's reviews.

    Args:
        df: Full reviews DataFrame.
        bank: Bank identifier (e.g., 'CBE').
        top_n: Number of top keywords to return.

    Returns:
        List of top keyword strings.
    """
    bank_texts = df[df["bank"] == bank]["review"].astype(str).tolist()
    if len(bank_texts) < 5:
        logger.warning(f"{bank}: Not enough reviews for TF-IDF.")
        return []

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
        max_features=500,
        min_df=2,
    )
    try:
        tfidf_matrix = vectorizer.fit_transform(bank_texts)
        mean_scores = np.asarray(tfidf_matrix.mean(axis=0)).flatten()
        top_indices = mean_scores.argsort()[::-1][:top_n]
        feature_names = vectorizer.get_feature_names_out()
        keywords = [feature_names[i] for i in top_indices]
        logger.info(f"{bank} TF-IDF top keywords: {keywords[:10]}")
        return keywords
    except Exception as e:
        logger.error(f"{bank}: TF-IDF extraction failed — {e}")
        return []


def run_thematic_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Assigns themes to each review and logs TF-IDF keywords per bank.

    Args:
        df: DataFrame with 'review' and 'bank' columns.

    Returns:
        DataFrame with 'identified_theme' column added.
    """
    logger.info("Running thematic analysis...")

    # Assign theme via keyword matching
    df["identified_theme"] = df["review"].apply(assign_theme)

    # Log TF-IDF keywords per bank for documentation
    for bank in df["bank"].unique():
        keywords = extract_tfidf_keywords(df, bank)
        logger.info(f"\n{bank} — Top 20 TF-IDF keywords:\n{keywords}")

    # Log theme distribution per bank
    logger.info("\n=== Theme Distribution per Bank ===")
    theme_dist = df.groupby(["bank", "identified_theme"]).size().unstack(fill_value=0)
    print(theme_dist.to_string())

    logger.info("Thematic analysis complete.")
    return df


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def main():
    """Main analysis workflow."""
    logger.info("=" * 60)
    logger.info("Omega Consultancy — Sentiment & Thematic Analysis")
    logger.info("=" * 60)

    # Step 1: Load clean data
    if not CLEAN_CSV.exists():
        raise FileNotFoundError(
            f"Clean CSV not found at {CLEAN_CSV}. "
            "Please run scripts/preprocess.py first."
        )
    df = pd.read_csv(CLEAN_CSV, encoding="utf-8")
    logger.info(f"Loaded {len(df)} clean reviews.")

    # Step 2: Sentiment analysis
    clf = load_sentiment_model()
    df = run_sentiment_analysis(df, clf)

    # Step 3: Thematic analysis
    df = run_thematic_analysis(df)

    # Step 4: Add sequential review_id for DB use
    df = df.reset_index(drop=True)
    df.insert(0, "id", range(1, len(df) + 1))

    # Step 5: Validate coverage
    sentiment_coverage = df["sentiment_label"].notna().mean() * 100
    logger.info(f"\nSentiment coverage: {sentiment_coverage:.1f}%")
    if sentiment_coverage < 90:
        logger.warning("Sentiment coverage below 90% KPI threshold!")

    # Step 6: Save results
    df.to_csv(SENTIMENT_CSV, index=False, encoding="utf-8")
    logger.info(f"\nResults saved: {SENTIMENT_CSV}")

    # Step 7: Summary
    logger.info("\n=== Sentiment Distribution per Bank ===")
    sent_dist = df.groupby(["bank", "sentiment_label"]).size().unstack(fill_value=0)
    print(sent_dist.to_string())

    logger.info("\n=== Mean Sentiment Score per Bank & Rating ===")
    score_summary = df.groupby(["bank", "rating"])["sentiment_score"].mean().round(3)
    print(score_summary.to_string())

    return df


if __name__ == "__main__":
    main()
