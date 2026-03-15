from scrapers.nba import get_todays_games
from scrapers.rotowire import get_projected_lineups
from scrapers.fantasypros import get_defense_vs_position
from analysis.engine import run_analysis
from output.formatter import format_results


def main():
    print("Fetching today's games...")
    games = get_todays_games()
    if not games:
        print("No games today.")
        return

    print(f"  {len(games)} games tonight\n")

    print("Fetching projected lineups (RotoWire)...")
    lineups = get_projected_lineups()
    print(f"  {len(lineups)} teams loaded\n")

    print("Fetching Defense vs Position (FantasyPros)...")
    dvp = get_defense_vs_position()
    print("  Done\n")

    print("Running analysis...")
    candidates = run_analysis(games, lineups, dvp)

    print("\n")
    print(format_results(candidates))


if __name__ == "__main__":
    main()
