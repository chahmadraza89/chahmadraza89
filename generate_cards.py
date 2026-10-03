#!/usr/bin/env python3
"""
Generates two SVG cards that match the look of github-profile-summary-cards
(transparent background, #58a6ff titles, #8b949e text) but with accurate data:

  * stats.svg      - Total Stars / Commits / PRs / Issues / Contributed to
  * top-langs.svg  - "Top Languages by Commit", up to 5 languages

Data comes straight from the GitHub GraphQL API using your own token, so
private repositories and private contributions are counted too.

Usage:
    GH_TOKEN=xxxx python generate_cards.py --user chahmadraza89 --out profile-cards
    python generate_cards.py --demo --out /tmp/cards      # no network, sample data
"""
import argparse
import datetime as dt
import json
import os
import urllib.request

API = "https://api.github.com/graphql"

# ---- style (same palette as your current README URLs) -----------------------
TITLE = "#58a6ff"
TEXT = "#8b949e"
ICON = "#58a6ff"
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MAX_LANGS = 5
W, H = 340, 195


# ---- GitHub API -------------------------------------------------------------
def gql(token, query, variables):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


PROFILE_Q = """
query($login:String!, $cursor:String) {
  user(login:$login) {
    createdAt
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(first:1,
      contributionTypes:[COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    repositories(ownerAffiliations:OWNER, isFork:false, first:100, after:$cursor) {
      nodes { stargazerCount }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""

YEAR_Q = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      totalCommitContributions
      restrictedContributionsCount
      commitContributionsByRepository(maxRepositories:100) {
        repository { primaryLanguage { name color } }
        contributions { totalCount }
      }
    }
  }
}"""


def fetch(login, token):
    stars, cursor = 0, None
    while True:
        u = gql(token, PROFILE_Q, {"login": login, "cursor": cursor})["user"]
        stars += sum(n["stargazerCount"] for n in u["repositories"]["nodes"])
        pi = u["repositories"]["pageInfo"]
        if not pi["hasNextPage"]:
            break
        cursor = pi["endCursor"]

    created = dt.datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)
    commits = 0
    langs = {}  # name -> [commit count, color]
    for year in range(created.year, now.year + 1):
        frm = dt.datetime(year, 1, 1, tzinfo=dt.timezone.utc)
        to = min(dt.datetime(year, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc), now)
        c = gql(token, YEAR_Q, {"login": login, "from": frm.isoformat(), "to": to.isoformat()})
        c = c["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        for item in c["commitContributionsByRepository"]:
            lang = item["repository"]["primaryLanguage"]
            if not lang:
                continue
            entry = langs.setdefault(lang["name"], [0, lang["color"] or "#8b949e"])
            entry[0] += item["contributions"]["totalCount"]

    top = sorted(langs.items(), key=lambda kv: kv[1][0], reverse=True)[:MAX_LANGS]
    return {
        "stars": stars,
        "commits": commits,
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "contributed": u["repositoriesContributedTo"]["totalCount"],
        "langs": [(name, v[0], v[1]) for name, v in top],
    }


def demo_data():
    return {
        "stars": 24, "commits": 212, "prs": 9, "issues": 4, "contributed": 13,
        "langs": [("Jupyter Notebook", 90, "#DA5B0B"), ("Dart", 70, "#00B4AB"),
                  ("Python", 28, "#3572A5"), ("C++", 14, "#f34b7d"),
                  ("JavaScript", 10, "#f1e05a")],
    }


# ---- SVG rendering ----------------------------------------------------------
def svg_wrap(body, title_id):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" fill="none" role="img" aria-labelledby="{title_id}">\n'
        f'<style>text{{font-family:{FONT}}}'
        f'.t{{font-size:18px;font-weight:600;fill:{TITLE}}}'
        f'.l{{font-size:13px;fill:{TEXT}}}'
        f'.v{{font-size:13px;font-weight:600;fill:{TEXT}}}</style>\n{body}\n</svg>\n'
    )


