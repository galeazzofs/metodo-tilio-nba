"""Shared analysis pipeline for manual and scheduled triggers."""
from scrapers.nba import (
    get_todays_games, get_team_defense_vs_position, get_team_defense_tracking,
    get_team_pace,
)
from scrapers.rotowire import get_projected_lineups
from scrapers.fantasypros import get_defense_vs_position
from scrapers.odds import get_event_ids, get_player_lines
from analysis.engine import run_analysis


def run_pipeline(games=None):
    """
    Execute the full analysis pipeline.
    Returns (stats_dict, games_list) or (None, games) if no games.
    stats_dict: {"pts": [...], "ast": [...], "reb": [...], "three_pt": [...]}
    """
    if games is None:
        print("Buscando jogos de hoje...")
        games = get_todays_games()

    if not games:
        print("Nenhum jogo hoje.")
        return None, games

    print(f"  {len(games)} jogos esta noite")

    print("Buscando lineups projetados (RotoWire)...")
    lineups = get_projected_lineups()
    print(f"  {len(lineups)} times carregados")

    print("Buscando Defesa por Posição — PTS (FantasyPros)...")
    dvp = get_defense_vs_position()
    print("  Concluído")

    print("Buscando Defesa por Posição — AST/REB/3PT (NBA API)...")
    team_defense = get_team_defense_vs_position()
    print("  Concluído")

    print("Buscando tracking stats defensivos (NBA API)...")
    tracking_data = get_team_defense_tracking()
    print("  Concluído")

    print("Buscando pace dos times (NBA API)...")
    pace_map, median_pace = get_team_pace()
    print(f"  Concluído (mediana: {median_pace:.1f})")

    print("Rodando análise (4 stats)...")
    stats = run_analysis(games, lineups, dvp, team_defense, tracking_data, pace_map, median_pace)
    total = sum(len(v) for v in stats.values())
    print(f"  {total} candidato(s) encontrado(s)")

    print("Buscando linhas de apostas (The Odds API)...")
    event_ids = get_event_ids(games)
    lines = get_player_lines(stats, event_ids)
    for stat_key, candidates in stats.items():
        for c in candidates:
            player_lines = lines.get(c["player_name"], {})
            if isinstance(player_lines, dict):
                val = player_lines.get(stat_key)
                odds = player_lines.get(f"{stat_key}_odds")
                c["line"] = {"value": val, "odds": odds} if val else None
            else:
                c["line"] = None

    return stats, games
