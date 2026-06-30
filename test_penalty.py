#!/usr/bin/env python3
"""Quick test to verify penalty shootout logic."""

import json
import sys
sys.path.insert(0, ".")

from scoring import _build_stats, _is_penalty_game, _penalty_winner

# Germany vs Paraguay penalty shootout game (from sampresp.json)
penalty_game = {
    "_id": "679c9c8a5749c4077500e074",
    "away_penalty_score": "4",
    "away_score": "1",
    "away_scorers": "{\"Khvliv Ansisv 42'\"}",
    "away_team_id": "14",
    "away_team_label": "3rd Group A/B/C/D/F",
    "away_team_name_en": "Paraguay",
    "finished": "TRUE",
    "group": "R32",
    "home_penalty_score": "3",
    "home_score": "1",
    "home_scorers": "{\"Kai Havertz 54'\"}",
    "home_team_id": "17",
    "home_team_label": "Winner Group E",
    "home_team_name_en": "Germany",
    "id": "74",
    "local_date": "06/29/2026 16:30",
    "matchday": "4",
    "type": "r32"
}

# Regular draw game (no penalties)
draw_game = {
    "_id": "test-draw",
    "away_score": "1",
    "away_scorers": "{\"Player A 30'\"}",
    "away_team_id": "14",
    "away_team_name_en": "Paraguay",
    "finished": "TRUE",
    "group": "A",
    "home_score": "1",
    "home_scorers": "{\"Player B 45'\"}",
    "home_team_id": "17",
    "home_team_name_en": "Germany",
    "id": "test-draw",
    "local_date": "06/10/2026 12:00",
    "matchday": "1",
    "type": "group"
}

print("=== Testing Penalty Shootout Detection ===")
print(f"Penalty game detected: {_is_penalty_game(penalty_game)}")
print(f"Draw game detected: {_is_penalty_game(draw_game)}")
print()

print("=== Testing Penalty Winner ===")
print(f"Penalty game winner: {_penalty_winner(penalty_game)}")
print(f"Draw game winner: {_penalty_winner(draw_game)}")
print()

# Test with full stats building
print("=== Testing Full Stats Build ===")
games = [penalty_game, draw_game]

# We need to set up minimal config for this test
import config

# Check if teams are in registry
from games_client import load_team_registry
registry = load_team_registry()
print(f"Germany (17) in registry: {'17' in registry}")
print(f"Paraguay (14) in registry: {'14' in registry}")
print()

# Check contender setup
if "Test" not in config.CONTENDERS:
    config.CONTENDERS["Test"] = ["17", "14"]
    config.DARK_HORSE["Test"] = ""
    config.AWARDS = {}
    config.AUCTION_PRICES["Test"] = {}
    config.BUDGETS["Test"] = 0

stats, _, _, warnings, _ = _build_stats(games)

print("=== Germany Stats ===")
germany = stats["17"]
print(f"  Matches: {germany.matches}")
print(f"  Wins: {germany.wins}")
print(f"  Draws: {germany.draws}")
print(f"  Losses: {germany.losses}")
print(f"  Match Pts: {germany.match_pts}")
print(f"  Goals For: {germany.goals_for}")
print(f"  Goals Against: {germany.goals_against}")
print()

print("=== Paraguay Stats ===")
paraguay = stats["14"]
print(f"  Matches: {paraguay.matches}")
print(f"  Wins: {paraguay.wins}")
print(f"  Draws: {paraguay.draws}")
print(f"  Losses: {paraguay.losses}")
print(f"  Match Pts: {paraguay.match_pts}")
print(f"  Goals For: {paraguay.goals_for}")
print(f"  Goals Against: {paraguay.goals_against}")
print()

print("=== Expected Results ===")
print("Penalty game (R32): Paraguay won on penalties 4-3")
print("  - Paraguay should have 1 win, Germany 1 loss")
print("  - Both should have 1 goal each (regular time only)")
print("  - Paraguay should get WIN_PTS, Germany should get 0")
print()
print("Draw game (Group): Regular draw")
print("  - Both should have 1 draw")
print("  - Both should have 1 goal each")
print("  - Both should get DRAW_PTS")
print()

# Verify
assert germany.matches == 2, f"Expected 2 matches for Germany, got {germany.matches}"
assert paraguay.matches == 2, f"Expected 2 matches for Paraguay, got {paraguay.matches}"

# Penalty game: Paraguay won
assert paraguay.wins == 1, f"Expected Paraguay to have 1 win, got {paraguay.wins}"
assert germany.losses == 1, f"Expected Germany to have 1 loss, got {germany.losses}"

# Draw game: both drew
assert germany.draws == 1, f"Expected Germany to have 1 draw, got {germany.draws}"
assert paraguay.draws == 1, f"Expected Paraguay to have 1 draw, got {paraguay.draws}"

# Goals (regular time only)
assert germany.goals_for == 2, f"Expected Germany to have 2 goals for, got {germany.goals_for}"
assert germany.goals_against == 2, f"Expected Germany to have 2 goals against, got {germany.goals_against}"
assert paraguay.goals_for == 2, f"Expected Paraguay to have 2 goals for, got {paraguay.goals_for}"
assert paraguay.goals_against == 2, f"Expected Paraguay to have 2 goals against, got {paraguay.goals_against}"

# Points
win_pts = config.WIN_PTS
draw_pts = config.DRAW_PTS
expected_paraguay_match_pts = win_pts + draw_pts  # 1 win + 1 draw
expected_germany_match_pts = draw_pts  # 1 draw + 1 loss (0 pts)

assert paraguay.match_pts == expected_paraguay_match_pts, \
    f"Expected Paraguay match pts {expected_paraguay_match_pts}, got {paraguay.match_pts}"
assert germany.match_pts == expected_germany_match_pts, \
    f"Expected Germany match pts {expected_germany_match_pts}, got {germany.match_pts}"

print("✅ All tests passed!")
print()
print("Summary:")
print(f"  Paraguay: {paraguay.wins}W-{paraguay.draws}D-{paraguay.losses}L, {paraguay.match_pts} pts")
print(f"  Germany: {germany.wins}W-{germany.draws}D-{germany.losses}L, {germany.match_pts} pts")