"""Tests for analysis/resolver.py — outcome resolution logic."""
from analysis.resolver import resolve_outcome

def test_hit_when_actual_exceeds_line():
    result = {"player": "Test Player", "line": 18.5}
    assert resolve_outcome(result, 22.0) == "hit"

def test_miss_when_actual_below_line():
    result = {"player": "Test Player", "line": 18.5}
    assert resolve_outcome(result, 15.0) == "miss"

def test_miss_when_actual_equals_line():
    result = {"player": "Test Player", "line": 18.5}
    assert resolve_outcome(result, 18.5) == "miss"

def test_none_when_no_line():
    result = {"player": "Test Player"}
    assert resolve_outcome(result, 20.0) is None
