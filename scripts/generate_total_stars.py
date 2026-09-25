import os
import json
import math
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path


USERNAME = os.environ.get("GITHUB_USERNAME", "htyjers")
TOKEN = os.environ.get("GITHUB_TOKEN")

OUTPUT = Path("assets/total-stars.svg")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)


def github_request(url, accept="application/vnd.github+json"):
    headers = {
        "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "total-star-history",
    }

    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def get_original_repositories():
    repos = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/users/{USERNAME}/repos"
            f"?type=owner&sort=created&direction=asc"
            f"&per_page=100&page={page}"
        )

        data = github_request(url)

        if not data:
            break

        for repo in data:
            # Only count original public repositories.
            # Exclude forks and the profile README repository itself.
            if repo["fork"]:
                continue

            if repo["name"].lower() == USERNAME.lower():
                continue

            repos.append(repo)

        if len(data) < 100:
            break

        page += 1

    return repos


def get_star_timestamps(repo_name):
    timestamps = []
    page = 1

    while True:
        encoded_repo = urllib.parse.quote(repo_name, safe="/")

        url = (
            f"https://api.github.com/repos/{encoded_repo}/stargazers"
            f"?per_page=100&page={page}"
        )

        data = github_request(
            url,
            accept="application/vnd.github.star+json"
        )

        if not data:
            break

        for star in data:
            timestamp = star.get("starred_at")

            if timestamp:
                timestamps.append(
                    datetime.fromisoformat(
                        timestamp.replace("Z", "+00:00")
                    )
                )

        if len(data) < 100:
            break

        page += 1

    return timestamps


def collect_star_history():
    repos = get_original_repositories()

    all_stars = []

    print(f"Found {len(repos)} original repositories.")

    for repo in repos:
        full_name = repo["full_name"]

        print(
            f"{full_name}: "
            f"{repo['stargazers_count']} current stars"
        )

        stars = get_star_timestamps(full_name)
        all_stars.extend(stars)

    all_stars.sort()

    return repos, all_stars


def monthly_history(stars):
    if not stars:
        return []

    first = stars[0]
    now = datetime.now(timezone.utc)

    start_year = first.year
    start_month = first.month

    year = start_year
    month = start_month

    monthly_counts = Counter(
        (star.year, star.month) for star in stars
    )

    history = []
    cumulative = 0

    while (year, month) <= (now.year, now.month):
        cumulative += monthly_counts[(year, month)]

        history.append(
            (
                datetime(
                    year,
                    month,
                    1,
                    tzinfo=timezone.utc
                ),
                cumulative,
            )
        )

        month += 1

        if month == 13:
            month = 1
            year += 1

    return history


def nice_max(value):
    if value <= 10:
        return 10

    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude

    if normalized <= 1:
        top = 1
    elif normalized <= 2:
        top = 2
    elif normalized <= 5:
        top = 5
    else:
        top = 10

    return top * magnitude


