"""
Tests for pipeline module: deduplicate_businesses and dedupe key logic.
"""

import pytest
from handwerk_hamburg.pipeline import (
    deduplicate_businesses,
    _business_dedupe_key,
    _normalize_text,
)


def test_normalize_text() -> None:
    """_normalize_text lowercases, strips, and collapses whitespace."""
    assert _normalize_text("  Meier  Elektro  ") == "meier elektro"
    assert _normalize_text(None) == ""
    assert _normalize_text("") == ""


def test_business_dedupe_key_deterministic() -> None:
    """Same name + address/coords produce the same key."""
    b1 = {"name": "Meier Elektro", "address": "Hauptstr. 1", "lat": 53.55, "lon": 9.93}
    b2 = {"name": "meier elektro", "address": " Hauptstr.  1 ", "lat": 53.55, "lon": 9.93}
    assert _business_dedupe_key(b1) == _business_dedupe_key(b2)


def test_business_dedupe_key_uses_coords_when_no_address() -> None:
    """When address is missing, key uses rounded coordinates."""
    b = {"name": "Elektro X", "lat": 53.55001, "lon": 9.93002}
    key = _business_dedupe_key(b)
    assert "53.55001" in key and "9.93002" in key


def test_deduplicate_businesses_removes_duplicates() -> None:
    """Same shop from two sources is kept once (first occurrence)."""
    overpass = [{"name": "Meier", "address": "Hauptstr. 1", "lat": 53.55, "lon": 9.93, "source": "overpass"}]
    elektriker = [{"name": "Meier", "address": "Hauptstr. 1", "lat": 53.55, "lon": 9.93, "source": "elektriker_org"}]
    combined = overpass + elektriker
    result = deduplicate_businesses(combined)
    assert len(result) == 1
    assert result[0]["source"] == "overpass"


def test_deduplicate_businesses_keeps_different_shops() -> None:
    """Different name or location remain separate."""
    a = [{"name": "A", "address": "Str. 1", "lat": 53.55, "lon": 9.93}]
    b = [{"name": "B", "address": "Str. 2", "lat": 53.56, "lon": 9.94}]
    result = deduplicate_businesses(a + b)
    assert len(result) == 2
