import logging
import types

from loguru import logger


class InterceptHandler(logging.Handler):
    """Route stdlib logging calls through loguru.

    Add this as a handler to the root logger to capture output from
    third-party libraries (uvicorn, httpx, boto3, etc.) into the
    loguru pipeline with all sinks and formatting intact.

    Preserves the original logger name via loguru's bind mechanism.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: types.FrameType | None = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(
            _stdlib_name=record.name,
        ).opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())
