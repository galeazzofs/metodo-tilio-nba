"""
analysis/resolver.py — Resolves analysis pick outcomes.
Compares stored betting lines against actual player performance.
"""

def resolve_outcome(result: dict, actual_pts: float) -> str | None:
    """
    Determines if a pick was a hit or miss.
    Returns "hit" if actual > line, "miss" if actual <= line, None if no line stored.
    """
    line = result.get("line")
    if line is None:
        return None
    return "hit" if actual_pts > line else "miss"
