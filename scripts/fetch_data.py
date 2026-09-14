#!/usr/bin/env python3
"""
fetch_data.py - merge data/projects.json (curated by hand) with live GitHub
data. Produces data/merged.json for generate_projects.py to render.

    python3 scripts/fetch_data.py --owner Hemansh-X797

User controls (in projects.json): repo, description, language, tagline,
live_url, order (array order).
Auto-fetched: stars, forks, languages (byte split, for the donut), pushed_at.

If a repo is private, renamed, or simply not pushed yet, the API call fails
and the project is marked "unavailable": true instead of crashing the run
or inventing numbers -- generate_projects.py renders those with a lock
badge and no live stats.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

TOKEN = None  # set in main() from --token/$GITHUB_TOKEN


def gh(url: str):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "projects-panel"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--owner", required=True, help="GitHub username that owns the repos")
    p.add_argument("--projects", type=Path, default=Path("data/projects.json"))
    p.add_argument("--out", type=Path, default=Path("data/merged.json"))
    p.add_argument("--token", default=None, help="defaults to $GITHUB_TOKEN")
    args = p.parse_args(argv)

    global TOKEN
    import os
    TOKEN = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    projects = json.loads(args.projects.read_text(encoding="utf-8"))["projects"]

    for proj in projects:
        repo = proj["repo"].strip().replace("https://github.com/", "") \
                            .replace("http://github.com/", "").rstrip("/")
        if "/" not in repo:
            repo = f"{args.owner}/{repo}"
        proj["repo"] = repo
        proj["name"] = repo.split("/", 1)[1]
        try:
            info = gh(f"https://api.github.com/repos/{repo}")
            proj["stars"] = info.get("stargazers_count", 0)
            proj["forks"] = info.get("forks_count", 0)
            proj["pushed_at"] = info.get("pushed_at")
            if not proj.get("description"):
                proj["description"] = info.get("description") or ""
            proj["languages"] = gh(f"https://api.github.com/repos/{repo}/languages")
            proj["unavailable"] = False
        except urllib.error.HTTPError as e:
            print(f"  note: {repo} not visible ({e.code}) -- "
                  f"private or not pushed yet, marking unavailable", file=sys.stderr)
            proj["unavailable"] = True
            proj.setdefault("stars", 0)
            proj.setdefault("forks", 0)
            proj.setdefault("languages", {})
            proj.setdefault("pushed_at", None)
        except Exception as e:  # network hiccups etc. -- never let one repo kill the run
            print(f"  warn: could not fetch {repo}: {e}", file=sys.stderr)
            proj["unavailable"] = True
            proj.setdefault("stars", 0)
            proj.setdefault("forks", 0)
            proj.setdefault("languages", {})
            proj.setdefault("pushed_at", None)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(projects, indent=2), encoding="utf-8")
    live = sum(1 for p in projects if not p["unavailable"])
    print(f"merged {len(projects)} projects ({live} live, {len(projects)-live} unavailable) -> {args.out}")


if __name__ == "__main__":
    main()
