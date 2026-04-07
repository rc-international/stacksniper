import json
from datetime import datetime, timezone
from typing import Any

from stacksniper.fingerprint import fingerprint_from_record


def serialize_record(record: dict[str, Any]) -> str:
    """Serialize a loguru record dict to stacksniper JSONL format.

    Output schema matches what DuckDB read_json_auto expects:
    - ts: ISO 8601 UTC with Z suffix (DuckDB infers as TIMESTAMP)
    - level: severity string
    - msg: formatted message
    - logger: module name
    - func: function name
    - file: source file path
    - line: line number
    - exc: full traceback or null
    - fingerprint: 8-char hex for deduplication
    - extra: any bound context (request_id, api_key, etc.)
    """
    ts = datetime.fromtimestamp(record["time"].timestamp(), tz=timezone.utc)

    exc = None
    if record["exception"] is not None:
        try:
            import traceback as tb_mod

            exc_val = record["exception"]
            if hasattr(exc_val, "type") and exc_val.type is not None:
                # loguru RecordException namedtuple: (type, value, traceback)
                exc = "".join(tb_mod.format_exception(exc_val.type, exc_val.value, exc_val.traceback))
            else:
                exc = str(exc_val)
        except Exception:
            exc = str(record["exception"])

    # Use original stdlib logger name if intercepted from stdlib logging
    logger_name = record["extra"].get("_stdlib_name", record["name"])

    # Separate internal keys from user-bound extra context
    extra = {k: v for k, v in record["extra"].items() if not k.startswith("_")}

    entry: dict[str, Any] = {
        "ts": ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{ts.microsecond // 1000:03d}Z",
        "level": record["level"].name,
        "msg": record["message"],
        "logger": logger_name,
        "func": record["function"],
        "file": str(record["file"].path) if hasattr(record["file"], "path") else str(record["file"]),
        "line": record["line"],
        "exc": exc,
        "fingerprint": fingerprint_from_record(record),
    }

    if extra:
        entry["extra"] = extra

    return json.dumps(entry, default=str, ensure_ascii=False)
