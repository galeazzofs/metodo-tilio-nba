from collections import defaultdict


RATING_ICON = {
    "BEST OF THE NIGHT": "***",
    "VERY FAVORABLE":    "**",
    "FAVORABLE":         "*",
}


def format_results(candidates):
    """
    Takes the top 5 candidates and formats them as plain text grouped by game.
    """
    if not candidates:
        return "No favorable plays found for tonight."

    # Group by game
    by_game = defaultdict(list)
    for c in candidates:
        by_game[c["game"]].append(c)

    lines = []
    lines.append("=" * 56)
    lines.append("   NBA TONIGHT - TOP PLAYS")
    lines.append("=" * 56)

    rank = 1
    for game, players in by_game.items():
        lines.append(f"\n  {game}")
        lines.append("  " + "-" * 30)

        for p in players:
            icon = RATING_ICON.get(p["rating"], "")
            lines.append(f"  #{rank} {p['player']} ({p['position']}) - {p['team']}")
            lines.append(f"      {icon} {p['rating']}")
            line_str = f"{p['line']} pts" if p.get("line") is not None else "N/A"
            lines.append(f"      Line: {line_str}")

            # Signals
            for signal in p["signals"]:
                lines.append(f"      - {signal}")

            # Quick stats
            if p["recent_stats"]:
                s = p["recent_stats"]
                lines.append(
                    f"      Stats (last {s['games']}g): "
                    f"{s['pts']} pts | {s['reb']} reb | {s['ast']} ast | {s['min']} min"
                )

            lines.append("")
            rank += 1

    lines.append("=" * 56)
    return "\n".join(lines)
