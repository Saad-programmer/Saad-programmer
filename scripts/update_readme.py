#!/usr/bin/env python3
"""
Reads the owner's public GitHub data and rewrites the dynamic sections of
README.md between these markers:

    STATS     badges (repos, stars, C/C++ repos, systems share)
    FOCUS     language focus bars, ranked by number of repos, systems first
    TECH      icon rows: systems core + other tools
    PROJECTS  featured repos, systems projects (C / C++ / ASM / Rust) first
    RECENT    most recently pushed repos
    ACTIVITY  latest public events

Web markup languages (CSS, HTML, SCSS) are deliberately NOT counted as a
"main language": they describe pages, not engineering depth. Standard library
only. Runs inside GitHub Actions with the default GITHUB_TOKEN.
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

# Languages that count as "systems engineering" work.
SYSTEMS_LANGS = {"C", "C++", "Assembly", "Rust", "Makefile", "CMake", "Shell", "Go", "Zig"}
# Languages ignored when picking a "main" language (markup / styling only).
IGNORED_LANGS = {"CSS", "HTML", "SCSS", "Sass", "Less"}
# Repo names that are websites, not projects to feature.
SKIP_FEATURED = re.compile(r"(\.github\.io$|^portfolio$)", re.I)

LANG_ICONS = {
    "C": "c", "C++": "cpp", "Assembly": "asm", "Rust": "rust", "Go": "go",
    "Shell": "bash", "CMake": "cmake", "Python": "py", "Java": "java",
    "C#": "cs", "JavaScript": "js", "TypeScript": "ts", "PHP": "php",
    "Kotlin": "kotlin", "Dart": "dart", "Lua": "lua", "Swift": "swift",
    "Dockerfile": "docker", "Makefile": "cmake", "HTML": "html", "CSS": "css",
}

# repo topic -> skillicons.dev id (systems-leaning tools first in the file)
TOPIC_ICONS = {
    "linux": "linux", "cmake": "cmake", "makefile": "cmake", "gdb": "gdb",
    "vim": "vim", "neovim": "neovim", "arduino": "arduino",
    "raspberry-pi": "raspberrypi", "raspberrypi": "raspberrypi",
    "git": "git", "docker": "docker", "kubernetes": "kubernetes",
    "nginx": "nginx", "githubactions": "githubactions", "github-actions": "githubactions",
    "sqlite": "sqlite", "mysql": "mysql", "postgresql": "postgres", "postgres": "postgres",
    "redis": "redis", "mongodb": "mongodb", "opencv": "opencv",
    "tensorflow": "tensorflow", "pytorch": "pytorch", "qt": "qt",
    "react": "react", "nodejs": "nodejs", "django": "django", "flask": "flask",
    "fastapi": "fastapi", "spring-boot": "spring", "springboot": "spring",
    "flutter": "flutter", "unity": "unity", "aws": "aws", "azure": "azure",
}

# Topics worth showing as text chips because skillicons has no icon for them.
TEXT_TOPICS = {
    "gtk": "GTK", "gtk3": "GTK3", "gtk4": "GTK4", "sdl": "SDL", "sdl2": "SDL2",
    "opengl": "OpenGL", "vulkan": "Vulkan", "posix": "POSIX", "sockets": "Sockets",
    "multithreading": "Multithreading", "pthreads": "pthreads", "stl": "STL",
    "data-structures": "Data Structures", "algorithms": "Algorithms",
    "operating-system": "Operating Systems", "os": "Operating Systems",
    "networking": "Networking", "memory-management": "Memory Management",
    "embedded": "Embedded", "kernel": "Kernel", "compiler": "Compilers",
    "ncurses": "ncurses", "valgrind": "Valgrind",
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
    pattern = re.compile(rf"(<!--START_{name}-->).*?(<!--END_{name}-->)", re.DOTALL)
    if not pattern.search(text):
        print(f"! marker {name} not found, skipped")
        return text
    return pattern.sub(lambda m: f"{m.group(1)}\n{content}\n{m.group(2)}", text)


def badge(label, value, color):
    def esc(s):
        return str(s).replace("-", "--").replace("_", "__").replace(" ", "%20")
    return (
        f'<img src="https://img.shields.io/badge/{esc(label)}-{esc(value)}-{color}'
        f'?style=for-the-badge&labelColor=0D1117" alt="{label}"/>'
    )


def repo_lang(r):
    lang = r.get("language")
    return lang if lang and lang not in IGNORED_LANGS else None


def lang_counts(repos):
    return Counter(repo_lang(r) for r in repos if repo_lang(r))


def build_stats(repos):
    langs = lang_counts(repos)
    stars = sum(r["stargazers_count"] for r in repos)
    c_cpp = langs.get("C", 0) + langs.get("C++", 0)
    systems = sum(n for l, n in langs.items() if l in SYSTEMS_LANGS)
    total = sum(langs.values()) or 1
    top = langs.most_common(1)[0][0] if langs else "N/A"
    return (
        '<div align="center">\n\n'
        + " ".join([
            badge("Public Repos", len(repos), "8B5CF6"),
            badge("C / C++ Repos", c_cpp, "00599C"),
            badge("Systems Code", f"{round(100 * systems / total)}%", "EC4899"),
            badge("Main Language", top, "22C55E"),
            badge("Stars", stars, "F59E0B"),
        ])
        + "\n\n</div>"
    )


def build_focus(repos):
    langs = lang_counts(repos)
    if not langs:
        return "_Language data will appear here automatically._"
    total = sum(langs.values())
    ordered = sorted(
        langs.items(),
        key=lambda kv: (kv[0] not in SYSTEMS_LANGS, -kv[1]),
    )[:8]
    top_n = max(n for _, n in ordered)
    rows = ["| Language | Repos | Share | |", "|---|---:|---:|---|"]
    for lang, n in ordered:
        filled = max(1, round(18 * n / top_n))
        bar = "█" * filled + "░" * (18 - filled)
        tag = " ⚙️" if lang in SYSTEMS_LANGS else ""
        rows.append(f"| **{lang}**{tag} | {n} | {round(100 * n / total)}% | `{bar}` |")
    rows.append("")
    rows.append("<sub>⚙️ = systems / low-level language. Ranked by number of repositories; CSS and HTML are excluded on purpose.</sub>")
    return "\n".join(rows)


def build_tech(repos):
    bytes_by_lang = Counter()
    for r in repos[:50]:
        try:
            for lang, size in api(r["languages_url"]).items():
                bytes_by_lang[lang] += size
        except Exception as exc:  # noqa: BLE001
            print(f"! languages failed for {r['name']}: {exc}")

    core, other = [], []
    for lang, _ in bytes_by_lang.most_common():
        if lang in IGNORED_LANGS:
            continue
        icon = LANG_ICONS.get(lang)
        if not icon:
            continue
        target = core if lang in SYSTEMS_LANGS else other
        if icon not in core and icon not in other:
            target.append(icon)

    topics = Counter(t.lower() for r in repos for t in r.get("topics", []))
    chips = []
    for t, _ in topics.most_common():
        icon = TOPIC_ICONS.get(t)
        if icon and icon not in core and icon not in other:
            (core if icon in {"linux", "cmake", "gdb", "vim", "neovim", "arduino", "raspberrypi", "git", "qt"} else other).append(icon)
        if t in TEXT_TOPICS and TEXT_TOPICS[t] not in chips:
            chips.append(TEXT_TOPICS[t])

    # Always-true basics for a C/C++ systems profile if repos prove the languages.
    for base in ("linux", "git"):
        if core and base not in core:
            core.append(base)

    out = ['<div align="center">\n']
    if core:
        out.append("**⚙️ Systems & low-level core**\n")
        out.append(f'<img src="https://skillicons.dev/icons?i={",".join(core)}&perline=8" alt="systems"/>\n')
    if chips:
        out.append(" ".join(
            f'<img src="https://img.shields.io/badge/{c.replace(" ", "%20")}-0D1117?style=flat-square&labelColor=0D1117&color=8B5CF6" alt="{c}"/>'
            for c in chips
        ) + "\n")
    if other:
        out.append("**🧰 Also work with**\n")
        out.append(f'<img src="https://skillicons.dev/icons?i={",".join(other)}&perline=8" alt="other"/>\n')
    if not core and not other:
        out.append("_Push some code and this section fills itself in._\n")
    out.append("</div>")
    return "\n".join(out)


def project_score(r):
    score = r["stargazers_count"] * 10 + r["forks_count"] * 5
    lang = r.get("language")
    if lang in SYSTEMS_LANGS:
        score += 50
    if lang in ("C", "C++"):
        score += 25
    if r.get("description"):
        score += 5
    return (score, r["pushed_at"])


def build_projects(repos):
    pool = [
        r for r in repos
        if not SKIP_FEATURED.search(r["name"]) and r.get("language") not in IGNORED_LANGS
        and r.get("language")
    ]
    ranked = sorted(pool, key=project_score, reverse=True)[:MAX_PROJECTS]
    if not ranked:
        return "_No public projects yet. They'll appear here automatically._"
    cards = [
        f'<a href="{r["html_url"]}"><img width="48%" '
        f'src="https://github-readme-stats.vercel.app/api/pin/?username={USER}'
        f'&repo={r["name"]}&theme=tokyonight&hide_border=true&bg_color=0D1117'
        f'&title_color=A78BFA&icon_color=EC4899" alt="{r["name"]}"/></a>'
        for r in ranked
    ]
    return '<div align="center">\n\n' + "\n".join(cards) + "\n\n</div>"


def build_recent(repos):
    recent = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:MAX_RECENT]
    if not recent:
        return "_Nothing here yet._"
    rows = ["| Repository | Description | Language | ⭐ | Updated |",
            "|---|---|---|---|---|"]
    for r in recent:
        desc = (r["description"] or "—").replace("|", "\\|")
        lang = r["language"] or "—"
        if lang in SYSTEMS_LANGS:
            lang += " ⚙️"
        rows.append(
            f'| [**{r["name"]}**]({r["html_url"]}) | {desc} | {lang} | '
            f'{r["stargazers_count"]} | {r["pushed_at"][:10]} |'
        )
    return "\n".join(rows)


def build_activity():
    try:
        events = api(f"https://api.github.com/users/{USER}/events/public?per_page=100")
    except Exception as exc:  # noqa: BLE001
        print(f"! events failed: {exc}")
        return "_Activity unavailable right now._"

    lines, seen = [], set()
    for e in events:
        repo = e["repo"]["name"]
        link = f"[{repo}](https://github.com/{repo})"
        day = e["created_at"][:10]
        t, p = e["type"], e.get("payload", {})
        if t == "PushEvent":
            n = len(p.get("commits", [])) or 1
            key = ("push", repo, day)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"- ⬆️ Pushed {n}+ commit(s) to {link} · `{day}`")
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
    text = replace(text, "FOCUS", build_focus(repos))
    text = replace(text, "TECH", build_tech(repos))
    text = replace(text, "PROJECTS", build_projects(repos))
    text = replace(text, "RECENT", build_recent(repos))
    text = replace(text, "ACTIVITY", build_activity())
    README.write_text(text, encoding="utf-8")
    print("README updated")


if __name__ == "__main__":
    main()
