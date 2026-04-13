"""Scoring and ranking engine for scraped TikTok accounts."""

import logging

from scraper import AccountData
import config

logger = logging.getLogger(__name__)


def score_accounts(accounts: list[AccountData]) -> list[dict]:
    """Score and rank accounts, returning enriched dicts sorted by score descending."""
    scored = []
    weights = config.SCORING_WEIGHTS

    # Collect raw metrics for normalization
    fv_ratios = []
    virality_rates = []
    growth_speeds = []
    freq_scores_raw = []

    for a in accounts:
        fv = a.follower_count / max(a.video_count, 1)
        fv_ratios.append(fv)

        vir = a.avg_views / max(a.follower_count, 1) if a.avg_views > 0 else 0
        virality_rates.append(vir)

        if a.account_age_months > 0:
            gs = a.follower_count / a.account_age_months
        else:
            gs = 0
        growth_speeds.append(gs)

        freq = _posting_frequency_score(a.posting_frequency)
        freq_scores_raw.append(freq)

    # Normalize each metric to 0-100
    fv_norm = _normalize(fv_ratios)
    vir_norm = _normalize(virality_rates)
    gs_norm = _normalize(growth_speeds)
    freq_norm = _normalize(freq_scores_raw)

    for i, a in enumerate(accounts):
        composite = (
            fv_norm[i] * weights["follower_video_ratio"]
            + vir_norm[i] * weights["virality_rate"]
            + gs_norm[i] * weights["growth_speed"]
            + freq_norm[i] * weights["posting_frequency"]
        )

        # High-priority flag
        is_high_priority = (
            a.follower_count >= config.HIGH_PRIORITY_MIN_FOLLOWERS
            and 0 < a.account_age_months <= config.HIGH_PRIORITY_MAX_AGE_MONTHS
        )

        fv_raw = a.follower_count / max(a.video_count, 1)
        vir_raw = (a.avg_views / max(a.follower_count, 1) * 100) if a.avg_views > 0 else 0

        scored.append({
            "rank": 0,
            "username": a.username,
            "display_name": a.display_name,
            "profile_url": a.profile_url,
            "followers": a.follower_count,
            "total_likes": a.total_likes,
            "video_count": a.video_count,
            "avg_views": round(a.avg_views),
            "follower_video_ratio": round(fv_raw, 1),
            "virality_pct": round(vir_raw, 1),
            "account_age": a.account_age,
            "account_age_months": round(a.account_age_months, 1) if a.account_age_months > 0 else None,
            "growth_speed": round(growth_speeds[i], 1),
            "bio": a.bio,
            "posting_frequency": a.posting_frequency,
            "content_style": a.content_style,
            "copy_signals": a.copy_signals,
            "composite_score": round(composite, 2),
            "high_priority": is_high_priority,
            # Sub-scores for dashboard detail
            "score_fv": round(fv_norm[i], 1),
            "score_vir": round(vir_norm[i], 1),
            "score_growth": round(gs_norm[i], 1),
            "score_freq": round(freq_norm[i], 1),
        })

    # Sort by composite score descending
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Assign ranks
    for i, entry in enumerate(scored, 1):
        entry["rank"] = i

    logger.info(f"Scored and ranked {len(scored)} accounts")
    hp_count = sum(1 for s in scored if s["high_priority"])
    if hp_count:
        logger.info(f"  {hp_count} HIGH PRIORITY accounts flagged")

    return scored


def _normalize(values: list[float]) -> list[float]:
    """Min-max normalize a list of values to 0-100 range."""
    if not values:
        return []
    min_v = min(values)
    max_v = max(values)
    spread = max_v - min_v
    if spread == 0:
        return [50.0] * len(values)
    return [(v - min_v) / spread * 100 for v in values]


def _posting_frequency_score(freq: str) -> float:
    """Convert posting frequency label to a numeric score (higher = more frequent)."""
    freq_lower = freq.lower()
    if "multiple daily" in freq_lower:
        return 100
    elif "daily" in freq_lower:
        return 80
    elif "every few days" in freq_lower or "every 2" in freq_lower or "every 3" in freq_lower:
        return 60
    elif "weekly" in freq_lower:
        return 40
    elif "infrequent" in freq_lower:
        return 20
    elif "every" in freq_lower:
        # "~Every N days"
        import re
        match = re.search(r"(\d+)", freq_lower)
        if match:
            days = int(match.group(1))
            if days <= 3:
                return 60
            elif days <= 7:
                return 40
            else:
                return 20
        return 30
    return 30  # Unknown
