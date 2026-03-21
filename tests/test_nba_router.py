"""Tests for routers/nba.py caching logic."""
import time
from routers.nba import _cache_get, _cache_set, _cache

def test_cache_set_and_get():
    _cache.clear()
    _cache_set("test_key", {"data": 1}, ttl=10)
    assert _cache_get("test_key") == {"data": 1}

def test_cache_expired():
    _cache.clear()
    _cache_set("test_key", {"data": 1}, ttl=0)
    time.sleep(0.1)
    assert _cache_get("test_key") is None
