"""Tests for the JSONL serializer — stacksniper schema output."""

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from stacksniper.serializer import serialize_record


def _make_record(
    *,
    message="test msg",
    name="myapp.pipeline",
    function="process",
    file="src/pipeline.py",
    line=42,
    level_name="ERROR",
    exception=None,
    extra=None,
    time=None,
):
    """Build a loguru-style record dict for testing."""
    if time is None:
        time = datetime(2026, 4, 7, 10, 0, 0, 123000, tzinfo=timezone.utc)
    return {
        "time": time,
        "level": SimpleNamespace(name=level_name),
        "message": message,
        "name": name,
        "function": function,
        "file": SimpleNamespace(path=file),
        "line": line,
        "exception": exception,
        "extra": extra or {},
    }


def test_produces_valid_json():
    record = _make_record()
    line = serialize_record(record)
    parsed = json.loads(line)
    assert parsed["level"] == "ERROR"
    assert parsed["msg"] == "test msg"
    assert parsed["logger"] == "myapp.pipeline"
    assert parsed["func"] == "process"
    assert parsed["file"] == "src/pipeline.py"
    assert parsed["line"] == 42
    assert parsed["exc"] is None
    assert len(parsed["fingerprint"]) == 8


def test_timestamp_is_utc_iso_with_z_suffix():
    record = _make_record()
    line = serialize_record(record)
    parsed = json.loads(line)
    assert parsed["ts"] == "2026-04-07T10:00:00.123Z"


def test_core_fields_present_without_extra():
    record = _make_record()
    parsed = json.loads(serialize_record(record))
    expected_fields = {"ts", "level", "msg", "logger", "func", "file", "line", "exc", "fingerprint"}
    assert set(parsed.keys()) == expected_fields


def test_extra_fields_included():
    record = _make_record(extra={"request_id": "req-123", "user_id": "u456"})
    parsed = json.loads(serialize_record(record))
    assert parsed["extra"]["request_id"] == "req-123"
    assert parsed["extra"]["user_id"] == "u456"


def test_internal_extra_keys_excluded():
    record = _make_record(extra={"_stdlib_name": "some.lib", "request_id": "req-1"})
    parsed = json.loads(serialize_record(record))
    assert "extra" in parsed
    assert "request_id" in parsed["extra"]
    assert "_stdlib_name" not in parsed.get("extra", {})


def test_stdlib_name_override():
    record = _make_record(extra={"_stdlib_name": "uvicorn.access"})
    parsed = json.loads(serialize_record(record))
    assert parsed["logger"] == "uvicorn.access"


def test_exception_formatting():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        import traceback

        exc_info = sys.exc_info()
        exc = SimpleNamespace(
            type=exc_info[0],
            value=exc_info[1],
            traceback=exc_info[2],
        )
        exc.format = lambda: traceback.format_exception(*exc_info)

    record = _make_record(exception=exc)
    parsed = json.loads(serialize_record(record))
    assert parsed["exc"] is not None
    assert "ValueError: boom" in parsed["exc"]
    assert "Traceback" in parsed["exc"]


def test_multiline_message_stays_single_line():
    record = _make_record(message="line1\nline2\nline3")
    line = serialize_record(record)
    assert "\n" not in line
    parsed = json.loads(line)
    assert "line1\nline2\nline3" in parsed["msg"]


def test_unicode_characters():
    record = _make_record(message="café, naïve, 日本語")
    line = serialize_record(record)
    parsed = json.loads(line)
    assert "café" in parsed["msg"]
    assert "日本語" in parsed["msg"]
