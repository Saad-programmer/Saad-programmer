#!/usr/bin/env python3
"""
Reads the owner's public GitHub data (repos, languages, topics, events)
and rewrites the dynamic sections of README.md between the markers:

    <!--START_STATS--> ... <!--END_STATS-->
    <!--START_TECH-->  ... <!--END_TECH-->
    <!--START_PROJECTS--> ... <!--END_PROJECTS-->
    <!--START_RECENT-->   ... <!--END_RECENT-->
    <!--START_ACTIVITY--> ... <!--END_ACTIVITY-->

Standard library only. Runs inside GitHub Actions with the default GITHUB_TOKEN.
"""
import json
import os
import re
import urllib.request
from collections import Counter
from pathlib import Path

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Saad-programmer"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
README = Path(os.environ.get("README_PATH", "README.md"))
MAX_PROJECTS = 6
MAX_RECENT = 5
MAX_EVENTS = 6

# GitHub language name -> skillicons.dev id
LANG_ICONS = {
    "JavaScript": "js", "TypeScript": "ts", "Python": "py", "Java": "java",
    "C": "c", "C++": "cpp", "C#": "cs", "PHP": "php", "HTML": "html",
    "CSS": "css", "SCSS": "sass", "Shell": "bash", "Go": "go", "Rust": "rust",
    "Kotlin": "kotlin", "Dart": "dart", "Vue": "vue", "Swift": "swift",
    "Ruby": "ruby", "Lua": "lua", "Dockerfile": "docker", "PLpgSQL": "postgres",
    "Svelte": "svelte", "R": "r", "MATLAB": "matlab", "Assembly": "asm",
}

# repo topic -> skillicons.dev id
TOPIC_ICONS = {
    "react": "react", "reactjs": "react", "nextjs": "next", "next-js": "next",
    "nodejs": "nodejs", "node": "nodejs", "express": "express", "expressjs": "express",
    "tailwindcss": "tailwind", "tailwind": "tailwind", "bootstrap": "bootstrap",
    "docker": "docker", "kubernetes": "kubernetes", "mongodb": "mongodb",
    "mysql": "mysql", "postgresql": "postgres", "postgres": "postgres",
    "redis": "redis", "firebase": "firebase", "flutter": "flutter",
    "laravel": "laravel", "django": "django", "flask": "flask",
    "fastapi": "fastapi", "spring": "spring", "spring-boot": "spring",
    "springboot": "spring", "angular": "angular", "vue": "vue", "vuejs": "vue",
    "svelte": "svelte", "nestjs": "nestjs", "git": "git", "linux": "linux",
    "figma": "figma", "tensorflow": "tensorflow", "pytorch": "pytorch",
    "opencv": "opencv", "vite": "vite", "sass": "sass", "graphql": "graphql",
    "aws": "aws", "azure": "azure", "githubactions": "githubactions",
    "github-actions": "githubactions", "nginx": "nginx", "sqlite": "sqlite",
    "unity": "unity", "dotnet": "dotnet", "arduino": "arduino", "jquery": "jquery",
}


def api(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-updater",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def all_repos():
    repos, page = [], 1
    while True:
        batch = api(
            f"https://api.github.com/users/{USER}/repos"
            f"?per_page=100&page={page}&type=owner&sort=pushed"
        )
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    return [
        r for r in repos
        if not r["fork"] and not r["archived"] and r["name"].lower() != USER.lower()
    ]


def replace(text, name, content):
    pattern = re.compile(
        rf"(<!--START_{name}-->).*?(<!--END_{name}-->)", re.DOTALL
    )
    if not pattern.search(text):
        print(f"! marker {name} not found, skipped")
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(2)}", text)


def badge(label, value, color):
    label = label.replace("-", "--").replace(" ", "%20")
    value = str(value).replace("-", "--").replace(" ", "%20")
    return (
        f'<img src="https://img.shields.io/badge/{label}-{value}-{color}'
        f'?style=for-the-badge&labelColor=0D1117" alt="{label}"/>'
    )


def build_stats(repos):
    stars = sum(r["stargazers_count"] for r in repos)
    forks = sum(r["forks_count"] for r in repos)
    langs = Counter(r["language"] for r in repos if r["language"])
    top = langs.most_common(1)[0][0] if langs else "N/A"
    return (
        '<div align="center">\n\n'
        + " ".join([
            badge("Public Repos", len(repos), "8B5CF6"),
            badge("Total Stars", stars, "EC4899"),
            badge("Total Forks", forks, "06B6D4"),
            badge("Top Language", top, "22C55E"),
        ])
        + "\n\n</div>"
    )