# 16x16 outline icons drawn with strokes
ICONS = {
    "star": '<path d="M8 1.5l1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.3l-3.8 2 .7-4.3-3.1-3 4.3-.6z" '
            'stroke-linejoin="round"/>',
    "commit": '<circle cx="8" cy="8" r="3"/><path d="M1 8h4M11 8h4"/>',
    "pr": '<circle cx="4" cy="3.5" r="1.6"/><circle cx="4" cy="12.5" r="1.6"/>'
          '<circle cx="12" cy="12.5" r="1.6"/><path d="M4 5.1v5.8M12 10.9V6a2 2 0 00-2-2H8.5'
          'M10 2.2L8.3 4 10 5.8" stroke-linejoin="round" stroke-linecap="round"/>',
    "issue": '<circle cx="8" cy="8" r="6.2"/><path d="M8 4.6v4" stroke-linecap="round"/>'
             '<circle cx="8" cy="11.1" r=".6" fill="currentColor" stroke="none"/>',
    "repo": '<path d="M3.5 12.5V2.5a1 1 0 011-1h8v10h-8a1 1 0 00-1 1 1 1 0 001 1h8M10 1.5v5l-1.5-1.2'
            'L7 6.5v-5" stroke-linejoin="round"/>',
}

MARK_GITHUB = (
    "M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49"
    "-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 "
    "1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59"
    ".82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 "
    "1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 "
    "3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42"
    "-3.58-8-8-8z"
)


def stats_svg(d):
    rows = [
        ("star", "Total Stars:", d["stars"]),
        ("commit", "Total Commits:", d["commits"]),
        ("pr", "Total PRs:", d["prs"]),
        ("issue", "Total Issues:", d["issues"]),
        ("repo", "Contributed to:", d["contributed"]),
    ]
    out = [f'<title id="stats-title">GitHub stats</title>',
           f'<text x="25" y="34" class="t">Stats</text>']
    for i, (icon, label, val) in enumerate(rows):
        y = 52 + i * 26
        out.append(
            f'<g transform="translate(25 {y})" stroke="{ICON}" stroke-width="1.4" '
            f'color="{ICON}">{ICONS[icon]}</g>'
        )
        out.append(f'<text x="48" y="{y + 12}" class="l">{label}</text>')
        out.append(f'<text x="152" y="{y + 12}" class="v">{val:,}</text>')
    # GitHub mark, 96px, right side
    out.append(
        f'<g transform="translate(230 55) scale(6)"><path d="{MARK_GITHUB}" fill="{ICON}"/></g>'
    )
    return svg_wrap("\n".join(out), "stats-title")


def langs_svg(d):
    langs = d["langs"][:MAX_LANGS]
    total = sum(c for _, c, _ in langs) or 1
    out = ['<title id="langs-title">Top languages by commit</title>',
           '<text x="25" y="34" class="t">Top Languages by Commit</text>']
    # legend
    for i, (name, _, color) in enumerate(langs):
        y = 56 + i * 24
        out.append(f'<rect x="25" y="{y}" width="12" height="12" fill="{color}"/>')
        out.append(f'<text x="43" y="{y + 11}" class="l">{name}</text>')
    # donut (stroke-dasharray segments, start at 12 o'clock)
    import math
    cx, cy, r, sw = 262, 112, 46, 22
    circ = 2 * math.pi * r
    offset = 0.0
    for name, count, color in langs:
        seg = circ * count / total
        out.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{color}" stroke-width="{sw}" '
            f'stroke-dasharray="{seg:.2f} {circ - seg:.2f}" stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        offset += seg
    return svg_wrap("\n".join(out), "langs-title")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GH_USER", "chahmadraza89"))
    ap.add_argument("--out", default="profile-cards")
    ap.add_argument("--demo", action="store_true", help="use sample data, no network")
    a = ap.parse_args()

    if a.demo:
        data = demo_data()
    else:
        token = os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("Set GH_TOKEN (classic PAT with read:user + repo scopes).")
        data = fetch(a.user, token)

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "stats.svg"), "w") as f:
        f.write(stats_svg(data))
    with open(os.path.join(a.out, "top-langs.svg"), "w") as f:
        f.write(langs_svg(data))
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
