"""Tests for the fingerprint module — loguru record-based fingerprinting."""

from types import SimpleNamespace

from stacksniper.fingerprint import fingerprint_from_record


def _make_record(*, file="src/app.py", func="process", message="test", exception=None):
    """Build a minimal loguru-style record dict for testing."""
    return {
        "file": SimpleNamespace(path=file),
        "function": func,
        "message": message,
        "exception": exception,
    }


def test_same_location_same_message_same_fingerprint():
    rec1 = _make_record(message="same msg")
    rec2 = _make_record(message="same msg")
    assert fingerprint_from_record(rec1) == fingerprint_from_record(rec2)


def test_different_messages_different_fingerprints():
    rec1 = _make_record(message="msg A")
    rec2 = _make_record(message="msg B")
    assert fingerprint_from_record(rec1) != fingerprint_from_record(rec2)


def test_different_files_different_fingerprints():
    rec1 = _make_record(file="src/a.py", message="same")
    rec2 = _make_record(file="src/b.py", message="same")
    assert fingerprint_from_record(rec1) != fingerprint_from_record(rec2)


def test_different_functions_different_fingerprints():
    rec1 = _make_record(func="func_a", message="same")
    rec2 = _make_record(func="func_b", message="same")
    assert fingerprint_from_record(rec1) != fingerprint_from_record(rec2)


def test_exception_fingerprint_ignores_message():
    """With exception, fingerprint uses exception type name, not message."""
    exc = SimpleNamespace(type=ValueError)
    rec1 = _make_record(message="first", exception=exc)
    rec2 = _make_record(message="second", exception=exc)
    assert fingerprint_from_record(rec1) == fingerprint_from_record(rec2)


def test_different_exception_types_differ():
    rec1 = _make_record(exception=SimpleNamespace(type=ValueError))
    rec2 = _make_record(exception=SimpleNamespace(type=TypeError))
    assert fingerprint_from_record(rec1) != fingerprint_from_record(rec2)


def test_fingerprint_is_8_char_hex():
    rec = _make_record()
    fp = fingerprint_from_record(rec)
    assert len(fp) == 8
    assert all(c in "0123456789abcdef" for c in fp)


def test_exception_with_none_type_falls_back_to_message():
    """exception present but type is None — use message-based fingerprint."""
    exc = SimpleNamespace(type=None)
    rec = _make_record(message="fallback msg", exception=exc)
    fp = fingerprint_from_record(rec)
    assert len(fp) == 8

    rec_no_exc = _make_record(message="fallback msg", exception=None)
    assert fp == fingerprint_from_record(rec_no_exc)
