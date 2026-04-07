import hashlib
from typing import Any


def fingerprint_from_record(record: dict[str, Any]) -> str:
    """Generate an 8-char hex fingerprint from a loguru record dict.

    With exception: hash(file + function + exception type name).
    Without: hash(file + function + message).

    The same bug in the same place always produces the same fingerprint
    regardless of variable content (URLs, payloads, timestamps).
    """
    file = record.get("file", record.get("pathname", ""))
    if hasattr(file, "path"):
        file = file.path
    func = record.get("function", record.get("funcName", ""))

    exception = record.get("exception")
    if exception and exception.type:
        raw = f"{file}:{func}:{exception.type.__name__}"
    else:
        raw = f"{file}:{func}:{record.get('message', '')}"

    return hashlib.sha256(raw.encode()).hexdigest()[:8]
