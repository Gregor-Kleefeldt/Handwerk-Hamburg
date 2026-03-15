"""
Tests for analysis module: assign_businesses_to_plz, compute_scores, build_output_geojson.
"""

import pytest
from handwerk_hamburg.analysis import (
    assign_businesses_to_plz,
    compute_scores,
    build_output_geojson,
)


def test_build_output_geojson() -> None:
    """Build_output_geojson returns a FeatureCollection with the given features."""
    features = [
        {"type": "Feature", "geometry": None, "properties": {"plz": "20095"}},
    ]
    out = build_output_geojson(features)
    assert out["type"] == "FeatureCollection"
    assert out["features"] == features
    assert len(out["features"]) == 1


def test_assign_businesses_to_plz_adds_business_count() -> None:
    """assign_businesses_to_plz adds business_count to each feature."""
    from shapely.geometry import mapping, Polygon
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    plz_features = [
        {
            "type": "Feature",
            "geometry": mapping(poly),
            "properties": {"plz": "20095", "inhabitants": 100},
        },
    ]
    business_points = [{"lon": 0.5, "lat": 0.5}]
    result = assign_businesses_to_plz(plz_features, business_points)
    assert result[0]["properties"]["business_count"] == 1


def test_compute_scores_adds_people_per_business_and_white_spot_score() -> None:
    """compute_scores adds people_per_business and white_spot_score to properties."""
    features = [
        {"type": "Feature", "geometry": None, "properties": {"plz": "A", "inhabitants": 100, "business_count": 2}},
        {"type": "Feature", "geometry": None, "properties": {"plz": "B", "inhabitants": 200, "business_count": 1}},
    ]
    result = compute_scores(features)
    assert result[0]["properties"]["people_per_business"] == 50.0
    assert result[1]["properties"]["people_per_business"] == 200.0
    assert "white_spot_score" in result[0]["properties"]
    assert "white_spot_score" in result[1]["properties"]
    assert 0 <= result[0]["properties"]["white_spot_score"] <= 1
    assert 0 <= result[1]["properties"]["white_spot_score"] <= 1
