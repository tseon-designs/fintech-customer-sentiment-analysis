-- ============================================================
-- schema.sql
-- Database: bank_reviews
-- Description: Schema for storing Ethiopian bank mobile app
--              reviews scraped from Google Play Store.
--
-- Author: Omega Consultancy Data Team
-- Date:   2026-05-18
-- ============================================================

-- Drop tables if they exist (for re-runs)
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS banks CASCADE;

-- ============================================================
-- Table: banks
-- Stores metadata about each bank and its mobile app.
-- ============================================================
CREATE TABLE banks (
    bank_id     SERIAL PRIMARY KEY,
    bank_name   VARCHAR(100) NOT NULL UNIQUE,
    app_name    VARCHAR(200) NOT NULL,
    app_id      VARCHAR(200),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Table: reviews
-- Stores scraped and processed review data.
-- ============================================================
CREATE TABLE reviews (
    review_id        SERIAL PRIMARY KEY,
    bank_id          INTEGER NOT NULL REFERENCES banks(bank_id) ON DELETE CASCADE,
    review_text      TEXT,
    rating           SMALLINT CHECK (rating BETWEEN 1 AND 5),
    review_date      DATE,
    sentiment_label  VARCHAR(20) CHECK (sentiment_label IN ('positive', 'negative', 'neutral')),
    sentiment_score  NUMERIC(6, 4) CHECK (sentiment_score BETWEEN 0 AND 1),
    identified_theme VARCHAR(100),
    source           VARCHAR(50) DEFAULT 'Google Play',
    raw_review_id    VARCHAR(200) UNIQUE,  -- Original Play Store review ID
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- Indexes for query performance
-- ============================================================
CREATE INDEX idx_reviews_bank_id       ON reviews(bank_id);
CREATE INDEX idx_reviews_rating        ON reviews(rating);
CREATE INDEX idx_reviews_sentiment     ON reviews(sentiment_label);
CREATE INDEX idx_reviews_theme         ON reviews(identified_theme);
CREATE INDEX idx_reviews_date          ON reviews(review_date);

-- ============================================================
-- Seed: Insert bank metadata
-- ============================================================
INSERT INTO banks (bank_name, app_name, app_id) VALUES
    ('CBE',    'CBE Mobile Banking',                  'com.combanketh.mobilebanking'),
    ('BOA',    'Bank of Abyssinia Mobile Banking',    'com.boa.boaMobileBanking'),
    ('Dashen', 'Dashen Bank Super App',               'com.dashen.dashensuperapp');

-- ============================================================
-- Verification Queries
-- ============================================================

-- Count reviews per bank
-- SELECT b.bank_name, COUNT(r.review_id) AS total_reviews
-- FROM reviews r
-- JOIN banks b ON r.bank_id = b.bank_id
-- GROUP BY b.bank_name;

-- Average rating per bank
-- SELECT b.bank_name, ROUND(AVG(r.rating), 2) AS avg_rating
-- FROM reviews r
-- JOIN banks b ON r.bank_id = b.bank_id
-- GROUP BY b.bank_name;

-- Null check on key columns
-- SELECT
--     COUNT(*) FILTER (WHERE review_text IS NULL) AS null_texts,
--     COUNT(*) FILTER (WHERE rating IS NULL)      AS null_ratings,
--     COUNT(*) FILTER (WHERE sentiment_label IS NULL) AS null_sentiments
-- FROM reviews;

-- Sentiment distribution per bank
-- SELECT b.bank_name, r.sentiment_label, COUNT(*) AS count
-- FROM reviews r
-- JOIN banks b ON r.bank_id = b.bank_id
-- GROUP BY b.bank_name, r.sentiment_label
-- ORDER BY b.bank_name, r.sentiment_label;
