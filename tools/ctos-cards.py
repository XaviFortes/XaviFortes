#!/usr/bin/env python3
"""Render live GitHub metrics as xfOS-styled SVG cards.

Pulls everything from the GitHub GraphQL API and writes static SVGs into
assets/gen/. Run from CI so the README never depends on a third-party card
service being up.

    GITHUB_TOKEN=... python3 tools/xfOS-cards.py [--user XaviFortes]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import pathlib
import sys
import urllib.error
import urllib.request
from collections import defaultdict

API = "https://api.github.com/graphql"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "gen"

# ---------------------------------------------------------------- palette --
BG = "#04090C"
PANEL = "#071319"
LINE = "#0E3A47"
LINE2 = "#10505F"
CYAN = "#22E6FF"
CYAND = "#0FB9D6"
DIM = "#4C7480"
TEXT = "#CFE6EC"
AMBER = "#FFB020"
GREEN = "#39FF8F"
RAMP = ["#08161C", "#0D4453", "#12708A", "#17A8CA", "#22E6FF"]
# rank ramp for language bars — cyan fading to amber, so the chart reads as one
# palette instead of GitHub's rainbow of official language colours
RANK = ["#22E6FF", "#1BCDE8", "#15B4D1", "#109BB9", "#0C82A1",
        "#FFB020", "#DE9A1D", "#BC8319", "#7A6A45", "#4C7480"]

MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'DejaVu Sans Mono', monospace"


# ------------------------------------------------------------------ query --
def gql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "xfOS-cards",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise RuntimeError(json.dumps(payload["errors"], indent=2))
    return payload["data"]


PROFILE_Q = """
query($login: String!) {
  user(login: $login) {
    login
    name
    createdAt
    followers { totalCount }
    following { totalCount }
    gists { totalCount }
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(
      contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]
      includeUserRepositories: false
    ) { totalCount }
    repositories(
      ownerAffiliations: OWNER
      isFork: false
      privacy: PUBLIC
      first: 100
      orderBy: { field: STARGAZERS, direction: DESC }
    ) {
      totalCount
      nodes {
        name
        stargazerCount
        forkCount
        languages(first: 12, orderBy: { field: SIZE, direction: DESC }) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

# Curated showcase for the "ASSETS RECOVERED" section, rendered one card per
# repo so each can be wrapped in a link in the README.
FEATURED = [
    "MetalMC",
    "otel-stream-router",
    "shellnet-infrastructure",
    "DeckSaves",
    "IPTables-DDOS-Protection",
    "tesla-tracker",
]

REPO_Q = """
query($login: String!, $name: String!) {
  repository(owner: $login, name: $name) {
    name
    description
    stargazerCount
    forkCount
    pushedAt
    primaryLanguage { name }
    repositoryTopics(first: 4) { nodes { topic { name } } }
  }
}
"""

YEAR_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def collect(token: str, login: str) -> dict:
    profile = gql(token, PROFILE_Q, {"login": login})["user"]
    created = dt.datetime.fromisoformat(profile["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)

    days: dict[str, int] = {}
    totals = defaultdict(int)
    # contributionsCollection caps at one year per call, so walk year by year
    start = created
    while start < now:
        end = min(start + dt.timedelta(days=364), now)
        cc = gql(
            token,
            YEAR_Q,
            {
                "login": login,
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": end.isoformat().replace("+00:00", "Z"),
            },
        )["user"]["contributionsCollection"]
        for key in (
            "totalCommitContributions",
            "totalPullRequestContributions",
            "totalIssueContributions",
            "totalPullRequestReviewContributions",
            "restrictedContributionsCount",
        ):
            totals[key] += cc[key]
        for week in cc["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                days[day["date"]] = max(days.get(day["date"], 0), day["contributionCount"])
        start = end + dt.timedelta(seconds=1)

    repos = []
    for name in FEATURED:
        try:
            repos.append(gql(token, REPO_Q, {"login": login, "name": name})["repository"])
        except (urllib.error.HTTPError, RuntimeError) as e:
            print(f"warning: skipping {name}: {e}", file=sys.stderr)

    return {"profile": profile, "totals": dict(totals), "days": days,
            "featured": repos, "now": now}


# ------------------------------------------------------------- derivation --
def streaks(days: dict[str, int]) -> dict:
    """Current / longest streak. Today counts as pending, not as a break."""
    if not days:
        return {"current": 0, "longest": 0, "cur_from": None, "cur_to": None,
                "long_from": None, "long_to": None, "best_day": None, "best_count": 0}

    ordered = sorted(days)
    today = ordered[-1]

    longest = run = 0
    long_end = run_start = None
    long_start = None
    prev_active = False
    for d in ordered:
        if days[d] > 0:
            run = run + 1 if prev_active else 1
            if run == 1:
                run_start = d
            if run > longest:
                longest, long_start, long_end = run, run_start, d
            prev_active = True
        else:
            prev_active = False
            run = 0

    # walk backwards for the current streak, tolerating an empty "today"
    idx = len(ordered) - 1
    if days[ordered[idx]] == 0 and ordered[idx] == today:
        idx -= 1
    current = 0
    cur_to = cur_from = None
    while idx >= 0 and days[ordered[idx]] > 0:
        cur_to = cur_to or ordered[idx]
        cur_from = ordered[idx]
        current += 1
        idx -= 1

    best_day = max(days, key=lambda d: days[d])
    return {
        "current": current,
        "longest": longest,
        "cur_from": cur_from,
        "cur_to": cur_to,
        "long_from": long_start,
        "long_to": long_end,
        "best_day": best_day,
        "best_count": days[best_day],
    }


def language_totals(repos: list[dict]) -> list[tuple[str, int, str]]:
    sizes: dict[str, int] = defaultdict(int)
    colors: dict[str, str] = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            sizes[name] += edge["size"]
            colors[name] = edge["node"]["color"] or DIM
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)
    return [(name, size, colors[name]) for name, size in ranked]


def human(n: int) -> str:
    for limit, suffix in ((1_000_000_000, "G"), (1_000_000, "M"), (1_000, "k")):
        if n >= limit:
            v = n / limit
            return f"{v:.1f}".rstrip("0").rstrip(".") + suffix
    return str(n)


def bytes_h(n: int) -> str:
    for limit, suffix in ((1 << 30, "GB"), (1 << 20, "MB"), (1 << 10, "kB")):
        if n >= limit:
            return f"{n / limit:.1f} {suffix}"
    return f"{n} B"


def nice_date(iso: str | None) -> str:
    if not iso:
        return "—"
    d = dt.date.fromisoformat(iso)
    return d.strftime("%d %b %Y").upper()


# ------------------------------------------------------------------ chrome --
def frame(w: int, h: int, uid: str, title: str, code: str) -> str:
    """Shared xfOS panel: backdrop, border, corner ticks, title bar."""
    return f"""
  <defs>
    <pattern id="scan{uid}" width="3" height="3" patternUnits="userSpaceOnUse">
      <line x1="0" y1="2.5" x2="3" y2="2.5" stroke="{CYAN}" stroke-opacity="0.045" stroke-width="1"/>
    </pattern>
    <pattern id="grid{uid}" width="34" height="20" patternUnits="userSpaceOnUse">
      <path d="M0 10 L8.5 0 L25.5 0 L34 10 L25.5 20 L8.5 20 Z" fill="none"
            stroke="{CYAN}" stroke-opacity="0.05" stroke-width="0.8"/>
    </pattern>
    <clipPath id="clip{uid}"><rect x="0" y="0" width="{w}" height="{h}"/></clipPath>
  </defs>
  <g clip-path="url(#clip{uid})">
    <rect width="{w}" height="{h}" fill="{BG}"/>
    <rect width="{w}" height="{h}" fill="url(#grid{uid})"/>
    <rect width="{w}" height="{h}" fill="url(#scan{uid})"/>
    <rect x="0" y="0" width="{w}" height="2" fill="{CYAN}" opacity="0">
      <animate attributeName="y" values="0;{h};0" dur="8s" repeatCount="indefinite"/>
      <animate attributeName="opacity" values="0;0.25;0" dur="8s" repeatCount="indefinite"/>
    </rect>
  </g>
  <rect x="1" y="1" width="{w-2}" height="{h-2}" fill="none" stroke="{LINE}" stroke-width="1.4"/>
  <g stroke="{CYAN}" stroke-width="1.8" fill="none" stroke-linecap="square">
    <path d="M9,25 L9,9 L25,9"/>
    <path d="M{w-25},9 L{w-9},9 L{w-9},25"/>
    <path d="M{w-9},{h-25} L{w-9},{h-9} L{w-25},{h-9}"/>
    <path d="M25,{h-9} L9,{h-9} L9,{h-25}"/>
  </g>
  <rect x="9" y="9" width="{w-18}" height="26" fill="{CYAN}" fill-opacity="0.06"/>
  <line x1="9" y1="35" x2="{w-9}" y2="35" stroke="{LINE}" stroke-width="1"/>
  <text x="24" y="27" font-size="12.5" fill="{CYAN}" letter-spacing="2.6">{title}</text>
  <text x="{w-24}" y="27" font-size="10.5" fill="{DIM}" letter-spacing="1.8"
        text-anchor="end">{code}</text>"""


def svg(w: int, h: int, label: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"\n'
        f'     font-family="{MONO}" role="img" aria-label="{label}">\n{body}\n</svg>\n'
    )


# ------------------------------------------------------------------ cards --
def card_stats(data: dict) -> str:
    p, t = data["profile"], data["totals"]
    repos = p["repositories"]["nodes"]
    stars = sum(r["stargazerCount"] for r in repos)
    forks = sum(r["forkCount"] for r in repos)
    commits = t["totalCommitContributions"] + t["restrictedContributionsCount"]

    cells = [
        ("COMMITS",      human(commits),                       CYAN),
        ("STARS EARNED", human(stars),                         AMBER),
        ("PULL REQS",    human(p["pullRequests"]["totalCount"]), CYAN),
        ("ISSUES",       human(p["issues"]["totalCount"]),     CYAN),
        ("REVIEWS",      human(t["totalPullRequestReviewContributions"]), CYAN),
        ("FORKS",        human(forks),                         CYAN),
        ("REPOS",        human(p["repositories"]["totalCount"]), CYAN),
        ("CONTRIB TO",   human(p["repositoriesContributedTo"]["totalCount"]), CYAN),
        ("FOLLOWERS",    human(p["followers"]["totalCount"]),   GREEN),
        ("GISTS",        human(p["gists"]["totalCount"]),       CYAN),
    ]

    W, H = 490, 280
    rows = []
    for i, (label, value, color) in enumerate(cells):
        col, row = i % 2, i // 2
        x = 26 + col * 232
        y = 86 + row * 38
        rows.append(
            f'<rect x="{x}" y="{y-17}" width="3" height="22" fill="{color}" opacity="0.55"/>'
            f'<text x="{x+14}" y="{y}" font-size="11.5" fill="{DIM}" letter-spacing="1.6">{label}</text>'
            f'<text x="{x+206}" y="{y}" font-size="17" fill="{color}" text-anchor="end">{value}</text>'
            f'<line x1="{x+14}" y1="{y+9}" x2="{x+206}" y2="{y+9}" stroke="{LINE}" stroke-width="1"/>'
        )

    body = (
        frame(W, H, "ST", "SUBJECT STATS", "xfOS/0x01")
        + f'\n  <text x="26" y="56" font-size="10.5" fill="{DIM}" letter-spacing="1.4">'
        f'LIFETIME RECORD &#183; SYNCED {data["now"].strftime("%Y.%m.%d %H:%M")} UTC</text>\n  '
        + "\n  ".join(rows)
    )
    return svg(W, H, "GitHub statistics", body)


def card_streak(data: dict) -> str:
    days = data["days"]
    s = streaks(days)
    total = sum(days.values())
    active = sum(1 for v in days.values() if v > 0)
    span = max(len(days), 1)

    W, H = 490, 268
    cx = W / 2

    # sparkline of the last 120 days
    recent = [days[d] for d in sorted(days)[-120:]]
    peak = max(recent) if recent and max(recent) else 1
    step = (W - 60) / max(len(recent) - 1, 1)
    pts = " ".join(
        f"{30 + i*step:.1f},{232 - (v / peak) * 30:.1f}" for i, v in enumerate(recent)
    )

    body = f"""{frame(W, H, "SK", "STREAK ANALYSIS", "xfOS/0x02")}
  <text x="26" y="56" font-size="10.5" fill="{DIM}" letter-spacing="1.4">CONTRIBUTION CONTINUITY &#183; {active} ACTIVE DAYS / {span}</text>

  <line x1="{cx-78}" y1="72" x2="{cx-78}" y2="192" stroke="{LINE}" stroke-width="1"/>
  <line x1="{cx+78}" y1="72" x2="{cx+78}" y2="192" stroke="{LINE}" stroke-width="1"/>

  <text x="{cx-108}" y="106" font-size="26" fill="{TEXT}" text-anchor="middle">{human(total)}</text>
  <text x="{cx-108}" y="126" font-size="10.5" fill="{DIM}" text-anchor="middle" letter-spacing="1.4">TOTAL</text>
  <text x="{cx-108}" y="150" font-size="9.5" fill="{DIM}" text-anchor="middle">{nice_date(min(days) if days else None)}</text>

  <circle cx="{cx}" cy="118" r="46" fill="none" stroke="{LINE}" stroke-width="6"/>
  <circle cx="{cx}" cy="118" r="46" fill="none" stroke="{CYAN}" stroke-width="6"
          stroke-linecap="butt" stroke-dasharray="289" stroke-dashoffset="289"
          transform="rotate(-90 {cx} 118)">
    <animate attributeName="stroke-dashoffset" values="289;{289 - min(s['current'] / max(s['longest'], 1), 1) * 289:.0f}"
             dur="1.4s" fill="freeze"/>
  </circle>
  <text x="{cx}" y="114" font-size="30" fill="{CYAN}" text-anchor="middle">{s['current']}</text>
  <text x="{cx}" y="134" font-size="9.5" fill="{DIM}" text-anchor="middle" letter-spacing="1.4">DAY STREAK</text>
  <text x="{cx}" y="182" font-size="9.5" fill="{DIM}" text-anchor="middle">{nice_date(s['cur_from'])} &#8594; {nice_date(s['cur_to'])}</text>

  <text x="{cx+108}" y="106" font-size="26" fill="{AMBER}" text-anchor="middle">{s['longest']}</text>
  <text x="{cx+108}" y="126" font-size="10.5" fill="{DIM}" text-anchor="middle" letter-spacing="1.4">LONGEST</text>
  <text x="{cx+108}" y="150" font-size="9.5" fill="{DIM}" text-anchor="middle">{nice_date(s['long_to'])}</text>

  <text x="26" y="212" font-size="10" fill="{DIM}" letter-spacing="1.4">LAST 120 DAYS &#183; PEAK {s['best_count']} ON {nice_date(s['best_day'])}</text>
  <polyline points="{pts}" fill="none" stroke="{CYAN}" stroke-width="1.5" stroke-opacity="0.85"/>
  <line x1="30" y1="234" x2="{W-30}" y2="234" stroke="{LINE}" stroke-width="1"/>"""
    return svg(W, H, "Contribution streak", body)


def card_languages(data: dict) -> str:
    ranked = [
        (name, size, RANK[i])
        for i, (name, size, _) in enumerate(language_totals(data["profile"]["repositories"]["nodes"])[:10])
    ]
    total = sum(size for _, size, _ in ranked) or 1

    W, H = 1000, 248
    bar_x, bar_w, bar_y = 26, W - 52, 66
    segments, cursor = [], float(bar_x)
    for name, size, color in ranked:
        seg = bar_w * size / total
        segments.append(
            f'<rect x="{cursor:.1f}" y="{bar_y}" width="{max(seg - 1.5, 1):.1f}" height="16" fill="{color}">'
            f'<animate attributeName="height" values="0;16" dur="0.5s" fill="freeze"/>'
            f'<animate attributeName="y" values="{bar_y+16};{bar_y}" dur="0.5s" fill="freeze"/>'
            f"</rect>"
        )
        cursor += seg

    rows = []
    for i, (name, size, color) in enumerate(ranked):
        col, row = i % 2, i // 2
        x = 26 + col * 486
        y = 130 + row * 22
        pct = 100 * size / total
        rows.append(
            f'<rect x="{x}" y="{y-8}" width="9" height="9" fill="{color}"/>'
            f'<text x="{x+20}" y="{y}" font-size="12" fill="{TEXT}">{name}</text>'
            f'<text x="{x+250}" y="{y}" font-size="11.5" fill="{DIM}" text-anchor="end">{bytes_h(size)}</text>'
            f'<rect x="{x+264}" y="{y-7}" width="140" height="7" fill="#0C2A33"/>'
            f'<rect x="{x+264}" y="{y-7}" width="{140 * size / ranked[0][1]:.1f}" height="7" fill="{color}" opacity="0.85"/>'
            f'<text x="{x+458}" y="{y}" font-size="11.5" fill="{CYAND}" text-anchor="end">{pct:.1f}%</text>'
        )

    body = (
        frame(W, H, "LG", "LANGUAGE DISTRIBUTION", "xfOS/0x03")
        + f'\n  <text x="26" y="54" font-size="10.5" fill="{DIM}" letter-spacing="1.4">'
        f"WEIGHTED BY SOURCE VOLUME ACROSS "
        f'{data["profile"]["repositories"]["totalCount"]} PUBLIC REPOSITORIES &#183; {bytes_h(total)} ANALYSED</text>\n  '
        + "\n  ".join(segments)
        + "\n  "
        + "\n  ".join(rows)
    )
    return svg(W, H, "Language distribution", body)


def card_heatmap(data: dict) -> str:
    days = data["days"]
    today = max(days) if days else dt.date.today().isoformat()
    end = dt.date.fromisoformat(today)
    start = end - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # back to a Sunday

    counts = [c for d, c in days.items() if start.isoformat() <= d <= today and c > 0]
    counts.sort()

    def level(n: int) -> int:
        if n <= 0 or not counts:
            return 0
        for i, q in enumerate((0.25, 0.5, 0.75)):
            if n <= counts[int(len(counts) * q)]:
                return i + 1
        return 4

    W, H = 1000, 252
    cell, gap = 14, 3
    ox, oy = 44, 88

    squares, labels, seen_months = [], [], set()
    cursor, week = start, 0
    while cursor <= end:
        dow = (cursor.weekday() + 1) % 7  # Sunday-first, like GitHub
        n = days.get(cursor.isoformat(), 0)
        x = ox + week * (cell + gap)
        y = oy + dow * (cell + gap)
        lv = level(n)
        squares.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{RAMP[lv]}" '
            f'stroke="{CYAN}" stroke-opacity="0.07"><title>{cursor.isoformat()} &#183; {n}</title></rect>'
        )
        if cursor.day <= 7 and cursor.strftime("%b") not in seen_months and dow == 0:
            seen_months.add(cursor.strftime("%b"))
            labels.append(
                f'<text x="{x}" y="{oy-10}" font-size="10" fill="{DIM}" letter-spacing="1">'
                f"{cursor.strftime('%b').upper()}</text>"
            )
        if dow == 6:
            week += 1
        cursor += dt.timedelta(days=1)

    dow_labels = "".join(
        f'<text x="{ox-10}" y="{oy + i*(cell+gap) + 11}" font-size="9.5" fill="{DIM}" text-anchor="end">{lbl}</text>'
        for i, lbl in ((1, "M"), (3, "W"), (5, "F"))
    )
    legend = "".join(
        f'<rect x="{W - 190 + i*18}" y="{H-34}" width="{cell}" height="{cell}" fill="{c}" '
        f'stroke="{CYAN}" stroke-opacity="0.07"/>'
        for i, c in enumerate(RAMP)
    )

    year_total = sum(c for d, c in days.items() if start.isoformat() <= d <= today)
    body = (
        frame(W, H, "HM", "CONTRIBUTION HEATMAP", "xfOS/0x04")
        + f'\n  <text x="26" y="54" font-size="10.5" fill="{DIM}" letter-spacing="1.4">'
        f"TRAILING 52 WEEKS &#183; {year_total} EVENTS LOGGED</text>\n  "
        + "\n  ".join(labels)
        + dow_labels
        + "\n  "
        + "\n  ".join(squares)
        + f'\n  <text x="{W - 210}" y="{H-24}" font-size="10" fill="{DIM}" text-anchor="end">LOW</text>'
        + legend
        + f'\n  <text x="{W - 26}" y="{H-24}" font-size="10" fill="{DIM}" text-anchor="end">HIGH</text>'
    )
    return svg(W, H, "Contribution heatmap", body)


def nice_ceiling(v: int) -> int:
    """Round an axis maximum up to a readable 1/1.2/1.5/2/2.5/3/4/5/6/8 x 10^n."""
    if v <= 5:
        return 5
    mag = 10 ** int(math.log10(v))
    for m in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if mag * m >= v:
            return int(mag * m)
    return int(mag * 10)


def card_telemetry(data: dict) -> str:
    days = data["days"]
    window = sorted(days)[-90:]
    series = [days[d] for d in window]
    if not series:
        series, window = [0], [dt.date.today().isoformat()]

    W, H = 1000, 240
    left, right, top, bottom = 62, W - 30, 84, 196
    axis = nice_ceiling(max(series) or 1)
    step = (right - left) / max(len(series) - 1, 1)

    def px(i: int) -> float:
        return left + i * step

    def py(v: int) -> float:
        return bottom - (v / axis) * (bottom - top)

    line = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(series))
    area = f"{left},{bottom} {line} {px(len(series)-1):.1f},{bottom}"

    grid = ""
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        y = bottom - frac * (bottom - top)
        grid += (
            f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="{LINE}" '
            f'stroke-width="1" stroke-dasharray="3 5"/>'
            f'<text x="{left-10}" y="{y+4:.1f}" font-size="9.5" fill="{DIM}" text-anchor="end">'
            f"{int(axis*frac)}</text>"
        )

    ticks = ""
    last_month = None
    for i, iso in enumerate(window):
        d = dt.date.fromisoformat(iso)
        if d.month != last_month:
            last_month = d.month
            ticks += (
                f'<line x1="{px(i):.1f}" y1="{bottom}" x2="{px(i):.1f}" y2="{bottom+5}" '
                f'stroke="{LINE2}" stroke-width="1"/>'
                f'<text x="{px(i):.1f}" y="{bottom+18}" font-size="9.5" fill="{DIM}" '
                f'text-anchor="middle" letter-spacing="1">{d.strftime("%b").upper()}</text>'
            )

    hi = series.index(max(series))
    total = sum(series)

    body = f"""{frame(W, H, "TL", "CONTRIBUTION TELEMETRY", "xfOS/0x05")}
  <defs>
    <linearGradient id="areaTL" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{CYAN}" stop-opacity="0.34"/>
      <stop offset="100%" stop-color="{CYAN}" stop-opacity="0.02"/>
    </linearGradient>
  </defs>
  <text x="26" y="54" font-size="10.5" fill="{DIM}" letter-spacing="1.4">TRAILING 90 DAYS &#183; {total} EVENTS &#183; PEAK {max(series)} ON {nice_date(window[hi])}</text>
  {grid}
  <polygon points="{area}" fill="url(#areaTL)"/>
  <polyline points="{line}" fill="none" stroke="{CYAN}" stroke-width="1.8" stroke-linejoin="round"/>
  <line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="{LINE2}" stroke-width="1.2"/>
  {ticks}
  <circle cx="{px(hi):.1f}" cy="{py(series[hi]):.1f}" r="4" fill="{AMBER}"/>
  <circle cx="{px(hi):.1f}" cy="{py(series[hi]):.1f}" r="4" fill="none" stroke="{AMBER}" stroke-width="1.5">
    <animate attributeName="r" values="4;11;4" dur="2.4s" repeatCount="indefinite"/>
    <animate attributeName="stroke-opacity" values="0.9;0;0.9" dur="2.4s" repeatCount="indefinite"/>
  </circle>
  <line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="{CYAN}" stroke-width="1" stroke-opacity="0.45">
    <animate attributeName="x1" values="{left};{right};{left}" dur="11s" repeatCount="indefinite"/>
    <animate attributeName="x2" values="{left};{right};{left}" dur="11s" repeatCount="indefinite"/>
  </line>
  <text x="{right}" y="{top-10}" font-size="9.5" fill="{DIM}" text-anchor="end" letter-spacing="1.2">EVENTS / DAY</text>"""
    return svg(W, H, "Contribution telemetry", body)


def wrap(text: str, width: int, lines: int) -> list[str]:
    out: list[str] = []
    words = text.split()
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= width:
            cur = candidate
            continue
        out.append(cur)
        cur = w
        if len(out) == lines:
            break
    if cur and len(out) < lines:
        out.append(cur)
    if len(out) == lines and len(" ".join(out)) < len(text):
        out[-1] = out[-1][: width - 1].rstrip() + "…"
    return out


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def card_repo(repo: dict, index: int) -> str:
    W, H = 490, 150
    name = repo["name"]
    desc = repo["description"] or "No description on file."
    lang = (repo["primaryLanguage"] or {}).get("name") or "MIXED"
    pushed = dt.datetime.fromisoformat(repo["pushedAt"].replace("Z", "+00:00"))
    topics = [t["topic"]["name"] for t in repo["repositoryTopics"]["nodes"]]

    desc_lines = "".join(
        f'<text x="26" y="{88 + i*17}" font-size="11.5" fill="{DIM}">{esc(line)}</text>'
        for i, line in enumerate(wrap(desc, 52, 2))
    )
    tag_x = 26
    tags = ""
    for t in topics[:3]:
        tw = 14 + len(t) * 6.6
        if tag_x + tw > W - 26:
            break
        tags += (
            f'<rect x="{tag_x}" y="118" width="{tw:.0f}" height="16" fill="{CYAN}" fill-opacity="0.07" '
            f'stroke="{LINE}" stroke-width="1"/>'
            f'<text x="{tag_x + 7}" y="130" font-size="9.5" fill="{CYAND}">{esc(t)}</text>'
        )
        tag_x += tw + 6

    body = f"""{frame(W, H, f"R{index}", "&#9656; " + esc(name.upper())[:26], lang.upper())}
  <text x="26" y="58" font-size="10" fill="{DIM}" letter-spacing="1.4">LAST WRITE {pushed.strftime('%Y.%m.%d')}</text>
  <text x="{W-26}" y="58" font-size="10" fill="{AMBER}" text-anchor="end" letter-spacing="1.2">STARS {repo['stargazerCount']:03d} &#183; FORKS {repo['forkCount']:03d}</text>
  <line x1="26" y1="68" x2="{W-26}" y2="68" stroke="{LINE}" stroke-width="1"/>
  {desc_lines}
  {tags}"""
    return svg(W, H, f"{name} repository card", body)


# ------------------------------------------------------------------- main --
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("xfOS_USER", "XaviFortes"))
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("METRICS_TOKEN")
    if not token:
        print("error: set GITHUB_TOKEN (or METRICS_TOKEN)", file=sys.stderr)
        return 1

    try:
        data = collect(token, args.user)
    except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError) as e:
        print(f"error: GitHub API request failed: {e}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    for name, render in (
        ("stats", card_stats),
        ("streak", card_streak),
        ("languages", card_languages),
        ("heatmap", card_heatmap),
        ("telemetry", card_telemetry),
    ):
        path = OUT / f"{name}.svg"
        path.write_text(render(data))
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} B)")

    for i, repo in enumerate(data["featured"]):
        path = OUT / f"repo-{repo['name'].lower()}.svg"
        path.write_text(card_repo(repo, i))
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
