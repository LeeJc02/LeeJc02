#!/usr/bin/env python3
"""Generate a self-hosted SVG telemetry card for a GitHub profile README."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen


QUERY = """
query ProfileTelemetry($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(
      first: 100
      ownerAffiliations: OWNER
      isFork: false
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      contributionCalendar { totalContributions }
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
    }
  }
}
"""

FALLBACK_COLORS = ["#38BDF8", "#A78BFA", "#67E8F9", "#818CF8", "#2DD4BF"]


def fetch_profile(token: str, username: str) -> dict:
    payload = json.dumps({"query": QUERY, "variables": {"login": username}}).encode()
    request = Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "LeeJc02-profile-telemetry",
        },
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(result["errors"][0]["message"])
    return result["data"]["user"]


def compact_number(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(value)


def language_mix(repositories: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}
    for repository in repositories:
        for edge in repository["languages"]["edges"]:
            language = edge["node"]
            current = totals.setdefault(
                language["name"],
                {"name": language["name"], "color": language["color"], "size": 0},
            )
            current["size"] += edge["size"]
    ranked = sorted(totals.values(), key=lambda item: item["size"], reverse=True)[:5]
    total_size = sum(item["size"] for item in ranked) or 1
    for index, item in enumerate(ranked):
        item["color"] = item["color"] or FALLBACK_COLORS[index]
        item["share"] = item["size"] / total_size
    return ranked


def render_svg(username: str, profile: dict) -> str:
    repositories = profile["repositories"]["nodes"]
    contributions = profile["contributionsCollection"]
    languages = language_mix(repositories)
    stars = sum(repository["stargazerCount"] for repository in repositories)
    stat_cards = [
        ("REPOSITORIES", profile["repositories"]["totalCount"], "owned / public"),
        ("TOTAL STARS", stars, "across systems"),
        ("FOLLOWERS", profile["followers"]["totalCount"], "signal network"),
        (
            "CONTRIBUTIONS",
            contributions["contributionCalendar"]["totalContributions"],
            "rolling 12 months",
        ),
    ]

    cards = []
    for index, (label, value, note) in enumerate(stat_cards):
        x = 42 + index * 281
        cards.append(
            f"""
      <g transform="translate({x} 62)">
        <rect width="257" height="102" rx="14" fill="#0B1220" fill-opacity="0.72" stroke="#38BDF8" stroke-opacity="0.13"/>
        <text x="18" y="27" fill="#64748B" font-size="10" letter-spacing="1.5">{label}</text>
        <text x="18" y="67" fill="#E2E8F0" font-size="31" font-weight="700">{compact_number(value)}</text>
        <text x="237" y="68" text-anchor="end" fill="#475569" font-size="9">{note}</text>
      </g>"""
        )

    bars = []
    legends = []
    bar_x = 42.0
    bar_width = 720.0
    legend_x = 42
    for index, language in enumerate(languages):
        width = max(language["share"] * bar_width, 5)
        bars.append(
            f'<rect class="meter meter-{index + 1}" x="{bar_x:.1f}" y="218" width="{width:.1f}" height="12" rx="6" fill="{language["color"]}"/>'
        )
        percentage = round(language["share"] * 100)
        legends.append(
            f'<circle cx="{legend_x}" cy="260" r="4" fill="{language["color"]}"/><text x="{legend_x + 11}" y="264" fill="#94A3B8" font-size="10">{language["name"]} {percentage}%</text>'
        )
        legend_x += 128
        bar_x += width + 3

    activity = [
        ("COMMITS", contributions["totalCommitContributions"]),
        ("PULL REQUESTS", contributions["totalPullRequestContributions"]),
        ("REVIEWS", contributions["totalPullRequestReviewContributions"]),
        ("ISSUES", contributions["totalIssueContributions"]),
    ]
    activity_rows = []
    for index, (label, value) in enumerate(activity):
        y = 207 + index * 20
        activity_rows.append(
            f'<text x="835" y="{y}" fill="#64748B" font-size="9" letter-spacing="1">{label}</text>'
            f'<text x="1138" y="{y}" text-anchor="end" fill="#CBD5E1" font-size="11">{value}</text>'
            f'<path d="M955 {y - 4}H1110" stroke="#1E293B" stroke-dasharray="2 5"/>'
        )

    return f"""<svg width="1200" height="300" viewBox="0 0 1200 300" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">{username} GitHub telemetry</title>
  <desc id="desc">Repository, star, follower, contribution, language, and activity data generated daily from GitHub.</desc>
  <style>
    .meter {{ animation: reveal 1.2s cubic-bezier(.2,.8,.2,1) both; transform-box: fill-box; transform-origin: left; }}
    .meter-2 {{ animation-delay: .08s; }} .meter-3 {{ animation-delay: .16s; }}
    .meter-4 {{ animation-delay: .24s; }} .meter-5 {{ animation-delay: .32s; }}
    .live {{ animation: live 2.2s ease-in-out infinite; }}
    @keyframes reveal {{ from {{ transform: scaleX(0); opacity: 0; }} to {{ transform: scaleX(1); opacity: 1; }} }}
    @keyframes live {{ 0%,100% {{ opacity:.35; }} 50% {{ opacity:1; }} }}
    @media (prefers-reduced-motion: reduce) {{ .meter, .live {{ animation: none; }} }}
  </style>
  <defs>
    <linearGradient id="bg" x1="30" y1="0" x2="1160" y2="300" gradientUnits="userSpaceOnUse">
      <stop stop-color="#07131D"/><stop offset=".55" stop-color="#0A1019"/><stop offset="1" stop-color="#120B20"/>
    </linearGradient>
    <linearGradient id="edge" x1="0" y1="0" x2="1200" y2="0" gradientUnits="userSpaceOnUse">
      <stop stop-color="#38BDF8"/><stop offset=".5" stop-color="#38BDF8" stop-opacity=".14"/><stop offset="1" stop-color="#A78BFA"/>
    </linearGradient>
  </defs>
  <rect x=".5" y=".5" width="1199" height="299" rx="18.5" fill="url(#bg)" stroke="url(#edge)" stroke-opacity=".42"/>
  <g font-family="ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace">
    <circle class="live" cx="43" cy="31" r="4" fill="#22C55E"/>
    <text x="56" y="35" fill="#86EFAC" font-size="10" letter-spacing="1.5">LIVE TELEMETRY</text>
    <text x="1160" y="35" text-anchor="end" fill="#475569" font-size="9" letter-spacing="1.3">AUTO-GENERATED / GITHUB ACTIONS</text>
    {''.join(cards)}
    <text x="42" y="199" fill="#64748B" font-size="10" letter-spacing="1.5">LANGUAGE MIX / TOP 5</text>
    {''.join(bars)}
    {''.join(legends)}
    <path d="M800 190V273" stroke="#1E293B"/>
    <text x="835" y="185" fill="#64748B" font-size="10" letter-spacing="1.5">ACTIVITY / ROLLING YEAR</text>
    {''.join(activity_rows)}
  </g>
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "LeeJc02"))
    parser.add_argument("--output", type=Path, default=Path("dist/telemetry.svg"))
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    profile = fetch_profile(token, args.username)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_svg(args.username, profile), encoding="utf-8")


if __name__ == "__main__":
    main()