def make_svg(history, repo_count):
    width = 1000
    height = 430

    left = 82
    right = 35
    top = 55
    bottom = 70

    chart_width = width - left - right
    chart_height = height - top - bottom

    total = history[-1][1] if history else 0
    y_max = nice_max(max(total, 1))

    if len(history) <= 1:
        x_positions = [left]
    else:
        x_positions = [
            left + i * chart_width / (len(history) - 1)
            for i in range(len(history))
        ]

    points = []

    for x, (_, value) in zip(x_positions, history):
        y = top + chart_height * (1 - value / y_max)
        points.append((x, y))

    path = ""

    for i, (x, y) in enumerate(points):
        if i == 0:
            path += f"M {x:.2f} {y:.2f}"
        else:
            path += f" L {x:.2f} {y:.2f}"

    # Area below line
    area_path = path

    if points:
        area_path += (
            f" L {points[-1][0]:.2f} {top + chart_height:.2f}"
            f" L {points[0][0]:.2f} {top + chart_height:.2f} Z"
        )

    # Y-axis ticks
    y_ticks = []

    for i in range(5):
        value = y_max * i / 4
        y = top + chart_height * (1 - i / 4)

        y_ticks.append(
            f"""
            <line
                x1="{left}"
                y1="{y:.2f}"
                x2="{width-right}"
                y2="{y:.2f}"
                class="grid"
            />

            <text
                x="{left-15}"
                y="{y+5:.2f}"
                text-anchor="end"
                class="axis"
            >
                {int(value)}
            </text>
            """
        )

    # Year labels
    year_positions = {}

    for i, (date, _) in enumerate(history):
        if date.year not in year_positions:
            year_positions[date.year] = x_positions[i]

    year_labels = []

    for year, x in year_positions.items():
        year_labels.append(
            f"""
            <text
                x="{x:.2f}"
                y="{height-28}"
                text-anchor="middle"
                class="axis"
            >
                {year}
            </text>
            """
        )

    last_point = ""

    if points:
        x, y = points[-1]

        last_point = f"""
        <circle
            cx="{x:.2f}"
            cy="{y:.2f}"
            r="5"
            class="dot"
        />
        """

    svg = f"""
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="{width}"
    height="{height}"
    viewBox="0 0 {width} {height}"
    role="img"
    aria-label="Total GitHub stars history"
>

<style>

    .background {{
        fill: #ffffff;
    }}

    .title {{
        fill: #24292f;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Helvetica,
            Arial,
            sans-serif;
        font-size: 22px;
        font-weight: 600;
    }}

    .subtitle {{
        fill: #57606a;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Helvetica,
            Arial,
            sans-serif;
        font-size: 14px;
    }}

    .axis {{
        fill: #57606a;
        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "Segoe UI",
            Helvetica,
            Arial,
            sans-serif;
        font-size: 13px;
    }}

    .grid {{
        stroke: #d8dee4;
        stroke-width: 1;
    }}

    .line {{
        fill: none;
        stroke: #0969da;
        stroke-width: 3;
        stroke-linejoin: round;
        stroke-linecap: round;
    }}

    .area {{
        fill: url(#gradient);
    }}

    .dot {{
        fill: #0969da;
        stroke: #ffffff;
        stroke-width: 2;
    }}

    @media (prefers-color-scheme: dark) {{

        .background {{
            fill: #0d1117;
        }}

        .title {{
            fill: #f0f6fc;
        }}

        .subtitle,
        .axis {{
            fill: #8b949e;
        }}

        .grid {{
            stroke: #30363d;
        }}

        .line {{
            stroke: #58a6ff;
        }}

        .dot {{
            fill: #58a6ff;
            stroke: #0d1117;
        }}
    }}

</style>

<defs>

    <linearGradient
        id="gradient"
        x1="0"
        y1="0"
        x2="0"
        y2="1"
    >

        <stop
            offset="0%"
            stop-color="#0969da"
            stop-opacity="0.20"
        />

        <stop
            offset="100%"
            stop-color="#0969da"
            stop-opacity="0.01"
        />

    </linearGradient>

</defs>

<rect
    class="background"
    x="0"
    y="0"
    width="{width}"
    height="{height}"
    rx="12"
/>

<text
    x="{left}"
    y="28"
    class="title"
>
    Total GitHub Stars
</text>

<text
    x="{width-right}"
    y="28"
    text-anchor="end"
    class="subtitle"
>
    {total} stars · {repo_count} repositories
</text>

{''.join(y_ticks)}

{''.join(year_labels)}

<path
    d="{area_path}"
    class="area"
/>

<path
    d="{path}"
    class="line"
/>

{last_point}

</svg>
"""

    return svg.strip()


def main():
    repos, stars = collect_star_history()

    history = monthly_history(stars)

    svg = make_svg(
        history,
        repo_count=len(repos)
    )

    OUTPUT.write_text(
        svg,
        encoding="utf-8"
    )

    print(
        f"Generated {OUTPUT}: "
        f"{len(stars)} total historical stars."
    )


if __name__ == "__main__":
    main()
