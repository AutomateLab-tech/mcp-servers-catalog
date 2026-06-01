#!/usr/bin/env python3
"""
MCP servers catalog extraction script.

Parses the awesome-mcp-servers README.md and emits:
  - servers.json     canonical record-per-server
  - servers.parquet  columnar, HuggingFace dataset viewer-ready

Source: https://github.com/AutomateLab-tech/awesome-mcp-servers

Run:
    python extract.py [--readme path/to/README.md]

Idempotent: re-running overwrites output files from the same source.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    sys.exit("pyarrow is required: pip install pyarrow")

OUT_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Emoji → field mappings
# ---------------------------------------------------------------------------

LANG_MAP = {
    "🐍": "python",
    "📇": "typescript",
    "🏎️": "go",
    "🦀": "rust",
    "#️⃣": "csharp",
    "☕": "java",
    "🌊": "c_cpp",
    "💎": "ruby",
}

SCOPE_MAP = {
    "☁️": "cloud",
    "🏠": "local",
    "📟": "embedded",
}

OS_MAP = {
    "🍎": "macos",
    "🪟": "windows",
    "🐧": "linux",
}

OFFICIAL_EMOJI = "🎖️"

# Pre-build sets for fast lookup
_LANG_CHARS = set(LANG_MAP)
_SCOPE_CHARS = set(SCOPE_MAP)
_OS_CHARS = set(OS_MAP)

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Match section headers: ### EMOJI <a name="slug"></a>Title
_SECTION_RE = re.compile(
    r'^###\s.*?<a\s+name="([^"]+)"></a>\s*(.+)', re.IGNORECASE
)

# Match list entries: - [name](url) ...flags... - description
# Also handles entries with glama badge img tags and whitespace variations
_ENTRY_RE = re.compile(r"^-\s+\[([^\]]+)\]\(([^)]+)\)(.*)")

# Glama badge URL from inline badge markdown
_GLAMA_BADGE_RE = re.compile(
    r"https://glama\.ai/mcp/servers/([^\s\"')]+)/badges/score\.svg"
)
_GLAMA_SERVER_URL_RE = re.compile(
    r"\(https://glama\.ai/mcp/servers/([^\s\"')]+)\)"
)


def _slugify_category(header: str) -> str:
    """Convert section header text to a clean category name."""
    # Strip leading emoji and whitespace
    cleaned = re.sub(r"^[\U00010000-\U0010ffff☀-⛿✀-➿\s]+", "", header)
    cleaned = re.sub(r"[^\w\s&/-]", "", cleaned).strip()
    return cleaned


def _strip_badges(text: str) -> str:
    """Remove markdown image badges from text."""
    # [![alt](img_url)](link_url) — full linked badge
    text = re.sub(r"\[!\[[^\]]*\]\([^)]+\)\]\([^)]+\)", "", text)
    # ![alt](img_url) — bare badge
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    return text


def _parse_flags(flags_text: str) -> dict:
    """
    Extract language, scope, os, is_official from the emoji flags region.
    flags_text is the raw text between the URL close-paren and the description dash.
    """
    languages = []
    scopes = []
    operating_systems = []
    is_official = False

    # Walk through grapheme clusters (emoji are multi-codepoint)
    # We check for known emojis as substrings
    if OFFICIAL_EMOJI in flags_text:
        is_official = True

    for emoji, lang in LANG_MAP.items():
        if emoji in flags_text:
            languages.append(lang)

    for emoji, scope in SCOPE_MAP.items():
        if emoji in flags_text:
            scopes.append(scope)

    for emoji, os_name in OS_MAP.items():
        if emoji in flags_text:
            operating_systems.append(os_name)

    return {
        "languages": languages,
        "scopes": scopes,
        "operating_systems": operating_systems,
        "is_official": is_official,
    }


def parse_readme(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    records = []
    current_category = ""
    in_server_section = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect start of Server Implementations section
        if line.startswith("## Server Implementations"):
            in_server_section = True
            i += 1
            continue

        # Stop at Frameworks section (end of server listings)
        if in_server_section and line.startswith("## Frameworks"):
            break

        if not in_server_section:
            i += 1
            continue

        # Category section header
        section_m = _SECTION_RE.match(line)
        if section_m:
            current_category = _slugify_category(section_m.group(2).strip())
            i += 1
            continue

        # Server entry
        if not line.startswith("- ["):
            i += 1
            continue

        entry_m = _ENTRY_RE.match(line)
        if not entry_m:
            i += 1
            continue

        name = entry_m.group(1).strip()
        url = entry_m.group(2).strip()
        rest = entry_m.group(3)

        # Extract glama badge presence + server path
        glama_badge_m = _GLAMA_BADGE_RE.search(rest)
        has_glama_badge = bool(glama_badge_m)
        glama_server_path = glama_badge_m.group(1) if glama_badge_m else ""

        # Strip badges from rest to isolate flags + description
        rest_clean = _strip_badges(rest)

        # Parse flags from the full rest_clean (handles both "URL FLAGS - desc"
        # and "URL - FLAGS - desc" formats)
        flags = _parse_flags(rest_clean)

        # Find description: last " - " segment that starts with a letter/digit
        # This handles: "FLAGS - desc", "- FLAGS - desc", badge stripped variants
        description = ""
        parts = re.split(r"\s+-\s+", rest_clean)
        for part in reversed(parts):
            part = part.strip()
            if part and re.match(r"[A-Za-z0-9\"\'\(]", part):
                description = part
                break

        # Clean up description
        description = re.sub(r"\s+", " ", description).strip()

        # Derive npm_install hint if present in description
        npm_install = ""
        npm_m = re.search(r"`(npx[^`]+)`", description)
        if npm_m:
            npm_install = npm_m.group(1).strip()

        # Determine source host
        if "github.com" in url:
            source_host = "github"
        elif "gitlab.com" in url:
            source_host = "gitlab"
        elif "npmjs.com" in url or "npm" in url:
            source_host = "npm"
        else:
            source_host = "other"

        record = {
            "name": name,
            "url": url,
            "source_host": source_host,
            "category": current_category,
            "description": description,
            "languages": flags["languages"],
            "scopes": flags["scopes"],
            "operating_systems": flags["operating_systems"],
            "is_official": flags["is_official"],
            "has_glama_badge": has_glama_badge,
            "glama_server_path": glama_server_path,
            "npm_install": npm_install,
        }
        records.append(record)
        i += 1

    return records


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

SCHEMA_FIELDS = [
    "name",
    "url",
    "source_host",
    "category",
    "description",
    "languages",
    "scopes",
    "operating_systems",
    "is_official",
    "has_glama_badge",
    "glama_server_path",
    "npm_install",
]

LIST_FIELDS = {"languages", "scopes", "operating_systems"}
BOOL_FIELDS = {"is_official", "has_glama_badge"}


def normalize(rec: dict) -> dict:
    out = {}
    for f in SCHEMA_FIELDS:
        val = rec.get(f)
        if f in LIST_FIELDS:
            out[f] = val if isinstance(val, list) else []
        elif f in BOOL_FIELDS:
            out[f] = bool(val)
        else:
            out[f] = val if val is not None else ""
    return out


def write_json(records: list[dict], path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"  wrote {len(records)} records -> {path.name}")


def write_parquet(records: list[dict], path: Path):
    if not records:
        print("  no records to write")
        return

    cols: dict[str, list] = {f: [] for f in SCHEMA_FIELDS}
    for rec in records:
        for f in SCHEMA_FIELDS:
            val = rec.get(f)
            if f in LIST_FIELDS:
                cols[f].append(json.dumps(val if isinstance(val, list) else []))
            elif f in BOOL_FIELDS:
                cols[f].append(bool(val))
            else:
                cols[f].append(val if val is not None else "")

    arrays = {}
    for f in SCHEMA_FIELDS:
        if f in BOOL_FIELDS:
            arrays[f] = pa.array(cols[f], type=pa.bool_())
        else:
            arrays[f] = pa.array(cols[f], type=pa.string())

    table = pa.table(arrays)
    pq.write_table(table, path, compression="snappy")
    print(f"  wrote {len(records)} records -> {path.name}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract MCP servers catalog from awesome-mcp-servers README"
    )
    parser.add_argument(
        "--readme",
        default=None,
        help="Path to README.md (default: sibling awesome-mcp-servers/README.md or downloads from GitHub)",
    )
    args = parser.parse_args()

    if args.readme:
        readme_path = Path(args.readme)
    else:
        # Default: look for sibling repo
        sibling = OUT_DIR.parent / "awesome-mcp-servers" / "README.md"
        if sibling.exists():
            readme_path = sibling
            print(f"Using local README: {readme_path}")
        else:
            # Download from GitHub
            import urllib.request
            url = "https://raw.githubusercontent.com/AutomateLab-tech/awesome-mcp-servers/main/README.md"
            tmp = OUT_DIR / ".cache" / "awesome-mcp-servers-README.md"
            tmp.parent.mkdir(exist_ok=True)
            print(f"Downloading README from {url} ...")
            urllib.request.urlretrieve(url, tmp)
            readme_path = tmp
            print(f"Saved to {tmp}")

    if not readme_path.exists():
        sys.exit(f"README not found: {readme_path}")

    print(f"Parsing {readme_path} ...")
    records = parse_readme(readme_path)
    print(f"Parsed {len(records)} server entries")

    # Normalize
    normalized = [normalize(r) for r in records]

    # Dedup by url (keep first occurrence)
    seen_urls: set[str] = set()
    deduped = []
    for r in normalized:
        key = r["url"].rstrip("/").lower()
        if key not in seen_urls:
            seen_urls.add(key)
            deduped.append(r)

    print(f"After dedup: {len(deduped)} records")

    # Sort by category then name
    deduped.sort(key=lambda r: (r["category"].lower(), r["name"].lower()))

    print("Writing output files ...")
    write_json(deduped, OUT_DIR / "servers.json")
    write_parquet(deduped, OUT_DIR / "servers.parquet")

    # Print category summary
    from collections import Counter
    cats = Counter(r["category"] for r in deduped)
    print(f"\nTop 10 categories:")
    for cat, count in cats.most_common(10):
        print(f"  {count:4d}  {cat}")

    print(f"\nDone. Total: {len(deduped)} servers across {len(cats)} categories.")


if __name__ == "__main__":
    main()
