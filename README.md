# stacksniper

[![CI](https://github.com/Bjern/stacksniper/actions/workflows/ci.yml/badge.svg)](https://github.com/Bjern/stacksniper/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/badge/linter-ruff-261230?logo=ruff)](https://docs.astral.sh/ruff/)
[![Mypy](https://img.shields.io/badge/types-mypy-blue?logo=python)](https://mypy-lang.org/)
[![Bandit](https://img.shields.io/badge/security-bandit-yellow?logo=python)](https://bandit.readthedocs.io/)

**Structured JSONL logging that's ready for DuckDB the moment you need it.**

stacksniper wraps [Loguru](https://github.com/Delgan/loguru) to give your Python app two things at once: pretty console output for humans, and a machine-readable `.jsonl` file you can query with SQL whenever something goes wrong. Every log line gets a stable fingerprint so you can group recurring errors without parsing free-text messages.

## Why?

Most logging setups force a trade-off: readable console output *or* structured files you can actually query. stacksniper gives you both with a single `setup()` call. When a bug hits production, you don't grep through walls of text -- you open DuckDB, point it at the JSONL file, and run SQL.

## Install

```bash
uv add stacksniper
# or
pip install stacksniper
```

## Typical usage flow

### 1. Wire it up (once, at startup)

```python
from stacksniper import setup, logger

setup("myapp")
```

That's it. You now have:

- **Console sink** -- colored, human-readable output on stderr
- **JSONL sink** -- `myapp.stacksniper.jsonl` in the current directory, rotating daily, with 7-day retention

Third-party libraries that use stdlib `logging` (uvicorn, httpx, boto3, etc.) are automatically intercepted and routed through the same pipeline.

### 2. Log stuff naturally

```python
logger.info("lead ingested", lead_id="abc-123", source="api")
logger.warning("retry failed", attempt=3, endpoint="/leads")

try:
    process_payment(order)
except Exception:
    logger.exception("payment processing failed", order_id=order.id)
```

Keyword arguments become structured `extra` fields in the JSONL output -- no format strings, no manual `json.dumps`.

### 3. Query when you need answers

When something breaks, open DuckDB and ask questions:

```sql
-- What errors happened in the last hour?
SELECT ts, msg, fingerprint, extra
FROM read_json_auto('myapp.stacksniper.jsonl')
WHERE level = 'ERROR'
  AND ts > now() - INTERVAL 1 HOUR
ORDER BY ts DESC;

-- Which errors keep recurring?
SELECT fingerprint, msg, count(*) AS hits
FROM read_json_auto('myapp.stacksniper.jsonl')
WHERE level = 'ERROR'
GROUP BY fingerprint, msg
ORDER BY hits DESC
LIMIT 10;

-- Trace a specific request
SELECT ts, level, msg, extra
FROM read_json_auto('myapp.stacksniper.jsonl')
WHERE extra->>'request_id' = 'req-abc-123'
ORDER BY ts;
```

### 4. Customize if needed

```python
setup(
    "myapp",
    log_dir="/var/log/myapp",   # where to write JSONL files
    console_level="INFO",       # less noise in the terminal
    jsonl_level="DEBUG",        # but capture everything on disk
    retention_days=30,          # keep a month of history
    intercept_stdlib=False,     # opt out of stdlib interception
)
```

## JSONL schema

Each log line is a JSON object with a flat, predictable structure:

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string | ISO 8601 UTC timestamp (`2026-04-07T12:00:00.123Z`) |
| `level` | string | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `msg` | string | Log message |
| `logger` | string | Module or stdlib logger name |
| `func` | string | Function that emitted the log |
| `file` | string | Source file path |
| `line` | int | Line number |
| `exc` | string\|null | Full traceback if an exception was logged |
| `fingerprint` | string | 8-char hex hash for deduplication |
| `extra` | object | Bound context (request_id, user_id, etc.) |

## License

GNU General Public License v3.0 -- see [LICENSE](LICENSE) for details.
