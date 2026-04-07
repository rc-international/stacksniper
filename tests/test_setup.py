"""Tests for the setup() function — sink configuration and stdlib interception."""

import json
import logging
import os
import tempfile

from loguru import logger

from stacksniper import setup


def _reset_loguru():
    """Remove all loguru sinks to isolate tests."""
    logger.remove()


def test_setup_creates_jsonl_file():
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL")
        logger.info("hello from loguru")

        jsonl = os.path.join(tmpdir, "testapp.stacksniper.jsonl")
        assert os.path.exists(jsonl)

        with open(jsonl) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        # Should have at least the init message and our test message
        msgs = [entry["msg"] for entry in lines]
        assert "stacksniper initialized" in msgs
        assert "hello from loguru" in msgs


def test_setup_intercepts_stdlib():
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL", intercept_stdlib=True)

        stdlib_logger = logging.getLogger("my.library")
        stdlib_logger.warning("stdlib captured")

        jsonl = os.path.join(tmpdir, "testapp.stacksniper.jsonl")
        with open(jsonl) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        stdlib_lines = [entry for entry in lines if entry["msg"] == "stdlib captured"]
        assert len(stdlib_lines) == 1
        assert stdlib_lines[0]["logger"] == "my.library"
        assert stdlib_lines[0]["level"] == "WARNING"


def test_setup_without_stdlib_intercept():
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL", intercept_stdlib=False)
        logger.info("loguru only")

        jsonl = os.path.join(tmpdir, "testapp.stacksniper.jsonl")
        with open(jsonl) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        msgs = [entry["msg"] for entry in lines]
        assert "loguru only" in msgs


def test_extra_context_in_jsonl():
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL")
        logger.info("with context", request_id="req-abc", user_id="u123")

        jsonl = os.path.join(tmpdir, "testapp.stacksniper.jsonl")
        with open(jsonl) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        ctx_lines = [entry for entry in lines if entry["msg"] == "with context"]
        assert len(ctx_lines) == 1
        assert ctx_lines[0]["extra"]["request_id"] == "req-abc"
        assert ctx_lines[0]["extra"]["user_id"] == "u123"


def test_exception_in_jsonl():
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL")

        try:
            raise RuntimeError("test boom")
        except RuntimeError:
            logger.exception("caught it")

        jsonl = os.path.join(tmpdir, "testapp.stacksniper.jsonl")
        with open(jsonl) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        exc_lines = [entry for entry in lines if entry["msg"] == "caught it"]
        assert len(exc_lines) == 1
        assert exc_lines[0]["exc"] is not None
        assert "RuntimeError: test boom" in exc_lines[0]["exc"]
        assert exc_lines[0]["fingerprint"]


def test_jsonl_level_filtering():
    _reset_loguru()
    with tempfile.TemporaryDirectory() as tmpdir:
        setup("testapp", log_dir=tmpdir, console_level="CRITICAL", jsonl_level="WARNING")

        logger.debug("skip this")
        logger.info("skip this too")
        logger.warning("include this")
        logger.error("include this too")

        jsonl = os.path.join(tmpdir, "testapp.stacksniper.jsonl")
        with open(jsonl) as f:
            lines = [json.loads(line) for line in f if line.strip()]

        levels = {entry["level"] for entry in lines}
        assert "DEBUG" not in levels
        assert "INFO" not in levels  # init message filtered out too
        assert "WARNING" in levels
        assert "ERROR" in levels
