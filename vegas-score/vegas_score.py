#!/usr/bin/env python3
"""
🎰 Las Vegas Health Score CLI
A dual-index tracking environmental and economic health for the Las Vegas valley.
Focused on the Seven Hills / Henderson area.

Usage:
    python vegas_score.py              # Live data (requires internet)
    python vegas_score.py --demo       # Demo mode with sample data
    python vegas_score.py --verbose    # Show raw API responses
    python vegas_score.py --json       # Output as JSON
"""

import argparse
import json
import sys
from datetime import datetime

from fetchers.environmental import EnvironmentalFetcher
from fetchers.economic import EconomicFetcher
from scoring import ScoreEngine
from display import Display


def main():
    parser = argparse.ArgumentParser(
        description="🎰 Las Vegas Health Score — Environmental & Economic Index"
    )
    parser.add_argument("--demo", action="store_true", help="Use sample data (no API calls)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show raw API data")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of CLI display")
    parser.add_argument("--env-only", action="store_true", help="Only show environmental score")
    parser.add_argument("--econ-only", action="store_true", help="Only show economic score")
    args = parser.parse_args()

    display = Display()
    quiet = args.json  # suppress fetch progress in JSON mode

    env_fetcher = EnvironmentalFetcher(demo=args.demo, verbose=args.verbose, quiet=quiet)
    econ_fetcher = EconomicFetcher(demo=args.demo, verbose=args.verbose, quiet=quiet)

    if not quiet:
        display.header()

    env_data = {}
    econ_data = {}

    if not args.econ_only:
        if not quiet:
            display.section("ENVIRONMENTAL HEALTH")
        env_data = env_fetcher.fetch_all()

    if not args.env_only:
        if not quiet:
            display.section("ECONOMIC HEALTH")
        econ_data = econ_fetcher.fetch_all()

    # ── Score ───────────────────────────────────────────────
    engine = ScoreEngine()

    if args.json:
        output = {"timestamp": datetime.now().isoformat(), "location": "Seven Hills, Henderson, NV"}
        if env_data:
            env_scores = engine.score_environmental(env_data)
            output["environmental"] = env_scores
        if econ_data:
            econ_scores = engine.score_economic(econ_data)
            output["economic"] = econ_scores
        if env_data and econ_data:
            output["composite"] = engine.composite(
                output.get("environmental", {}).get("overall", 0),
                output.get("economic", {}).get("overall", 0),
            )
        print(json.dumps(output, indent=2))
    else:
        env_score_data = None
        econ_score_data = None

        if env_data:
            env_score_data = engine.score_environmental(env_data)
            display.section("ENVIRONMENTAL SCORES")
            display.scores(env_score_data)

        if econ_data:
            econ_score_data = engine.score_economic(econ_data)
            display.section("ECONOMIC SCORES")
            display.scores(econ_score_data)

        if env_score_data and econ_score_data:
            composite = engine.composite(
                env_score_data["overall"], econ_score_data["overall"]
            )
            display.composite(composite, env_score_data["overall"], econ_score_data["overall"])

        display.footer(demo=args.demo)


if __name__ == "__main__":
    main()
