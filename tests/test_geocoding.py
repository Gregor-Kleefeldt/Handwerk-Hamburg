"""
Tests for geocoding module: normalize_address_for_geocoding, _normalize_address_key,
_lookup_known_address, geocode_address, geocode_address_with_fallbacks.
"""

import pytest
from unittest.mock import patch, MagicMock

from handwerk_hamburg.geocoding import (
    normalize_address_for_geocoding,
    _normalize_address_key,
    _lookup_known_address,
    geocode_address,
    geocode_address_with_fallbacks,
)

import handwerk_hamburg.geocoding as geocoding_module


def test_normalize_address_for_geocoding_returns_list_with_at_least_one_variant() -> None:
    """normalize_address_for_geocoding returns a list with at least one variant."""
    result = normalize_address_for_geocoding("Some Street 5")
    assert isinstance(result, list)
    assert len(result) >= 1
    assert all(isinstance(s, str) for s in result)


def test_normalize_address_for_geocoding_adds_hamburg_when_missing() -> None:
    """Adds ', Hamburg' when 'hamburg' is not in the input."""
    result = normalize_address_for_geocoding("Some Street 5")
    assert any("Hamburg" in v for v in result)


def test_normalize_address_for_geocoding_applies_street_normalizations() -> None:
    """Applies STREET_NORMALIZATIONS (e.g. 'Max Brauer Alle' -> 'Max-Brauer-Allee')."""
    result = normalize_address_for_geocoding("Max Brauer Alle 10")
    assert any("Max-Brauer-Allee" in v for v in result)


def test_normalize_address_for_geocoding_empty_returns_empty_list() -> None:
    """Empty or None input returns empty list."""
    assert normalize_address_for_geocoding("") == []
    assert normalize_address_for_geocoding(None) == []


def test_normalize_address_key_lowercases_strips_removes_commas_collapses_whitespace() -> None:
    """_normalize_address_key lowercases, strips, removes commas, collapses whitespace."""
    got = _normalize_address_key("Max-Brauer-Allee 10, Hamburg")
    assert got == "max-brauer-allee 10 hamburg"


def test_lookup_known_address_returns_tuple_for_known_address() -> None:
    """_lookup_known_address returns (lat, lon) tuple for a known address."""
    coords = _lookup_known_address("Max-Brauer-Allee 10 Hamburg")
    assert coords is not None
    assert isinstance(coords, tuple)
    assert len(coords) == 2
    assert coords == (53.5506, 9.9292)


def test_lookup_known_address_returns_none_for_unknown() -> None:
    """_lookup_known_address returns None for unknown address."""
    assert _lookup_known_address("Unknown Street 999 Hamburg") is None


def test_geocode_address_returns_tuple_on_success() -> None:
    """geocode_address returns (lat, lon) when Nominatim returns valid JSON inside Hamburg bbox."""
    geocoding_module._geocode_cache.clear()
    fake_response = MagicMock()
    fake_response.json.return_value = [{"lat": "53.55", "lon": "9.99"}]
    fake_response.raise_for_status = MagicMock()
    with patch.object(geocoding_module.requests, "get", return_value=fake_response):
        result = geocode_address("Walther-Kunze-Str. 16, 22765 Hamburg")
    assert result == (53.55, 9.99)


def test_geocode_address_returns_none_when_response_empty_list() -> None:
    """geocode_address returns None when Nominatim response is empty list."""
    geocoding_module._geocode_cache.clear()
    fake_response = MagicMock()
    fake_response.json.return_value = []
    fake_response.raise_for_status = MagicMock()
    with patch.object(geocoding_module.requests, "get", return_value=fake_response):
        result = geocode_address("Nonexistent Address 123")
    assert result is None


def test_geocode_address_returns_none_when_outside_hamburg_bbox() -> None:
    """geocode_address returns None when coordinates are outside Hamburg bbox + margin."""
    geocoding_module._geocode_cache.clear()
    fake_response = MagicMock()
    fake_response.json.return_value = [{"lat": "52.0", "lon": "8.0"}]
    fake_response.raise_for_status = MagicMock()
    with patch.object(geocoding_module.requests, "get", return_value=fake_response):
        result = geocode_address("Some Address Far Away")
    assert result is None


def test_geocode_address_caches_result_so_second_call_does_not_call_requests_get() -> None:
    """Cached result means a second call does not trigger requests.get again."""
    geocoding_module._geocode_cache.clear()
    fake_response = MagicMock()
    fake_response.json.return_value = [{"lat": "53.55", "lon": "9.99"}]
    fake_response.raise_for_status = MagicMock()
    with patch.object(geocoding_module.requests, "get", return_value=fake_response) as mock_get:
        geocode_address("Cached Address 1, Hamburg")
        geocode_address("Cached Address 1, Hamburg")
    assert mock_get.call_count == 1


def test_geocode_address_with_fallbacks_returns_known_coords_without_nominatim() -> None:
    """geocode_address_with_fallbacks returns known coords without calling Nominatim."""
    with patch.object(geocoding_module, "geocode_address") as mock_geocode:
        result = geocode_address_with_fallbacks("Max-Brauer-Allee 10 Hamburg")
    assert result == (53.5506, 9.9292)
    mock_geocode.assert_not_called()


def test_geocode_address_with_fallbacks_calls_geocode_when_not_known() -> None:
    """geocode_address_with_fallbacks calls geocode_address when not in known table."""
    geocoding_module._geocode_cache.clear()
    with patch.object(geocoding_module, "geocode_address", return_value=(53.5, 9.9)):
        result = geocode_address_with_fallbacks("Unknown Street 1")
    assert result == (53.5, 9.9)


def test_geocode_address_with_fallbacks_returns_none_when_all_variants_fail() -> None:
    """geocode_address_with_fallbacks returns None if all variants fail."""
    geocoding_module._geocode_cache.clear()
    with patch.object(geocoding_module, "geocode_address", return_value=None):
        result = geocode_address_with_fallbacks("Nonexistent Place 999")
    assert result is None
