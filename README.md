# Fintech Review Analytics

A rigorous analytics pipeline that transforms raw Google Play Store reviews for Ethiopian banks into actionable business intelligence. Built for **Omega Consultancy** as part of a customer experience analytics engagement.

## Banks Analyzed
| Bank | App Name | Play Store App ID |
|------|----------|-------------------|
| Commercial Bank of Ethiopia (CBE) | CBE Birr | com.combanketh.mobilebanking |
| Bank of Abyssinia (BOA) | Abyssinia Mobile Banking | com.bankofabyssinia.mobile |
| Dashen Bank | Amole by Dashen Bank | com.dashen.amole |

---

## Project Structure
```
fintech-review-analytics/
├── .github/workflows/unittests.yml   # CI/CD pipeline
├── data/raw/                         # Raw scraped data (git-ignored)
├── notebooks/                        # Jupyter notebooks for analysis
├── scripts/
│   ├── scrape_reviews.py             # Google Play Store scraper
│   ├── preprocess.py                 # Data cleaning pipeline
│   ├── analyze_sentiment.py          # DistilBERT sentiment + TF-IDF themes
│   ├── db_insert.py                  # PostgreSQL data insertion
│   └── schema.sql                    # Database schema DDL
├── src/                              # Reusable utility modules
├── tests/                            # Unit tests (pytest)
├── requirements.txt
└── README.md
```

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/fintech-review-analytics.git
cd fintech-review-analytics
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 4. Configure Environment Variables
Create a `.env` file (this file is git-ignored):
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=bank_reviews
DB_USER=postgres
DB_PASSWORD=your_password
```

---

## Task 1: Data Collection & Preprocessing

### Scraping Methodology
Reviews are collected using the `google-play-scraper` Python library, which interfaces with the public Google Play Store data endpoint. No authentication or API key is required.

**Target Apps & IDs:**
- CBE: `com.combanketh.mobilebanking`
- BOA: `com.bankofabyssinia.mobile`
- Dashen: `com.dashen.amole`

**Data Collected per Review:**
- `review`: Full review text
- `rating`: 1–5 star rating
- `date`: Review posting date (normalized to YYYY-MM-DD)
- `bank`: Bank name identifier
- `source`: Always "Google Play"

**Date Range:** Up to 24 months of reviews collected using continuation tokens. The scraper requests 400+ reviews per bank using `count` and `continuation_token` pagination.

**Preprocessing Steps:**
1. Removed duplicate reviews by `reviewId`
2. Dropped rows with missing `review` text or `rating`
3. Normalized `at` timestamp to `YYYY-MM-DD` date string
4. Standardized `bank` name to one of: `CBE`, `BOA`, `Dashen`

**Limitations:**
- Google Play API is unofficial; rate limiting may apply
- English-language reviews dominate; Amharic reviews are present but not translated
- Review count depends on Play Store availability (documented per run)

### Run Scraper
```bash
python scripts/scrape_reviews.py
```

### Run Preprocessing
```bash
python scripts/preprocess.py
```

Output: `data/raw/reviews_clean.csv`

---

## Task 2: Sentiment & Thematic Analysis

**Model:** `distilbert-base-uncased-finetuned-sst-2-english` (Hugging Face Transformers)

**Rationale:** DistilBERT offers a strong balance between speed and accuracy for binary/ternary sentiment classification. It significantly outperforms lexicon-based methods (VADER, TextBlob) on short, informal text like app reviews.

**Themes Identified:** Account Access Issues, Transaction Performance, UI & Design, Customer Support, Feature Requests

```bash
python scripts/analyze_sentiment.py
```

Output: `data/raw/reviews_with_sentiment.csv`

---

## Task 3: PostgreSQL Database

```bash
# Create database and tables
psql -U postgres -f scripts/schema.sql

# Insert data
python scripts/db_insert.py
```

Schema: `banks` table (bank_id, bank_name, app_name) + `reviews` table (FK to banks)

---

## Task 4: Insights & Recommendations

See `notebooks/insights_and_visualizations.ipynb` and the Final Report in `reports/`.

---

## CI/CD
GitHub Actions runs on every push to `main`, `task-*` branches:
- Installs all dependencies from `requirements.txt`
- Runs `pytest tests/`

---

## License
MIT License — for academic and consulting use.
