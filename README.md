# TikTok Dog Account Growth Intelligence Scraper

Scrapes TikTok for dog content repost accounts using Playwright (headless browser), analyzes their growth patterns, and outputs a ranked CSV + interactive HTML dashboard.

## What It Does

1. **Searches TikTok** using 10 dog-related keywords to discover accounts
2. **Scrapes each profile** — followers, likes, video count, views, bio, posting patterns
3. **Classifies content** — reposts/compilations vs. original vs. mixed
4. **Scores & ranks** accounts by growth potential using weighted metrics
5. **Flags high-priority** accounts (50k+ followers, under 6 months old)
6. **Outputs** a ranked CSV and an interactive HTML dashboard

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Usage

```bash
# Run with defaults (10 keywords, headless)
python main.py

# Custom keywords
python main.py --keywords "funny dogs" "dog fails" "puppy moments"

# Visible browser (useful for debugging CAPTCHAs)
python main.py --headless false

# Limit accounts per keyword
python main.py --max-accounts 5

# Verbose logging
python main.py -v
```

## Output

Results go to `output/`:
- **`dog_accounts_ranked.csv`** — Full data, ranked by composite score
- **`dashboard.html`** — Interactive HTML dashboard with sorting, filtering, and search

## Scoring System

Each account is scored on a 0–100 composite scale:

| Metric | Weight | What It Measures |
|--------|--------|------------------|
| Follower/Video Ratio | 30% | High followers + low video count = fast growth |
| Virality Rate | 30% | Avg views / followers — how far content reaches |
| Growth Speed | 25% | Followers / account age in months |
| Posting Frequency | 15% | Consistency of posting schedule |

Accounts under 6 months old with 50k+ followers are flagged as **HIGH PRIORITY**.

## Configuration

Edit `config.py` to customize:
- Search keywords
- Accounts per keyword
- Scoring weights
- High-priority thresholds
- Browser settings (headless, timeouts, delays)

## Dashboard Features

- Sortable columns (click any header)
- Filter by content style (Reposts, Original, Mixed)
- Filter by priority level
- Full-text search across usernames, bios, and signals
- Score breakdown bars
- Direct links to TikTok profiles

## Important Notes

- TikTok actively blocks scrapers. If you get empty results, try `--headless false` to handle CAPTCHAs manually.
- Add delays between runs to avoid rate limiting. The default `SLOW_MO` in config adds 500ms between actions.
- This tool is for **research purposes only**. Respect TikTok's Terms of Service.
- Scraped data is approximate — view counts and follower numbers change constantly.