def build_tech(repos):
    bytes_by_lang = Counter()
    for r in repos[:40]:
        try:
            for lang, size in api(r["languages_url"]).items():
                bytes_by_lang[lang] += size
        except Exception as exc:  # noqa: BLE001
            print(f"! languages failed for {r['name']}: {exc}")

    langs = [l for l, _ in bytes_by_lang.most_common(14)]
    lang_icons = []
    for l in langs:
        icon = LANG_ICONS.get(l)
        if icon and icon not in lang_icons:
            lang_icons.append(icon)

    topics = Counter(t for r in repos for t in r.get("topics", []))
    tool_icons = []
    for t, _ in topics.most_common():
        icon = TOPIC_ICONS.get(t.lower())
        if icon and icon not in tool_icons and icon not in lang_icons:
            tool_icons.append(icon)

    out = ['<div align="center">\n']
    if lang_icons:
        out.append("**Languages (from my repos)**\n")
        out.append(
            f'<img src="https://skillicons.dev/icons?i={",".join(lang_icons)}'
            f'&perline=8" alt="languages"/>\n'
        )
    if tool_icons:
        out.append("**Frameworks & tools (from repo topics)**\n")
        out.append(
            f'<img src="https://skillicons.dev/icons?i={",".join(tool_icons)}'
            f'&perline=8" alt="tools"/>\n'
        )
    if not lang_icons and not tool_icons:
        out.append("_Push some code and this section fills itself in._\n")
    out.append("</div>")
    return "\n".join(out)


def build_projects(repos):
    ranked = sorted(
        repos, key=lambda r: (r["stargazers_count"], r["pushed_at"]), reverse=True
    )[:MAX_PROJECTS]
    if not ranked:
        return "_No public projects yet. They'll appear here automatically._"
    cards = []
    for r in ranked:
        cards.append(
            f'<a href="{r["html_url"]}"><img width="48%" '
            f'src="https://github-readme-stats.vercel.app/api/pin/?username={USER}'
            f'&repo={r["name"]}&theme=tokyonight&hide_border=true&bg_color=0D1117'
            f'&title_color=A78BFA&icon_color=EC4899" alt="{r["name"]}"/></a>'
        )
    return '<div align="center">\n\n' + "\n".join(cards) + "\n\n</div>"


def build_recent(repos):
    recent = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:MAX_RECENT]
    if not recent:
        return "_Nothing here yet._"
    rows = ["| Repository | Description | Language | ⭐ | Updated |",
            "|---|---|---|---|---|"]
    for r in recent:
        desc = (r["description"] or "—").replace("|", "\\|")
        rows.append(
            f'| [**{r["name"]}**]({r["html_url"]}) | {desc} | '
            f'{r["language"] or "—"} | {r["stargazers_count"]} | {r["pushed_at"][:10]} |'
        )
    return "\n".join(rows)


def build_activity():
    try:
        events = api(f"https://api.github.com/users/{USER}/events/public?per_page=50")
    except Exception as exc:  # noqa: BLE001
        print(f"! events failed: {exc}")
        return "_Activity unavailable right now._"

    lines = []
    for e in events:
        repo = e["repo"]["name"]
        link = f"[{repo}](https://github.com/{repo})"
        day = e["created_at"][:10]
        t, p = e["type"], e.get("payload", {})
        if t == "PushEvent":
            lines.append(f"- ⬆️ Pushed code to {link} · `{day}`")
        elif t == "CreateEvent" and p.get("ref_type") == "repository":
            lines.append(f"- 🆕 Created repository {link} · `{day}`")
        elif t == "PullRequestEvent":
            lines.append(f"- 🔀 {p.get('action', 'updated').capitalize()} a pull request in {link} · `{day}`")
        elif t == "IssuesEvent":
            lines.append(f"- 🐛 {p.get('action', 'updated').capitalize()} an issue in {link} · `{day}`")
        elif t == "WatchEvent":
            lines.append(f"- ⭐ Starred {link} · `{day}`")
        elif t == "ForkEvent":
            lines.append(f"- 🍴 Forked {link} · `{day}`")
        if len(lines) >= MAX_EVENTS:
            break
    return "\n".join(lines) if lines else "_No recent public activity._"


def main():
    repos = all_repos()
    print(f"Found {len(repos)} eligible repos for {USER}")

    text = README.read_text(encoding="utf-8")
    text = replace(text, "STATS", build_stats(repos))
    text = replace(text, "TECH", build_tech(repos))
    text = replace(text, "PROJECTS", build_projects(repos))
    text = replace(text, "RECENT", build_recent(repos))
    text = replace(text, "ACTIVITY", build_activity())
    README.write_text(text, encoding="utf-8")
    print("README updated")


if __name__ == "__main__":
    main()
