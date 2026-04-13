"""CSV and HTML dashboard output generation."""

import csv
import logging
import os
from datetime import datetime

from jinja2 import Template

logger = logging.getLogger(__name__)

CSV_COLUMNS = [
    "rank",
    "username",
    "display_name",
    "followers",
    "total_likes",
    "video_count",
    "avg_views",
    "follower_video_ratio",
    "virality_pct",
    "account_age",
    "growth_speed",
    "posting_frequency",
    "content_style",
    "copy_signals",
    "composite_score",
    "high_priority",
    "bio",
    "profile_url",
]


def write_csv(scored_accounts: list[dict], filepath: str):
    """Write scored accounts to a CSV file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for entry in scored_accounts:
            row = dict(entry)
            row["high_priority"] = "HIGH PRIORITY" if entry["high_priority"] else ""
            writer.writerow(row)

    logger.info(f"CSV written to {filepath}")


DASHBOARD_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dog Account Growth Intelligence Dashboard</title>
<style>
  :root {
    --bg: #0f1117;
    --card: #1a1d27;
    --border: #2a2d3a;
    --text: #e4e4e7;
    --muted: #9ca3af;
    --accent: #6366f1;
    --accent-light: #818cf8;
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --fire: #ff6b35;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 24px;
    line-height: 1.5;
  }
  .header {
    text-align: center;
    margin-bottom: 32px;
    padding: 32px;
    background: linear-gradient(135deg, var(--card), #1e1b4b);
    border-radius: 16px;
    border: 1px solid var(--border);
  }
  .header h1 {
    font-size: 28px;
    background: linear-gradient(90deg, var(--accent-light), #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
  }
  .header .subtitle {
    color: var(--muted);
    font-size: 14px;
  }
  .stats-bar {
    display: flex;
    gap: 16px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }
  .stat-card {
    flex: 1;
    min-width: 160px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
  }
  .stat-card .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-card .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
  .stat-card .value.fire { color: var(--fire); }
  .stat-card .value.green { color: var(--green); }
  .stat-card .value.accent { color: var(--accent-light); }

  .controls {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    align-items: center;
  }
  .controls input[type="text"] {
    flex: 1;
    min-width: 200px;
    padding: 10px 16px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 14px;
    outline: none;
  }
  .controls input:focus { border-color: var(--accent); }
  .controls select {
    padding: 10px 16px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 14px;
    cursor: pointer;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--border);
  }
  thead { background: #15171f; }
  th {
    padding: 14px 12px;
    text-align: left;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--muted);
    font-weight: 600;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }
  th:hover { color: var(--accent-light); }
  th.sorted-asc::after { content: ' \\25B2'; color: var(--accent-light); }
  th.sorted-desc::after { content: ' \\25BC'; color: var(--accent-light); }

  td {
    padding: 12px;
    font-size: 13px;
    border-top: 1px solid var(--border);
    vertical-align: top;
  }
  tr:hover { background: rgba(99, 102, 241, 0.06); }
  tr.high-priority { background: rgba(255, 107, 53, 0.08); }
  tr.high-priority:hover { background: rgba(255, 107, 53, 0.14); }

  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 9999px;
    font-size: 11px;
    font-weight: 600;
  }
  .badge-fire { background: rgba(255, 107, 53, 0.2); color: var(--fire); }
  .badge-repost { background: rgba(99, 102, 241, 0.2); color: var(--accent-light); }
  .badge-original { background: rgba(34, 197, 94, 0.2); color: var(--green); }
  .badge-mixed { background: rgba(245, 158, 11, 0.2); color: var(--amber); }

  .score-bar {
    width: 100%;
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
    margin-top: 4px;
  }
  .score-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s;
  }

  .username-link {
    color: var(--accent-light);
    text-decoration: none;
    font-weight: 600;
  }
  .username-link:hover { text-decoration: underline; }

  .copy-signals {
    max-width: 280px;
    font-size: 12px;
    color: var(--muted);
    line-height: 1.4;
  }
  .bio-text {
    max-width: 200px;
    font-size: 12px;
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .bio-text:hover { white-space: normal; }

  .num { font-variant-numeric: tabular-nums; }
  .right { text-align: right; }

  .footer {
    text-align: center;
    padding: 24px;
    color: var(--muted);
    font-size: 12px;
    margin-top: 24px;
  }

  @media (max-width: 1200px) {
    body { padding: 12px; }
    .copy-signals { max-width: 180px; }
  }
</style>
</head>
<body>

<div class="header">
  <h1>Dog Account Growth Intelligence</h1>
  <p class="subtitle">{{ total }} accounts scraped &bull; Generated {{ timestamp }}</p>
</div>

<div class="stats-bar">
  <div class="stat-card">
    <div class="label">Total Accounts</div>
    <div class="value accent">{{ total }}</div>
  </div>
  <div class="stat-card">
    <div class="label">High Priority</div>
    <div class="value fire">{{ high_priority_count }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Avg Followers</div>
    <div class="value green">{{ avg_followers }}</div>
  </div>
  <div class="stat-card">
    <div class="label">Top Virality %</div>
    <div class="value accent">{{ top_virality }}%</div>
  </div>
</div>

<div class="controls">
  <input type="text" id="searchBox" placeholder="Filter by username, bio, signals..." oninput="filterTable()">
  <select id="styleFilter" onchange="filterTable()">
    <option value="">All content styles</option>
    <option value="Reposts/Compilations">Reposts/Compilations</option>
    <option value="Likely Reposts">Likely Reposts</option>
    <option value="Original">Original</option>
    <option value="Mixed">Mixed</option>
    <option value="Undetermined">Undetermined</option>
  </select>
  <select id="priorityFilter" onchange="filterTable()">
    <option value="">All priorities</option>
    <option value="high">High Priority only</option>
  </select>
</div>

<table id="dashTable">
<thead>
<tr>
  <th data-col="rank" data-type="num">Rank</th>
  <th data-col="username" data-type="str">Account</th>
  <th data-col="followers" data-type="num">Followers</th>
  <th data-col="total_likes" data-type="num">Likes</th>
  <th data-col="video_count" data-type="num">Videos</th>
  <th data-col="avg_views" data-type="num">Avg Views</th>
  <th data-col="follower_video_ratio" data-type="num">F/V Ratio</th>
  <th data-col="virality_pct" data-type="num">Virality %</th>
  <th data-col="account_age" data-type="str">Age</th>
  <th data-col="posting_frequency" data-type="str">Post Freq</th>
  <th data-col="content_style" data-type="str">Content Style</th>
  <th data-col="copy_signals" data-type="str">Copy Signals</th>
  <th data-col="composite_score" data-type="num">Score</th>
</tr>
</thead>
<tbody>
{% for a in accounts %}
<tr class="{{ 'high-priority' if a.high_priority else '' }}"
    data-search="{{ a.username }} {{ a.display_name }} {{ a.bio }} {{ a.copy_signals }}|lower"
    data-style="{{ a.content_style }}"
    data-priority="{{ 'high' if a.high_priority else '' }}">
  <td class="num">{{ a.rank }}</td>
  <td>
    <a class="username-link" href="{{ a.profile_url }}" target="_blank" rel="noopener">@{{ a.username }}</a>
    {% if a.high_priority %}<span class="badge badge-fire">HIGH PRIORITY</span>{% endif %}
    <div class="bio-text" title="{{ a.bio }}">{{ a.bio[:80] }}</div>
  </td>
  <td class="num right">{{ "{:,}".format(a.followers) }}</td>
  <td class="num right">{{ "{:,}".format(a.total_likes) }}</td>
  <td class="num right">{{ "{:,}".format(a.video_count) }}</td>
  <td class="num right">{{ "{:,}".format(a.avg_views) }}</td>
  <td class="num right">{{ a.follower_video_ratio }}</td>
  <td class="num right">{{ a.virality_pct }}%</td>
  <td>{{ a.account_age }}</td>
  <td>{{ a.posting_frequency }}</td>
  <td>
    {% if 'Repost' in a.content_style or 'Compilation' in a.content_style %}
      <span class="badge badge-repost">{{ a.content_style }}</span>
    {% elif a.content_style == 'Original' %}
      <span class="badge badge-original">{{ a.content_style }}</span>
    {% elif a.content_style == 'Mixed' %}
      <span class="badge badge-mixed">{{ a.content_style }}</span>
    {% else %}
      {{ a.content_style }}
    {% endif %}
  </td>
  <td class="copy-signals">{{ a.copy_signals }}</td>
  <td class="num right">
    <strong>{{ a.composite_score }}</strong>
    <div class="score-bar">
      <div class="score-bar-fill" style="width: {{ a.composite_score }}%; background: {% if a.composite_score >= 70 %}var(--green){% elif a.composite_score >= 40 %}var(--amber){% else %}var(--accent){% endif %};"></div>
    </div>
  </td>
</tr>
{% endfor %}
</tbody>
</table>

<div class="footer">
  Dog Account Growth Intelligence Scraper &bull; Data is approximate and for research purposes only.
</div>

<script>
// Column sorting
document.querySelectorAll('#dashTable thead th').forEach(th => {
  th.addEventListener('click', () => {
    const table = document.getElementById('dashTable');
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const col = th.cellIndex;
    const type = th.dataset.type;
    const isAsc = th.classList.contains('sorted-asc');

    // Clear all sort indicators
    document.querySelectorAll('#dashTable th').forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));
    th.classList.add(isAsc ? 'sorted-desc' : 'sorted-asc');

    rows.sort((a, b) => {
      let aVal = a.cells[col].textContent.trim();
      let bVal = b.cells[col].textContent.trim();
      if (type === 'num') {
        aVal = parseFloat(aVal.replace(/[^\\d.\\-]/g, '')) || 0;
        bVal = parseFloat(bVal.replace(/[^\\d.\\-]/g, '')) || 0;
      }
      if (aVal < bVal) return isAsc ? 1 : -1;
      if (aVal > bVal) return isAsc ? -1 : 1;
      return 0;
    });

    rows.forEach(row => tbody.appendChild(row));
  });
});

// Filtering
function filterTable() {
  const search = document.getElementById('searchBox').value.toLowerCase();
  const style = document.getElementById('styleFilter').value;
  const priority = document.getElementById('priorityFilter').value;

  document.querySelectorAll('#dashTable tbody tr').forEach(row => {
    const text = row.dataset.search || '';
    const rowStyle = row.dataset.style || '';
    const rowPriority = row.dataset.priority || '';

    let show = true;
    if (search && !text.toLowerCase().includes(search)) show = false;
    if (style && rowStyle !== style) show = false;
    if (priority === 'high' && rowPriority !== 'high') show = false;

    row.style.display = show ? '' : 'none';
  });
}
</script>
</body>
</html>
"""


def write_html(scored_accounts: list[dict], filepath: str):
    """Render the HTML dashboard from scored account data."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Compute summary stats
    total = len(scored_accounts)
    hp_count = sum(1 for a in scored_accounts if a["high_priority"])
    avg_foll = int(sum(a["followers"] for a in scored_accounts) / max(total, 1))
    top_vir = max((a["virality_pct"] for a in scored_accounts), default=0)

    def format_num(n):
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    template = Template(DASHBOARD_TEMPLATE)
    html = template.render(
        accounts=scored_accounts,
        total=total,
        high_priority_count=hp_count,
        avg_followers=format_num(avg_foll),
        top_virality=top_vir,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info(f"HTML dashboard written to {filepath}")
