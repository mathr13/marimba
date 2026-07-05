#!/usr/bin/env python3
"""Test to verify qualification points are awarded for all knockout stages."""

import json
import sys
sys.path.insert(0, ".")

from scoring import _build_stats
import config
from games_client import load_team_registry

# Set up minimal config for testing
if "Test" not in config.CONTENDERS:
    config.CONTENDERS["Test"] = ["17", "14", "9", "1"]
    config.DARK_HORSE["Test"] = "14"  # Paraguay as dark horse (Tier 2)
    config.AWARDS = {}
    config.AUCTION_PRICES["Test"] = {}
    config.BUDGETS["Test"] = 0

# Verify teams are in registry
registry = load_team_registry()
assert "17" in registry, "Germany (17) not in registry"
assert "14" in registry, "Paraguay (14) not in registry"
assert "9" in registry, "Brazil (9) not in registry"
assert "1" in registry, "Mexico (1) not in registry"

# Create test games for each knockout stage
# Each game represents a team advancing to the next stage
games = [
    # R32: Germany vs Paraguay
    {
        "_id": "r32-game",
        "finished": "TRUE",
        "type": "r32",
        "home_team_id": "17",
        "home_team_name_en": "Germany",
        "away_team_id": "14",
        "away_team_name_en": "Paraguay",
        "home_score": "2",
        "away_score": "1",
        "home_scorers": "{}",
        "away_scorers": "{}",
        "local_date": "06/29/2026 16:30",
    },
    # R16: Germany vs Mexico
    {
        "_id": "r16-game",
        "finished": "TRUE",
        "type": "r16",
        "home_team_id": "17",
        "home_team_name_en": "Germany",
        "away_team_id": "1",
        "away_team_name_en": "Mexico",
        "home_score": "3",
        "away_score": "2",
        "home_scorers": "{}",
        "away_scorers": "{}",
        "local_date": "07/03/2026 16:30",
    },
    # QF: Germany vs Brazil
    {
        "_id": "qf-game",
        "finished": "TRUE",
        "type": "qf",
        "home_team_id": "17",
        "home_team_name_en": "Germany",
        "away_team_id": "9",
        "away_team_name_en": "Brazil",
        "home_score": "2",
        "away_score": "1",
        "home_scorers": "{}",
        "away_scorers": "{}",
        "local_date": "07/07/2026 16:30",
    },
    # SF: Germany vs (placeholder - using Mexico again for test)
    {
        "_id": "sf-game",
        "finished": "TRUE",
        "type": "sf",
        "home_team_id": "17",
        "home_team_name_en": "Germany",
        "away_team_id": "1",
        "away_team_name_en": "Mexico",
        "home_score": "2",
        "away_score": "0",
        "home_scorers": "{}",
        "away_scorers": "{}",
        "local_date": "07/11/2026 16:30",
    },
    # Final: Germany vs (placeholder - using Brazil again for test)
    {
        "_id": "final-game",
        "finished": "TRUE",
        "type": "final",
        "home_team_id": "17",
        "home_team_name_en": "Germany",
        "away_team_id": "9",
        "away_team_name_en": "Brazil",
        "home_score": "1",
        "away_score": "0",
        "home_scorers": "{}",
        "away_scorers": "{}",
        "local_date": "07/15/2026 16:30",
    },
]

print("=== Testing Qualification Points for All Knockout Stages ===\n")

stats, _, _, warnings, _ = _build_stats(games)

# Check Germany's qualification points
germany = stats["17"]
print(f"Germany qualification points: {germany.qualify_pts}")
print(f"  - R32: +{config.QUALIFY_BONUS[1]} (Tier 1)")
print(f"  - R16: +{config.QUALIFY_BONUS[1]}")
print(f"  - QF: +{config.QUALIFY_BONUS[1]}")
print(f"  - SF: +{config.QUALIFY_BONUS[1]}")
print(f"  - Final: +{config.QUALIFY_BONUS[1]}")
print(f"  - Expected total: {5 * config.QUALIFY_BONUS[1]}")
print()

# Verify Germany reached all stages
assert germany.qualify_pts == 5 * config.QUALIFY_BONUS[1], \
    f"Expected Germany to have {5 * config.QUALIFY_BONUS[1]} qualification points, got {germany.qualify_pts}"

# Check that teams eliminated at each stage only get points for stages they reached
# Paraguay (eliminated in R32)
paraguay = stats["14"]
print(f"Paraguay qualification points: {paraguay.qualify_pts}")
print(f"  - R32 only: +{config.QUALIFY_BONUS[2]}")
print(f"  - Expected total: {config.QUALIFY_BONUS[2]}")
print()
assert paraguay.qualify_pts == config.QUALIFY_BONUS[2], \
    f"Expected Paraguay to have {config.QUALIFY_BONUS[2]} qualification points, got {paraguay.qualify_pts}"

# Mexico (reached R16)
mexico = stats["1"]
print(f"Mexico qualification points: {mexico.qualify_pts}")
print(f"  - R32: +{config.QUALIFY_BONUS[1]}")
print(f"  - R16: +{config.QUALIFY_BONUS[1]}")
print(f"  - Expected total: {2 * config.QUALIFY_BONUS[1]}")
print()
assert mexico.qualify_pts == 2 * config.QUALIFY_BONUS[1], \
    f"Expected Mexico to have {2 * config.QUALIFY_BONUS[1]} qualification points, got {mexico.qualify_pts}"

# Brazil (reached QF and Final)
brazil = stats["9"]
print(f"Brazil qualification points: {brazil.qualify_pts}")
print(f"  - QF: +{config.QUALIFY_BONUS[1]}")
print(f"  - Final: +{config.QUALIFY_BONUS[1]}")
print(f"  - Expected total: {2 * config.QUALIFY_BONUS[1]}")
print()
assert brazil.qualify_pts == 2 * config.QUALIFY_BONUS[1], \
    f"Expected Brazil to have {2 * config.QUALIFY_BONUS[1]} qualification points, got {brazil.qualify_pts}"

