import logging
import sys
from pathlib import Path

from loguru import logger

from stacksniper.intercept import InterceptHandler
from stacksniper.sink import RotatingJsonlSink


def setup(
    app_name: str,
    *,
    log_dir: str | Path | None = None,
    console_level: str = "DEBUG",
    jsonl_level: str = "DEBUG",
    retention_days: int = 7,
    intercept_stdlib: bool = True,
) -> None:
    """Configure structured logging for an application.

    Sets up two loguru sinks:
    1. Console — human-readable colored output for terminals / docker logs
    2. JSONL file — {app_name}.stacksniper.jsonl with stacksniper schema
       for DuckDB querying and AI-powered log analysis

    Optionally intercepts stdlib logging so third-party libraries
    (uvicorn, httpx, boto3, etc.) route through the same pipeline.

    Args:
        app_name: Application name, used for JSONL filename.
        log_dir: Directory for JSONL file. Defaults to current directory.
        console_level: Minimum level for console output.
        jsonl_level: Minimum level for JSONL output.
        retention_days: How many days of rotated JSONL files to keep.
        intercept_stdlib: Whether to intercept stdlib logging module.
    """
    # Remove loguru's default stderr sink
    logger.remove()

    # Sink 1: Console (human-readable)
    logger.add(
        sys.stderr,
        level=console_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=False,  # don't leak variable values in production tracebacks
    )

    # Sink 2: JSONL file (machine-readable, DuckDB-queryable)
    if log_dir is None:
        log_dir = Path(".")
    else:
        log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = log_dir / f"{app_name}.stacksniper.jsonl"

    jsonl_sink = RotatingJsonlSink(
        path=jsonl_path,
        retention_days=retention_days,
    )
    logger.add(
        jsonl_sink,
        level=jsonl_level,
        format="{message}",  # unused — sink handles serialization
        backtrace=True,
        diagnose=False,
    )

    # Intercept stdlib logging
    if intercept_stdlib:
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

        # Explicitly intercept loggers that configure their own handlers
        # (uvicorn sets up its own handlers, bypassing the root interceptor)
        for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
            stdlib_logger = logging.getLogger(name)
            stdlib_logger.handlers = [InterceptHandler()]
            stdlib_logger.propagate = False

    logger.info(
        "stacksniper initialized",
        app_name=app_name,
        jsonl_path=str(jsonl_path),
    )
