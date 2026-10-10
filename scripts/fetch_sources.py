#!/usr/bin/env python3
"""Fetch public community AI lists as review-only candidates; never publish them."""
from __future__ import annotations
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "SurgeToolkit": "https://raw.githubusercontent.com/imetn/SurgeToolkit/main/Rules/ai.list",
    "Yixuling": "https://raw.githubusercontent.com/Yixuling/surge-rulekit/main/rules/AI.list",
}
RULE = re.compile(r"^(DOMAIN|DOMAIN-SUFFIX),([a-z0-9.-]+)(?:,|$)", re.I)
DOMAIN = re.compile(r"^[a-z0-9-]+(?:\.[a-z0-9-]+)+$", re.I)
DENY = {"google.com", "googleapis.com", "gstatic.com", "cloudflare.com", "apple.com"}
OUT = ROOT / "sources/candidates.txt"
REPORT = ROOT / "reports/upstream.json"

def main() -> None:
    found: dict[str, set[str]] = {}
    errors: dict[str, str] = {}
    for name, url in SOURCES.items():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RocketGo-Rules/1.0"})
            with urllib.request.urlopen(req, timeout=20) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError("Source exceeds size limit")
            rules = set()
            for line in body.decode("utf-8-sig").splitlines():
                match = RULE.match(line.strip())
                if not match:
                    continue
                kind, domain = match.group(1).upper(), match.group(2).lower().rstrip(".")
                if DOMAIN.fullmatch(domain) and domain not in DENY:
                    rules.add(f"{kind},{domain}")
            if not rules:
                raise ValueError("No valid domain rules found")
            found[name] = rules
        except (OSError, ValueError, UnicodeError) as exc:
            errors[name] = str(exc)[:250]
    if not found:
        raise SystemExit("All upstream sources failed; keeping existing candidates and published module")
    # Review-only: generated module reads approved.rules, never candidates.txt.
    all_rules = sorted(set().union(*found.values()))
    OUT.write_text("# UNREVIEWED upstream suggestions. Not published automatically.\n" + "\n".join(all_rules) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "sources": {name: {"url": SOURCES[name], "count": len(rules)} for name, rules in sorted(found.items())},
        "errors": errors,
        "candidate_count": len(all_rules),
        "published_automatically": False
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Collected {len(all_rules)} candidates for review; no unapproved domains published.")

if __name__ == "__main__":
    main()
