from collections import defaultdict


RATING_ICON = {
    "BEST OF THE NIGHT": "***",
    "VERY FAVORABLE":    "**",
    "FAVORABLE":         "*",
}

STAT_LABELS = {
    "pts": "PONTOS (PTS)",
    "ast": "ASSISTÊNCIAS (AST)",
    "reb": "REBOTES (REB)",
    "three_pt": "CESTAS DE 3 (3PT)",
}


def _format_line(line_val):
    """Extract a display string from a line value (dict or number)."""
    if isinstance(line_val, dict):
        v = line_val.get("value")
        return str(v) if v is not None else "N/A"
    if line_val is not None:
        return str(line_val)
    return "N/A"


def _format_stat_section(stat_key, candidates):
    """Format a single stat section with its header and ranked players."""
    label = STAT_LABELS.get(stat_key, stat_key.upper())
    lines = []
    lines.append(f"\n  >> {label}")
    lines.append("  " + "-" * 30)

    by_game = defaultdict(list)
    for c in candidates:
        game = c.get("game", "Unknown")
        by_game[game].append(c)

    rank = 1
    for game, players in by_game.items():
        lines.append(f"\n  {game}")

        for p in players:
            player_name = p.get("player_name", p.get("player", ""))
            rating = p.get("rating", "")
            icon = RATING_ICON.get(rating, "")
            position = p.get("position", "")
            team = p.get("team", "")

            lines.append(f"  #{rank} {player_name} ({position}) - {team}")
            lines.append(f"      {icon} {rating}")

            line_val = p.get("line", {})
            line_str = f"{_format_line(line_val)} {stat_key}"
            lines.append(f"      Line: {line_str}")

            # Signals — support both new context-based and legacy flat list
            signals = p.get("context", {}).get(
                "signal_descriptions", p.get("signals", [])
            )
            for signal in signals:
                lines.append(f"      - {signal}")

            # Quick stats
            recent = p.get("recent_stats")
            if recent:
                lines.append(
                    f"      Stats (last {recent['games']}g): "
                    f"{recent['pts']} pts | {recent['reb']} reb | "
                    f"{recent['ast']} ast | {recent['min']} min"
                )

            lines.append("")
            rank += 1

    return lines


def format_results(stats):
    """
    Accepts either:
      - a dict  {"pts": [...], "ast": [...], ...}  (new multi-stat format)
      - a list  [...]                               (legacy PTS-only format)

    Returns formatted plain text grouped by stat section and game.
    """
    # Legacy support: bare list → treat as PTS-only
    if isinstance(stats, list):
        stats = {"pts": stats}

    # Check if there is anything to show
    if not stats or not any(stats.values()):
        return "No favorable plays found for tonight."

    lines = []
    lines.append("=" * 56)
    lines.append("   NBA TONIGHT - TOP PLAYS")
    lines.append("=" * 56)

    for stat_key in ("pts", "ast", "reb", "three_pt"):
        candidates = stats.get(stat_key, [])
        if not candidates:
            continue
        lines.extend(_format_stat_section(stat_key, candidates))

    lines.append("=" * 56)
    return "\n".join(lines)
