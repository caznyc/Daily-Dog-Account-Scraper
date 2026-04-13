"""Configuration for TikTok Dog Account Scraper."""

SEARCH_KEYWORDS = [
    "dog compilation",
    "funny dogs",
    "cute dogs daily",
    "dog reposts",
    "dog moments",
    "dogs of tiktok",
    "puppy compilation",
    "dog fails",
    "dog videos daily",
    "best dog clips",
]

# How many accounts to collect per keyword search
ACCOUNTS_PER_KEYWORD = 10

# How many videos to sample for average views calculation
VIDEOS_TO_SAMPLE = 10

# Scoring weights
SCORING_WEIGHTS = {
    "follower_video_ratio": 0.30,
    "virality_rate": 0.30,
    "growth_speed": 0.25,
    "posting_frequency": 0.15,
}

# High-priority thresholds
HIGH_PRIORITY_MIN_FOLLOWERS = 50_000
HIGH_PRIORITY_MAX_AGE_MONTHS = 6

# Browser settings
HEADLESS = True
SLOW_MO = 500  # ms between actions to avoid detection
PAGE_TIMEOUT = 30_000  # ms
NAV_TIMEOUT = 45_000  # ms

# Output paths
OUTPUT_CSV = "output/dog_accounts_ranked.csv"
OUTPUT_HTML = "output/dashboard.html"
