---
license: cc-by-4.0
task_categories:
  - text-generation
  - text-classification
language:
  - en
size_categories:
  - 1K<n<10K
tags:
  - mcp
  - model-context-protocol
  - ai-agents
  - llm-tooling
  - agent-tooling
  - structured-data
  - claude
  - llm-training
pretty_name: MCP Servers Catalog
---

# MCP Servers Catalog

A structured, machine-readable catalog of **2,223 MCP (Model Context Protocol) servers** extracted from the curated [awesome-mcp-servers](https://github.com/AutomateLab-tech/awesome-mcp-servers) list. Covers 49 categories with language, scope, OS, and officiality metadata for each server.

Updated monthly. Last updated: 2026-05.

## Dataset Summary

This dataset catalogs what each MCP server *is*: its name, repository URL, category, description, implementation language, deployment scope (cloud/local), supported operating systems, and whether it carries an official or community-quality signal (official flag, Glama badge, npm install hint).

Existing MCP directories (glama.ai, mcp.so) are web-browsable but not machine-queryable. This dataset fills the gap: a flat, Parquet-native catalog an AI agent or researcher can load in one line and filter, rank, or embed without scraping.

## Intended Uses

**Agent tooling at inference time.** An AI agent selecting an MCP server for a task can load this catalog as context — filter by category, language, and scope before recommending an install command.

**LLM training and fine-tuning.** Ground models in the current MCP server landscape. Reduces hallucination of server names, capabilities, and install paths.

**Research.** Quantitative analysis of the MCP ecosystem: language distribution, category coverage, official vs. community server ratio, cloud vs. local split.

**Developer reference.** "What MCP servers exist for database access?" becomes a one-liner (see Sample Queries).

## Dataset Statistics

| Metric | Count |
|---|---|
| Total servers | 2,223 |
| Categories | 49 |
| Official servers | 122 |
| Servers with Glama quality badge | 857 |
| Servers with npm install hint | 84 |

**Top categories:** Developer Tools (327), Finance & Fintech (273), Other Tools and Integrations (162), Knowledge & Memory (159), Search & Data Extraction (140)

**Languages:** TypeScript (1,114), Python (776), Go (131), Rust (56), Java (23), C# (17)

**Scope:** Cloud (1,243), Local (1,124), Embedded (16)

## Files

| File | Description |
|---|---|
| `servers.json` | Canonical record-per-server, UTF-8 JSON array |
| `servers.parquet` | Columnar output, Snappy-compressed, HuggingFace dataset viewer-ready |
| `extract.py` | Extraction script - run to regenerate |

## Schema

| Field | Type | Notes |
|---|---|---|
| `name` | string | Server name as listed (often `owner/repo` format) |
| `url` | string | Primary repository or project URL |
| `source_host` | string | `github`, `gitlab`, `npm`, or `other` |
| `category` | string | Top-level category from the curated list (e.g. `Developer Tools`, `Databases`) |
| `description` | string | One-line description from the listing |
| `languages` | list[string] | Implementation languages: `typescript`, `python`, `go`, `rust`, `csharp`, `java`, `c_cpp`, `ruby` |
| `scopes` | list[string] | Deployment scope: `cloud`, `local`, `embedded` |
| `operating_systems` | list[string] | Supported OS: `macos`, `windows`, `linux` |
| `is_official` | bool | `true` if the server carries the official implementation flag |
| `has_glama_badge` | bool | `true` if a Glama quality score badge is present |
| `glama_server_path` | string | Glama server path (e.g. `owner/repo`) — empty if no badge |
| `npm_install` | string | Extracted `npx ...` install command from description — empty if none |

**Note on list fields in Parquet:** `languages`, `scopes`, and `operating_systems` are stored as JSON strings (e.g. `'["typescript","python"]'`). Parse with `json.loads()`.

## Sample Queries

**Find all Python MCP servers for databases (pandas):**

```python
import pandas as pd, json
df = pd.read_parquet("servers.parquet")
df["langs"] = df["languages"].apply(json.loads)
db_python = df[
    (df["category"] == "Databases") &
    df["langs"].apply(lambda l: "python" in l)
]
print(db_python[["name", "description"]].to_string())
```

**List official servers with npm install commands:**

```python
from datasets import load_dataset
ds = load_dataset("automatelab/mcp-servers-catalog", split="train")
official_npm = [r for r in ds if r["is_official"] and r["npm_install"]]
for r in official_npm:
    print(r["npm_install"], "—", r["description"][:60])
```

**Count servers by category and language (DuckDB):**

```sql
SELECT category,
       COUNT(*) AS total,
       COUNT_IF(has_glama_badge) AS quality_badged
FROM read_parquet('servers.parquet')
GROUP BY category
ORDER BY total DESC
LIMIT 15;
```

**Find all cloud-native TypeScript servers:**

```python
import pandas as pd, json
df = pd.read_parquet("servers.parquet")
df["scopes"] = df["scopes"].apply(json.loads)
df["langs"] = df["languages"].apply(json.loads)
cloud_ts = df[
    df["scopes"].apply(lambda s: "cloud" in s) &
    df["langs"].apply(lambda l: "typescript" in l)
]
print(f"{len(cloud_ts)} cloud TypeScript servers")
```

## Methodology

The catalog is extracted from the awesome-mcp-servers README using `extract.py`. The script:

1. Reads the README (local path or fetched from GitHub).
2. Walks the `## Server Implementations` section, tracking `###` category headers.
3. For each `- [name](url) ...` entry, parses emoji flags for language/scope/OS metadata, strips Glama badge markup, and splits the description from the flags region.
4. Deduplicates on URL (keeps first occurrence of any URL collision).
5. Emits `servers.json` (UTF-8 JSON array) and `servers.parquet` (Snappy-compressed columnar).

The script is idempotent: re-running on the same README produces identical output.

## Update Cadence

Updated monthly in sync with the upstream awesome-mcp-servers list. The `Last Updated` field at the top of this card tracks the most recent extraction run.

## Source

Upstream data: [AutomateLab-tech/awesome-mcp-servers](https://github.com/AutomateLab-tech/awesome-mcp-servers) — a curated community list of MCP server implementations.

## License

**Our additions** (catalog format, `extract.py`, this dataset card, and editorial framing) are licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

**Upstream server metadata** is derived from the awesome-mcp-servers community list. Each server's source code is under its own license (typically MIT). This dataset is a catalog/index of publicly listed server metadata, not a redistribution of source code.

Attribution: *Upstream server listings from the awesome-mcp-servers community list. Individual server source code under each project's own license.*

## Maintainer

[AutomateLab](https://automatelab.tech) - AI automation guides and tools.

## Maintenance and verification

See [the maintenance guide](docs/maintenance-guide.md) for interpretation limits, current tool names where applicable, and reproducible verification.

## October 2026 snapshot

4,210 records across 58 categories, parsed from punkpeye/awesome-mcp-servers at cc7f1f42c3fa8ced6fd5c0e02ea366ef7ed8cf1b. Listings are not security or health endorsements.

Snapshot prepared 12 October 2026. Publication time is recorded separately in the release receipt.
