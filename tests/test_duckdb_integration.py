"""DuckDB integration tests — prove JSONL → DuckDB query pipeline works."""

import json
import os
import tempfile

import duckdb
from loguru import logger

from stacksniper import setup


def _reset_loguru():
    logger.remove()


def test_duckdb_reads_stacksniper_jsonl_with_timestamp_filtering():
    """End-to-end: loguru logs → JSONL → DuckDB query with ts filter."""
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL")

        logger.debug("debug msg")
        logger.info("info msg")
        logger.warning("warning msg")
        logger.error("error msg")
        logger.critical("critical msg")

        logfile = os.path.join(tmpdir, "testapp.stacksniper.jsonl")

        # Verify DuckDB infers ts as TIMESTAMP with the iso hint
        schema = duckdb.sql(f"""
            SELECT column_name, column_type
            FROM (DESCRIBE SELECT * FROM read_json_auto('{logfile}', timestampformat='iso'))
        """).fetchall()
        type_map = dict(schema)
        assert type_map["ts"] == "TIMESTAMP", f"Expected TIMESTAMP, got {type_map['ts']}"

        # Filter by level
        errors = duckdb.sql(f"""
            SELECT level, msg, fingerprint
            FROM read_json_auto('{logfile}', timestampformat='iso')
            WHERE level IN ('ERROR', 'WARNING', 'CRITICAL')
        """).fetchall()
        levels = [r[0] for r in errors]
        assert "WARNING" in levels
        assert "ERROR" in levels
        assert "CRITICAL" in levels

        # All fingerprints are 8-char hex
        for row in errors:
            assert len(row[2]) == 8


def test_duckdb_groupby_fingerprint():
    """Duplicate errors group correctly by fingerprint."""
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL")

        for _ in range(5):
            logger.error("repeated error")
        logger.error("unique error")

        logfile = os.path.join(tmpdir, "testapp.stacksniper.jsonl")

        result = duckdb.sql(f"""
            SELECT fingerprint, msg, count(*) as occurrences
            FROM read_json_auto('{logfile}', timestampformat='iso')
            WHERE level = 'ERROR'
            GROUP BY fingerprint, msg
            ORDER BY occurrences DESC
        """).fetchall()

        assert len(result) == 2
        assert result[0][1] == "repeated error"
        assert result[0][2] == 5
        assert result[1][1] == "unique error"
        assert result[1][2] == 1


def test_duckdb_extra_fields_queryable():
    """Extra context fields (request_id, etc.) are queryable in DuckDB."""
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL")

        logger.info("with context", request_id="req-abc")
        logger.info("no context")

        logfile = os.path.join(tmpdir, "testapp.stacksniper.jsonl")

        result = duckdb.sql(f"""
            SELECT msg, extra->>'request_id' as request_id
            FROM read_json_auto('{logfile}', timestampformat='iso')
            WHERE msg NOT LIKE 'stacksniper%'
        """).fetchall()

        result_dict = {r[0]: r[1] for r in result}
        assert result_dict["with context"] == "req-abc"


def test_duckdb_timestamp_interval_filter():
    """Interval-based filtering works on stacksniper timestamps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        logfile = os.path.join(tmpdir, "app.stacksniper.jsonl")

        # Write lines with controlled timestamps
        lines = [
            {
                "ts": "2026-04-02T19:00:00.000Z",
                "level": "ERROR",
                "msg": "old",
                "logger": "app",
                "func": "f",
                "file": "a.py",
                "line": 1,
                "exc": None,
                "fingerprint": "aaaaaaaa",
            },
            {
                "ts": "2026-04-02T22:00:00.000Z",
                "level": "ERROR",
                "msg": "recent",
                "logger": "app",
                "func": "f",
                "file": "a.py",
                "line": 2,
                "exc": None,
                "fingerprint": "bbbbbbbb",
            },
            {
                "ts": "2026-04-02T23:30:00.000Z",
                "level": "ERROR",
                "msg": "very recent",
                "logger": "app",
                "func": "f",
                "file": "a.py",
                "line": 3,
                "exc": None,
                "fingerprint": "cccccccc",
            },
        ]
        with open(logfile, "w") as f:
            for line in lines:
                f.write(json.dumps(line) + "\n")

        result = duckdb.sql(f"""
            SELECT msg
            FROM read_json_auto('{logfile}', timestampformat='iso')
            WHERE ts >= TIMESTAMP '2026-04-02T23:00:00' - INTERVAL 2 HOUR
            ORDER BY ts
        """).fetchall()
        msgs = [r[0] for r in result]
        assert msgs == ["recent", "very recent"]
