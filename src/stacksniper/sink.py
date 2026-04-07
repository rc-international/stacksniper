import logging
import time
from pathlib import Path
from threading import Lock
from typing import IO

from stacksniper.serializer import serialize_record

_log = logging.getLogger(__name__)


class RotatingJsonlSink:
    """Loguru sink that writes stacksniper JSONL with daily rotation.

    Used as a callable sink: logger.add(RotatingJsonlSink(...))

    Handles file rotation by date and retention by age, matching
    the behavior of loguru's built-in file rotation but with our
    custom serialization format.
    """

    def __init__(
        self,
        path: str | Path,
        rotation_days: int = 1,
        retention_days: int = 7,
    ) -> None:
        self._path = Path(path)
        self._rotation_days = rotation_days
        self._retention_days = retention_days
        self._lock = Lock()
        self._file: IO[str] | None = None
        self._current_date: str | None = None
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _get_date_str(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime())

    def _rotate_if_needed(self) -> None:
        today = self._get_date_str()
        if today != self._current_date:
            if self._file is not None:
                self._file.close()
                # Rename old file with date suffix
                if self._current_date and self._path.exists():
                    rotated = self._path.with_suffix(f".{self._current_date}.jsonl")
                    try:
                        self._path.rename(rotated)
                    except OSError as e:
                        _log.debug("rotate rename failed (concurrent rotation?): %s", e)
            self._file = open(self._path, "a", encoding="utf-8")
            self._current_date = today
            self._cleanup_old_files()

    def _cleanup_old_files(self) -> None:
        cutoff = time.time() - (self._retention_days * 86400)
        parent = self._path.parent
        stem = self._path.stem.split(".")[0]  # e.g. "parqinglot" from "parqinglot.stacksniper"
        for f in parent.glob(f"{stem}.stacksniper.*.jsonl"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
            except OSError as e:
                _log.debug("cleanup failed for %s: %s", f, e)

    def write(self, message) -> None:
        record = message.record
        line = serialize_record(record)
        with self._lock:
            self._rotate_if_needed()
            assert self._file is not None
            self._file.write(line + "\n")
            self._file.flush()

    def __call__(self, message) -> None:
        self.write(message)

    def close(self) -> None:
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None
