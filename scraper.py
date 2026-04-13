"""TikTok Dog Account Scraper using Playwright."""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from playwright.async_api import async_playwright, Page, BrowserContext

import config

logger = logging.getLogger(__name__)


@dataclass
class AccountData:
    username: str = ""
    display_name: str = ""
    follower_count: int = 0
    total_likes: int = 0
    video_count: int = 0
    avg_views: float = 0.0
    account_age: str = "Unknown"
    account_age_months: float = -1
    bio: str = ""
    posting_frequency: str = "Unknown"
    content_style: str = "Unknown"
    copy_signals: str = ""
    video_views: list = field(default_factory=list)
    recent_captions: list = field(default_factory=list)
    recent_dates: list = field(default_factory=list)
    hashtags_used: list = field(default_factory=list)
    profile_url: str = ""


def parse_count(text: str) -> int:
    """Parse abbreviated counts like '1.2M', '456K', '12.3B' into integers."""
    if not text:
        return 0
    text = text.strip().upper().replace(",", "")
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    for suffix, mult in multipliers.items():
        if text.endswith(suffix):
            try:
                return int(float(text[:-1]) * mult)
            except ValueError:
                return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def estimate_age_months(age_text: str) -> float:
    """Convert an age string like 'Joined Jan 2023' to months from now."""
    if not age_text or age_text == "Unknown":
        return -1
    try:
        # Try parsing "Joined <Month> <Year>" format
        match = re.search(r"(\w+ \d{4})", age_text)
        if match:
            from dateutil.parser import parse as dateparse
            joined = dateparse(match.group(1))
            delta = datetime.now() - joined
            return max(delta.days / 30.44, 0.1)
    except Exception:
        pass
    return -1


async def create_browser_context() -> tuple:
    """Launch browser and create a stealth-ish context."""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=config.HEADLESS,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/121.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    context.set_default_timeout(config.PAGE_TIMEOUT)
    context.set_default_navigation_timeout(config.NAV_TIMEOUT)
    return pw, browser, context


async def dismiss_overlays(page: Page):
    """Dismiss cookie banners, login modals, and other overlays."""
    dismiss_selectors = [
        # Cookie banners
        'button:has-text("Accept all")',
        'button:has-text("Accept")',
        'button:has-text("Allow all")',
        # Login/signup modals
        '[data-e2e="modal-close-inner-button"]',
        'button[aria-label="Close"]',
        '.tiktok-modal button:has-text("Not now")',
        # CAPTCHA close
        '.verify-bar-close',
    ]
    for selector in dismiss_selectors:
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=1000):
                await el.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass


async def search_accounts(context: BrowserContext, keyword: str) -> list[str]:
    """Search TikTok for a keyword and collect unique account usernames from results."""
    page = await context.new_page()
    usernames = []
    try:
        search_url = f"https://www.tiktok.com/search/user?q={keyword.replace(' ', '%20')}"
        logger.info(f"Searching: {keyword}")
        await page.goto(search_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await dismiss_overlays(page)

        # Scroll to load more results
        for _ in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1.5)

        # Extract usernames from user search results
        # TikTok user search results contain links to profiles
        links = await page.query_selector_all('a[href*="/@"]')
        seen = set()
        for link in links:
            href = await link.get_attribute("href")
            if href:
                match = re.search(r"/@([^/?]+)", href)
                if match:
                    uname = match.group(1).lower()
                    if uname not in seen:
                        seen.add(uname)
                        usernames.append(uname)
            if len(usernames) >= config.ACCOUNTS_PER_KEYWORD:
                break

        logger.info(f"  Found {len(usernames)} accounts for '{keyword}'")
    except Exception as e:
        logger.warning(f"  Error searching '{keyword}': {e}")
    finally:
        await page.close()

    return usernames


