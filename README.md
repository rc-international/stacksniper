# stacksniper

Structured JSONL logging for automated code healers -- loguru-powered, DuckDB-queryable.

![CI](https://github.com/rc-international/stacksniper/actions/workflows/ci.yml/badge.svg)

## Install

```bash
uv add stacksniper
# or
pip install stacksniper
```

## Quick Start

```python
from stacksniper import setup, logger

setup("myapp")

logger.info("lead ingested", lead_id="abc-123", source="api")
logger.warning("retry failed", attempt=3, endpoint="/leads")
```

This creates `myapp.stacksniper.jsonl` with daily rotation and 7-day retention.

## JSONL Schema

Each log line is a JSON object with these fields:

| Field | Type | Description |
|-------|------|-------------|
| `ts` | string | ISO 8601 UTC timestamp (`2026-04-07T12:00:00.123Z`) |
| `level` | string | Severity: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `msg` | string | Log message |
| `logger` | string | Module or stdlib logger name |
| `func` | string | Function name |
| `file` | string | Source file path |
| `line` | int | Line number |
| `exc` | string\|null | Full traceback if exception was logged |
| `fingerprint` | string | 8-char hex hash for deduplication |
| `extra` | object | Bound context (request_id, user_id, etc.) |

## DuckDB Queryability

```sql
SELECT level, msg, extra->>'lead_id' AS lead_id
FROM read_json_auto('myapp.stacksniper.jsonl')
WHERE level = 'ERROR'
ORDER BY ts DESC
LIMIT 10;
```

## License

MIT