# Check knockout points for final
print(f"Germany knockout points: {germany.knockout_pts}")
print(f"  - QF bonus: +{config.QF_BONUS}")
print(f"  - SF bonus: +{config.SF_BONUS}")
print(f"  - Final bonus: +{config.FINAL_BONUS}")
print(f"  - Champion bonus: +{config.CHAMPION_BONUS}")
print(f"  - Expected total: {config.QF_BONUS + config.SF_BONUS + config.FINAL_BONUS + config.CHAMPION_BONUS}")
print()
expected_knockout = config.QF_BONUS + config.SF_BONUS + config.FINAL_BONUS + config.CHAMPION_BONUS
assert germany.knockout_pts == expected_knockout, \
    f"Expected Germany to have {expected_knockout} knockout points, got {germany.knockout_pts}"

# Check Brazil (runner-up - only played QF and Final)
print(f"Brazil knockout points: {brazil.knockout_pts}")
print(f"  - QF bonus: +{config.QF_BONUS}")
print(f"  - Final bonus: +{config.FINAL_BONUS}")
print(f"  - Runner-up bonus: +{config.RUNNER_UP_BONUS}")
print(f"  - Expected total: {config.QF_BONUS + config.FINAL_BONUS + config.RUNNER_UP_BONUS}")
print()
expected_brazil_knockout = config.QF_BONUS + config.FINAL_BONUS + config.RUNNER_UP_BONUS
assert brazil.knockout_pts == expected_brazil_knockout, \
    f"Expected Brazil to have {expected_brazil_knockout} knockout points, got {brazil.knockout_pts}"

# Test dark horse points (should start from R16, not R32)
print("\n=== Testing Dark Horse Points (start from R16) ===\n")

# Get dark horse points for Test contender
_, _, contender_dh_pts, _, _ = _build_stats(games)
test_dh_pts = contender_dh_pts.get("Test", 0.0)

print(f"Paraguay (dark horse) eliminated in R32: {paraguay.qualify_pts} qualify pts")
print(f"  - Dark horse points: {test_dh_pts}")
print(f"  - Expected: 0.0 (dark horse bonus only starts from R16)")
print()
assert test_dh_pts == 0.0, \
    f"Expected 0.0 dark horse points for R32 elimination, got {test_dh_pts}"

# Test with dark horse reaching R16
# Change dark horse to Mexico for this test
config.DARK_HORSE["Test"] = "1"
games_r16 = [
    # R32: Mexico vs Paraguay (Mexico wins)
    {
        "_id": "r32-game-2",
        "finished": "TRUE",
        "type": "r32",
        "home_team_id": "1",
        "home_team_name_en": "Mexico",
        "away_team_id": "14",
        "away_team_name_en": "Paraguay",
        "home_score": "2",
        "away_score": "1",
        "home_scorers": "{}",
        "away_scorers": "{}",
        "local_date": "06/29/2026 16:30",
    },
    # R16: Mexico vs Brazil (Mexico eliminated)
    {
        "_id": "r16-game-2",
        "finished": "TRUE",
        "type": "r16",
        "home_team_id": "1",
        "home_team_name_en": "Mexico",
        "away_team_id": "9",
        "away_team_name_en": "Brazil",
        "home_score": "1",
        "away_score": "2",
        "home_scorers": "{}",
        "away_scorers": "{}",
        "local_date": "07/03/2026 16:30",
    },
]

stats_r16, _, _, _, _ = _build_stats(games_r16)
mexico_r16 = stats_r16["1"]
paraguay_r32 = stats_r16["14"]

print(f"Paraguay eliminated in R32: {paraguay_r32.qualify_pts} qualify pts")
print(f"  - Dark horse points: 0.0 (Paraguay is not the dark horse)")
print(f"  - Expected: 0.0")
assert paraguay_r32.qualify_pts == config.QUALIFY_BONUS[1], \
    f"Expected Paraguay to have {config.QUALIFY_BONUS[1]} qualification points, got {paraguay_r32.qualify_pts}"

print(f"\nMexico (dark horse) reached R16: {mexico_r16.qualify_pts} qualify pts")
print(f"  - Dark horse points: {config.DARK_HORSE_BONUS['r16']}")
print(f"  - Expected: {config.DARK_HORSE_BONUS['r16']}")
assert mexico_r16.qualify_pts == 2 * config.QUALIFY_BONUS[1], \
    f"Expected Mexico to have {2 * config.QUALIFY_BONUS[1]} qualification points, got {mexico_r16.qualify_pts}"

# Verify dark horse points are awarded for reaching R16
_, _, dh_pts_r16, _, _ = _build_stats(games_r16)
mexico_dh = dh_pts_r16.get("Test", 0.0)
print(f"\n✅ Dark horse bonus for reaching R16: {mexico_dh}")
assert mexico_dh == config.DARK_HORSE_BONUS["r16"], \
    f"Expected dark horse bonus {config.DARK_HORSE_BONUS['r16']}, got {mexico_dh}"

print("\n✅ All qualification points tests passed!")
print()
print("Summary:")
print(f"  Germany (champion): {germany.qualify_pts} qualify pts + {germany.knockout_pts} knockout pts")
print(f"  Brazil (runner-up): {brazil.qualify_pts} qualify pts + {brazil.knockout_pts} knockout pts")
print(f"  Mexico (R16): {mexico.qualify_pts} qualify pts")
print(f"  Paraguay (R32): {paraguay.qualify_pts} qualify pts")
print(f"  Dark horse starts from R16: ✅")