async def scrape_profile(context: BrowserContext, username: str) -> AccountData | None:
    """Scrape a single TikTok profile page for account data."""
    account = AccountData(username=username, profile_url=f"https://www.tiktok.com/@{username}")
    page = await context.new_page()

    try:
        logger.info(f"  Scraping @{username}")
        await page.goto(f"https://www.tiktok.com/@{username}", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        await dismiss_overlays(page)

        # --- Display Name ---
        try:
            name_el = page.locator('h1[data-e2e="user-title"], h2[data-e2e="user-subtitle"]').first
            account.display_name = (await name_el.inner_text()).strip()
        except Exception:
            try:
                name_el = page.locator("h1").first
                account.display_name = (await name_el.inner_text()).strip()
            except Exception:
                account.display_name = username

        # --- Stats: followers, likes, video count ---
        # Try data-e2e attributes first
        stat_map = {
            "followers-count": "follower_count",
            "likes-count": "total_likes",
            "following-count": None,  # skip
        }
        for attr, field_name in stat_map.items():
            if field_name is None:
                continue
            try:
                el = page.locator(f'strong[data-e2e="{attr}"], [data-e2e="{attr}"]').first
                text = await el.inner_text()
                setattr(account, field_name, parse_count(text))
            except Exception:
                pass

        # Video count from tab or stats bar
        try:
            video_tab = page.locator('[data-e2e="videos-tab"] span, [data-e2e="user-post-item-count"]').first
            text = await video_tab.inner_text()
            count = parse_count(re.sub(r"[^0-9KMBkmb.]", "", text))
            if count > 0:
                account.video_count = count
        except Exception:
            pass

        # Fallback: parse stats from the page text
        if account.follower_count == 0:
            try:
                page_text = await page.inner_text("body")
                followers_match = re.search(r"([\d.]+[KMB]?)\s*Follower", page_text, re.IGNORECASE)
                if followers_match:
                    account.follower_count = parse_count(followers_match.group(1))
                likes_match = re.search(r"([\d.]+[KMB]?)\s*Like", page_text, re.IGNORECASE)
                if likes_match:
                    account.total_likes = parse_count(likes_match.group(1))
            except Exception:
                pass

        # --- Bio ---
        try:
            bio_el = page.locator('[data-e2e="user-bio"], .user-bio').first
            account.bio = (await bio_el.inner_text()).strip()
        except Exception:
            try:
                bio_el = page.locator('h2[data-e2e="user-subtitle"]').first
                # If this is actually the subtitle not bio, try another selector
                bio_el2 = page.locator('.share-desc, [class*="userBio"]').first
                account.bio = (await bio_el2.inner_text()).strip()
            except Exception:
                pass

        # --- Account age ---
        try:
            # Sometimes visible in profile metadata
            page_text = await page.inner_text("body")
            join_match = re.search(r"Joined\s+(\w+\s+\d{4})", page_text)
            if join_match:
                account.account_age = f"Joined {join_match.group(1)}"
                account.account_age_months = estimate_age_months(account.account_age)
        except Exception:
            pass

        # --- Scrape recent videos for views, captions, dates ---
        await _scrape_recent_videos(page, account)

        # --- Analyze content patterns ---
        _analyze_content(account)

    except Exception as e:
        logger.warning(f"  Error scraping @{username}: {e}")
        return None
    finally:
        await page.close()

    return account


async def _scrape_recent_videos(page: Page, account: AccountData):
    """Extract data from the most recent videos on a profile page."""
    try:
        # Wait for video items to load
        await page.wait_for_selector(
            '[data-e2e="user-post-item"], [class*="DivItemContainer"], [class*="video-feed"] a',
            timeout=8000,
        )
    except Exception:
        logger.debug(f"  No video items found for @{account.username}")
        return

    video_links = await page.query_selector_all(
        '[data-e2e="user-post-item"] a, [data-e2e="user-post-item-list"] a[href*="/video/"]'
    )
    if not video_links:
        video_links = await page.query_selector_all('a[href*="/video/"]')

    # Collect view counts displayed on thumbnails
    view_elements = await page.query_selector_all(
        '[data-e2e="video-views"], [class*="video-count"], [class*="DivPlayCount"]'
    )
    for el in view_elements[: config.VIDEOS_TO_SAMPLE]:
        try:
            text = await el.inner_text()
            views = parse_count(text.strip())
            if views > 0:
                account.video_views.append(views)
        except Exception:
            pass

    # If we didn't get view counts from thumbnails, try clicking into videos
    if len(account.video_views) < 3 and video_links:
        sample_links = video_links[: min(config.VIDEOS_TO_SAMPLE, len(video_links))]
        for link in sample_links:
            try:
                href = await link.get_attribute("href")
                if not href or "/video/" not in href:
                    continue

                # Try to get the caption text from the thumbnail
                try:
                    caption_el = await link.query_selector(
                        '[class*="title"], [class*="desc"], [class*="caption"]'
                    )
                    if caption_el:
                        cap_text = await caption_el.inner_text()
                        if cap_text.strip():
                            account.recent_captions.append(cap_text.strip())
                except Exception:
                    pass

            except Exception:
                continue

    # Navigate into a few videos to get view counts and captions if still needed
    if len(account.video_views) < 3:
        video_hrefs = []
        for link in video_links[: config.VIDEOS_TO_SAMPLE]:
            try:
                href = await link.get_attribute("href")
                if href and "/video/" in href:
                    if not href.startswith("http"):
                        href = "https://www.tiktok.com" + href
                    video_hrefs.append(href)
            except Exception:
                pass

        for href in video_hrefs[:5]:
            try:
                await page.goto(href, wait_until="domcontentloaded")
                await asyncio.sleep(2)
                await dismiss_overlays(page)

                # View count
                try:
                    view_el = page.locator(
                        '[data-e2e="video-views"], [data-e2e="browse-video-count"], '
                        '[class*="PlayCount"], strong:near(:text("views"))'
                    ).first
                    text = await view_el.inner_text()
                    views = parse_count(text)
                    if views > 0:
                        account.video_views.append(views)
                except Exception:
                    pass

                # Caption
                try:
                    cap_el = page.locator(
                        '[data-e2e="browse-video-desc"], [data-e2e="video-desc"], '
                        '[class*="videoDesc"], [class*="caption"]'
                    ).first
                    text = await cap_el.inner_text()
                    if text.strip():
                        account.recent_captions.append(text.strip())
                        # Extract hashtags
                        tags = re.findall(r"#\w+", text)
                        account.hashtags_used.extend(tags)
                except Exception:
                    pass

                # Date
                try:
                    date_el = page.locator(
                        '[data-e2e="browser-nickname"] + span, '
                        'span:has-text("ago"), span:has-text("2024"), span:has-text("2025"), '
                        'span:has-text("2026")'
                    ).first
                    text = await date_el.inner_text()
                    account.recent_dates.append(text.strip())
                except Exception:
                    pass

            except Exception:
                continue

        # Navigate back to profile
        try:
            await page.goto(
                f"https://www.tiktok.com/@{account.username}",
                wait_until="domcontentloaded",
            )
        except Exception:
            pass

    # Calculate averages
    if account.video_views:
        account.avg_views = sum(account.video_views) / len(account.video_views)
    if not account.video_count and video_links:
        account.video_count = len(video_links)

    # Deduplicate hashtags
    account.hashtags_used = list(dict.fromkeys(account.hashtags_used))


def _analyze_content(account: AccountData):
    """Analyze captions, bio, and patterns to classify content style and extract signals."""
    all_text = " ".join(account.recent_captions + [account.bio]).lower()

    # --- Content style classification ---
    repost_signals = [
        "repost", "compilation", "credit", "dm for removal", "not mine",
        "dm to remove", "original creator", "all credits", "no copyright",
        "daily dose", "best of", "top clips", "funny moments", "tag the owner",
    ]
    original_signals = [
        "my dog", "our dog", "meet my", "my puppy", "rescued", "adopted",
        "our puppy", "my pup",
    ]

    repost_count = sum(1 for s in repost_signals if s in all_text)
    original_count = sum(1 for s in original_signals if s in all_text)

    if repost_count >= 2 and original_count == 0:
        account.content_style = "Reposts/Compilations"
    elif original_count >= 2 and repost_count == 0:
        account.content_style = "Original"
    elif repost_count > 0 and original_count > 0:
        account.content_style = "Mixed"
    elif any(w in all_text for w in ["compilation", "daily", "moments", "best", "clips"]):
        account.content_style = "Likely Reposts"
    else:
        account.content_style = "Undetermined"

    # --- Posting frequency estimation ---
    if account.recent_dates:
        _estimate_posting_frequency(account)
    elif account.video_count > 0:
        if account.account_age_months > 0:
            vids_per_month = account.video_count / account.account_age_months
            if vids_per_month >= 30:
                account.posting_frequency = "Multiple daily"
            elif vids_per_month >= 15:
                account.posting_frequency = "Daily"
            elif vids_per_month >= 7:
                account.posting_frequency = "Every few days"
            elif vids_per_month >= 3:
                account.posting_frequency = "Weekly"
            else:
                account.posting_frequency = "Infrequent"

    # --- Copy signals ---
    signals = []

    # Caption style
    captions = account.recent_captions
    if captions:
        avg_len = sum(len(c) for c in captions) / len(captions)
        if avg_len < 30:
            signals.append("Short captions")
        elif avg_len > 100:
            signals.append("Long captions with stories")
        else:
            signals.append("Medium-length captions")

        emoji_count = sum(1 for c in " ".join(captions) if ord(c) > 0x1F600)
        if emoji_count > len(captions) * 2:
            signals.append("Heavy emoji usage")

        question_count = sum(1 for c in captions if "?" in c)
        if question_count > len(captions) * 0.3:
            signals.append("Uses questions as hooks")

    # Hashtag patterns
    if account.hashtags_used:
        signals.append(f"Top hashtags: {', '.join(account.hashtags_used[:5])}")
        if len(account.hashtags_used) > len(captions or [1]) * 3:
            signals.append("Hashtag-heavy strategy")

    # Bio patterns
    bio = account.bio.lower()
    if "daily" in bio:
        signals.append("'Daily' in bio (consistency promise)")
    if "dm" in bio:
        signals.append("DM engagement in bio")
    if "link" in bio or "linktree" in bio:
        signals.append("Link in bio (monetization)")
    if any(w in bio for w in ["submit", "send", "tag"]):
        signals.append("UGC/submission-based content")
    if "follow" in bio:
        signals.append("Follow CTA in bio")

    account.copy_signals = "; ".join(signals) if signals else "No clear signals detected"


def _estimate_posting_frequency(account: AccountData):
    """Estimate posting frequency from recent video dates."""
    from dateutil.parser import parse as dateparse

    dates = []
    for d in account.recent_dates:
        try:
            # Handle relative times
            if "ago" in d.lower():
                if "hour" in d.lower() or "minute" in d.lower():
                    dates.append(datetime.now())
                elif "day" in d.lower():
                    match = re.search(r"(\d+)", d)
                    if match:
                        from datetime import timedelta
                        days = int(match.group(1))
                        dates.append(datetime.now() - timedelta(days=days))
                continue
            parsed = dateparse(d, fuzzy=True)
            dates.append(parsed)
        except Exception:
            pass

    if len(dates) >= 2:
        dates.sort(reverse=True)
        gaps = [(dates[i] - dates[i + 1]).days for i in range(len(dates) - 1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 999

        if avg_gap < 1:
            account.posting_frequency = "Multiple daily"
        elif avg_gap <= 1.5:
            account.posting_frequency = "Daily"
        elif avg_gap <= 3:
            account.posting_frequency = "Every few days"
        elif avg_gap <= 7:
            account.posting_frequency = "Weekly"
        else:
            account.posting_frequency = f"~Every {int(avg_gap)} days"


async def run_scraper(keywords: list[str] | None = None) -> list[AccountData]:
    """Main scraper pipeline: search keywords -> collect profiles -> scrape each."""
    keywords = keywords or config.SEARCH_KEYWORDS
    all_usernames: dict[str, str] = {}  # username -> keyword that found it

    pw, browser, context = await create_browser_context()

    try:
        # Phase 1: Search for accounts
        logger.info("=== Phase 1: Searching for dog accounts ===")
        for keyword in keywords:
            found = await search_accounts(context, keyword)
            for u in found:
                if u not in all_usernames:
                    all_usernames[u] = keyword
            await asyncio.sleep(config.SLOW_MO / 1000)

        logger.info(f"\nFound {len(all_usernames)} unique accounts across all keywords")

        # Phase 2: Scrape each profile
        logger.info("\n=== Phase 2: Scraping profiles ===")
        accounts: list[AccountData] = []
        for i, username in enumerate(all_usernames, 1):
            logger.info(f"[{i}/{len(all_usernames)}]")
            account = await scrape_profile(context, username)
            if account:
                accounts.append(account)
            await asyncio.sleep(config.SLOW_MO / 1000)

        logger.info(f"\nSuccessfully scraped {len(accounts)} accounts")
        return accounts

    finally:
        await browser.close()
        await pw.stop()
