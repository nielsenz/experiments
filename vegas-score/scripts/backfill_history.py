#!/usr/bin/env python3
"""
Backfill Vegas score history with historical economic snapshots.

This script creates one snapshot per month for the requested lookback window.
Environmental history is not backfilled (most sources are current-conditions APIs),
so snapshots include economic score and composite (equal to economic when env is missing).
"""

from __future__ import annotations

import argparse
import os
from datetime import date, datetime
from typing import Any

import requests

from history import append_snapshot
from scoring import ScoreEngine

BLS_BASE = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
CENSUS_BASE = "https://api.census.gov/data"
EIA_BASE = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"

BLS_SERIES = {
    "unemployment": "LAUCN320030000000003",
    "total_nonfarm": "SMU32298200000000001",
    "leisure_hosp": "SMU32298207000000001",
    "cpi_west": "CUURS400SA0",
}


def month_starts(end_month: date, months: int) -> list[date]:
    out = []
    y = end_month.year
    m = end_month.month
    for _ in range(months):
        out.append(date(y, m, 1))
        m -= 1
        if m == 0:
            y -= 1
            m = 12
    out.reverse()
    return out


def bls_fetch(series_id: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    payload = {
        "seriesid": [series_id],
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    r = requests.post(BLS_BASE, json=payload, timeout=30)
    r.raise_for_status()
    resp = r.json()
    if resp.get("status") != "REQUEST_SUCCEEDED":
        raise ValueError(f"BLS request failed: {resp.get('message', resp.get('status'))}")
    return resp["Results"]["series"][0]["data"]


def bls_month_map(series_rows: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in series_rows:
        period = row.get("period", "")
        if not period.startswith("M") or period == "M13":
            continue
        ym = f"{row['year']}-{period[1:]}"
        try:
            out[ym] = float(row["value"])
        except (TypeError, ValueError):
            continue
    return out


def eia_monthly_map(api_key: str, start_month: date, end_month: date) -> dict[str, float]:
    params = {
        "frequency": "weekly",
        "data[0]": "value",
        "facets[product][]": "EPM0",
        "facets[duoarea][]": "R50",
        "start": start_month.strftime("%Y-%m"),
        "end": end_month.strftime("%Y-%m"),
        "sort[0][column]": "period",
        "sort[0][direction]": "asc",
        "length": "5000",
        "api_key": api_key,
    }
    r = requests.get(EIA_BASE, params=params, timeout=30)
    r.raise_for_status()
    rows = r.json().get("response", {}).get("data", [])
    by_month: dict[str, list[float]] = {}
    for row in rows:
        p = str(row.get("period", ""))
        if len(p) < 7:
            continue
        ym = p[:7]
        try:
            val = float(row["value"])
        except (TypeError, ValueError):
            continue
        by_month.setdefault(ym, []).append(val)
    return {k: sum(v) / len(v) for k, v in by_month.items() if v}


def fred_monthly_map(api_key: str, start_month: date, end_month: date) -> dict[str, float]:
    params = {
        "series_id": "MORTGAGE30US",
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_month.isoformat(),
        "observation_end": end_month.isoformat(),
    }
    r = requests.get(FRED_BASE, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json().get("observations", [])
    by_month: dict[str, list[float]] = {}
    for row in obs:
        d = str(row.get("date", ""))
        v = str(row.get("value", ""))
        if v == "." or len(d) < 7:
            continue
        ym = d[:7]
        try:
            rate = float(v)
        except ValueError:
            continue
        by_month.setdefault(ym, []).append(rate)
    return {k: sum(v) / len(v) for k, v in by_month.items() if v}


def census_housing(year: int) -> dict[str, int] | None:
    url = f"{CENSUS_BASE}/{year}/acs/acs1"
    params = {
        "get": "B25077_001E,B25064_001E,NAME",
        "for": "county:003",
        "in": "state:32",
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    if len(data) <= 1:
        return None
    try:
        return {
            "median_home_value": int(data[1][0]) if data[1][0] else 0,
            "median_rent": int(data[1][1]) if data[1][1] else 0,
        }
    except (TypeError, ValueError, IndexError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Vegas score history")
    parser.add_argument("--months", type=int, default=13, help="Months to backfill")
    parser.add_argument(
        "--history-file",
        default=".vegas_score_history.jsonl",
        help="History JSONL file path",
    )
    args = parser.parse_args()

    today = date.today()
    end_month = date(today.year, today.month, 1)
    months = month_starts(end_month, args.months)
    start_year = months[0].year - 1
    end_year = months[-1].year

    unemp = bls_month_map(bls_fetch(BLS_SERIES["unemployment"], start_year, end_year))
    total = bls_month_map(bls_fetch(BLS_SERIES["total_nonfarm"], start_year, end_year))
    leisure = bls_month_map(bls_fetch(BLS_SERIES["leisure_hosp"], start_year, end_year))
    cpi = bls_month_map(bls_fetch(BLS_SERIES["cpi_west"], start_year, end_year))

    eia_key = os.environ.get("EIA_API_KEY", "DEMO_KEY")
    gas = eia_monthly_map(eia_key, months[0], months[-1])

    fred_key = os.environ.get("FRED_API_KEY", "")
    mortgage = fred_monthly_map(fred_key, months[0], months[-1]) if fred_key else {}

    housing_cache: dict[int, dict[str, int] | None] = {}
    engine = ScoreEngine()

    written = 0
    for month in months:
        ym = month.strftime("%Y-%m")
        econ_data: dict[str, Any] = {}

        if ym in unemp:
            econ_data["unemployment"] = {"rate": unemp[ym]}

        if ym in total:
            prev_ym = f"{month.year - 1:04d}-{month.month:02d}"
            yoy = ""
            if prev_ym in total:
                yoy_delta = total[ym] - total[prev_ym]
                yoy = f"{yoy_delta:+.1f}K YoY"
            econ_data["employment_total"] = {"jobs_k": total[ym], "yoy_change": yoy}

        if ym in leisure:
            econ_data["employment_leisure"] = {"jobs_k": leisure[ym]}

        if ym in cpi:
            econ_data["cpi"] = {"index": cpi[ym]}

        if ym in gas:
            econ_data["gas_prices"] = {"price": gas[ym]}

        if ym in mortgage:
            econ_data["mortgage_rate"] = {"rate": mortgage[ym]}

        if month.year not in housing_cache:
            housing_cache[month.year] = census_housing(month.year)
        if housing_cache[month.year]:
            econ_data["housing"] = housing_cache[month.year]

        if not econ_data:
            continue

        econ_scores = engine.score_economic(econ_data)
        econ_overall = econ_scores.get("overall")
        ts = datetime(month.year, month.month, 1, 12, 0, 0).isoformat()
        snapshot = {
            "timestamp": ts,
            "env_overall": None,
            "econ_overall": econ_overall,
            "composite": econ_overall,
            "demo": False,
            "source": "historical_backfill_economic",
        }
        append_snapshot(args.history_file, snapshot)
        written += 1

    print(f"Backfilled {written} monthly snapshots to {args.history_file}")
    if not fred_key:
        print("Note: FRED_API_KEY not set, mortgage component omitted.")


if __name__ == "__main__":
    main()
