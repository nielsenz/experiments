"""
Economic health data fetchers for Las Vegas metro area.

APIs used (all free):
  - BLS API v1              — Unemployment, CPI, employment by sector. No key needed.
  - Census Bureau           — Population, housing values, rent. No key needed.
  - EIA API v2              — Gas prices (PADD 5 / West). Free key or DEMO_KEY.
  - FRED (St. Louis Fed)    — Mortgage rates, economic indicators. Free key required.

Notes:
  - BLS v1 is rate-limited to 25 requests/day. v2 (free registration) allows 500/day.
  - FRED requires free registration at https://fred.stlouisfed.org/docs/api/api_key.html
  - For production use, set FRED_API_KEY and EIA_API_KEY environment variables.
"""

import os
import requests
from datetime import datetime

BLS_BASE = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
CENSUS_BASE = "https://api.census.gov/data"

# BLS Series IDs for Las Vegas-Henderson-Paradise, NV MSA
BLS_SERIES = {
    "unemployment": "LAUCN320030000000003",      # Unemployment rate (Clark County)
    "total_nonfarm": "SMU32298200000000001",      # Total nonfarm employment (thousands)
    "leisure_hosp": "SMU32298207000000001",       # Leisure & hospitality employment
    "construction": "SMU32298202000000001",       # Construction employment
    "trade_transport": "SMU32298204000000001",    # Trade, transportation, utilities
}


class EconomicFetcher:
    def __init__(self, demo=False, verbose=False, quiet=False):
        self.demo = demo
        self.verbose = verbose
        self.quiet = quiet
        self.fred_key = os.environ.get("FRED_API_KEY", "")
        self.eia_key = os.environ.get("EIA_API_KEY", "DEMO_KEY")

    def _log(self, source, data):
        if self.verbose and not self.quiet:
            print(f"    [DEBUG] {source}: {data}")

    def fetch_all(self):
        """Fetch all economic indicators."""
        data = {}
        sources = [
            ("unemployment", self._fetch_unemployment),
            ("employment_total", self._fetch_total_employment),
            ("employment_leisure", self._fetch_leisure_employment),
            ("employment_construction", self._fetch_construction_employment),
            ("cpi", self._fetch_cpi),
            ("population", self._fetch_population),
            ("housing", self._fetch_housing),
            ("gas_prices", self._fetch_gas_prices),
            ("mortgage_rate", self._fetch_mortgage_rate),
        ]
        for key, func in sources:
            try:
                result = func()
                data[key] = result
                status = "✅"
            except Exception as e:
                data[key] = {"error": str(e)}
                status = "⚠️ "
            if not self.quiet:
                label = key.replace("_", " ").title()
                val = self._summary(key, data[key])
                print(f"  {status} {label:.<30s} {val}")
            self._log(key, data[key])
        return data

    def _summary(self, key, data):
        if "error" in data:
            return f"unavailable ({data['error'][:40]})"
        summaries = {
            "unemployment": lambda d: f"{d['rate']}% ({d['period']})",
            "employment_total": lambda d: f"{d['jobs_k']}K jobs ({d['period']}) {d.get('yoy_change', '')}",
            "employment_leisure": lambda d: f"{d['jobs_k']}K jobs ({d['period']})",
            "employment_construction": lambda d: f"{d['jobs_k']}K jobs ({d['period']})",
            "cpi": lambda d: f"{d['index']} ({d['period']}) — {d.get('region', 'West')}",
            "population": lambda d: f"{int(d['population']):,} ({d['name']})",
            "housing": lambda d: f"Median home ${int(d['median_home_value']):,} / Rent ${int(d['median_rent']):,}",
            "gas_prices": lambda d: f"${d['price']}/gal ({d['period']}) — {d.get('region', 'West')}",
            "mortgage_rate": lambda d: f"{d['rate']}% 30yr fixed ({d['date']})",
        }
        fn = summaries.get(key, lambda d: str(d)[:60])
        try:
            return fn(data)
        except Exception:
            return str(data)[:60]

    # ── BLS helpers ─────────────────────────────────────────
    def _bls_fetch(self, series_id, start_year=None, end_year=None):
        if start_year is None:
            start_year = str(datetime.now().year - 2)  # Go back 2 years for LAU publication lag
        if end_year is None:
            end_year = str(datetime.now().year)
        payload = {
            "seriesid": [series_id],
            "startyear": start_year,
            "endyear": end_year,
        }
        r = requests.post(BLS_BASE, json=payload, timeout=15)
        r.raise_for_status()
        resp = r.json()
        if resp["status"] != "REQUEST_SUCCEEDED":
            raise ValueError(f"BLS error: {resp.get('message', resp['status'])}")
        data = resp["Results"]["series"][0]["data"]
        if not data:
            raise ValueError(f"No BLS data for {series_id} in {start_year}-{end_year}")
        return data

    # ── Unemployment ────────────────────────────────────────
    def _fetch_unemployment(self):
        if self.demo:
            return {"rate": 5.2, "period": "Jan 2026", "series": "Las Vegas MSA"}
        data = self._bls_fetch(BLS_SERIES["unemployment"])
        latest = data[0]
        return {
            "rate": float(latest["value"]),
            "period": f"{latest['periodName']} {latest['year']}",
            "series": "Las Vegas-Henderson-Paradise MSA",
        }

    # ── Total Nonfarm Employment ────────────────────────────
    def _fetch_total_employment(self):
        if self.demo:
            return {
                "jobs_k": 1105.2,
                "period": "Jan 2026",
                "yoy_change": "+22.3K YoY",
            }
        data = self._bls_fetch(BLS_SERIES["total_nonfarm"])
        latest = data[0]
        # Find same month prior year for YoY comparison
        prev = [
            d for d in data
            if d["year"] == str(int(latest["year"]) - 1)
            and d["period"] == latest["period"]
        ]
        yoy = ""
        if prev:
            change = float(latest["value"]) - float(prev[0]["value"])
            yoy = f"{change:+.1f}K YoY"
        return {
            "jobs_k": float(latest["value"]),
            "period": f"{latest['periodName']} {latest['year']}",
            "yoy_change": yoy,
        }

    # ── Leisure & Hospitality ───────────────────────────────
    def _fetch_leisure_employment(self):
        if self.demo:
            return {"jobs_k": 298.5, "period": "Jan 2026"}
        data = self._bls_fetch(BLS_SERIES["leisure_hosp"])
        latest = data[0]
        return {
            "jobs_k": float(latest["value"]),
            "period": f"{latest['periodName']} {latest['year']}",
        }

    # ── Construction ────────────────────────────────────────
    def _fetch_construction_employment(self):
        if self.demo:
            return {"jobs_k": 72.8, "period": "Jan 2026"}
        data = self._bls_fetch(BLS_SERIES["construction"])
        latest = data[0]
        return {
            "jobs_k": float(latest["value"]),
            "period": f"{latest['periodName']} {latest['year']}",
        }

    # ── CPI (West Region) ──────────────────────────────────
    def _fetch_cpi(self):
        if self.demo:
            return {"index": 318.4, "period": "Jan 2026", "region": "West Urban"}
        # CUURS400SA0 = CPI-U All Items, West Region
        data = self._bls_fetch("CUURS400SA0")
        latest = data[0]
        return {
            "index": float(latest["value"]),
            "period": f"{latest['periodName']} {latest['year']}",
            "region": "West Urban",
        }

    # ── Census Population ───────────────────────────────────
    def _fetch_population(self):
        if self.demo:
            return {"population": 2320800, "name": "Clark County, NV", "year": 2022}
        # PEP endpoint is unreliable; use ACS 5-year estimate (B01003_001E = total population)
        url = f"{CENSUS_BASE}/2022/acs/acs5"
        params = {"get": "B01003_001E,NAME", "for": "county:003", "in": "state:32"}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if len(data) > 1:
            return {
                "population": int(data[1][0]),
                "name": data[1][1],
                "year": 2022,
            }
        raise ValueError("No population data")

    # ── Census Housing ──────────────────────────────────────
    def _fetch_housing(self):
        if self.demo:
            return {
                "median_home_value": 395400,
                "median_rent": 1485,
                "name": "Clark County, NV",
            }
        url = f"{CENSUS_BASE}/2023/acs/acs1"
        params = {
            "get": "B25077_001E,B25064_001E,NAME",
            "for": "county:003",
            "in": "state:32",
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if len(data) > 1:
            return {
                "median_home_value": int(data[1][0]) if data[1][0] else 0,
                "median_rent": int(data[1][1]) if data[1][1] else 0,
                "name": data[1][2],
            }
        raise ValueError("No housing data")

    # ── EIA Gas Prices ──────────────────────────────────────
    def _fetch_gas_prices(self):
        if self.demo:
            return {"price": 3.89, "period": "2026-02-17", "region": "PADD 5 (West Coast)"}
        url = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
        params = {
            "frequency": "weekly",
            "data[0]": "value",
            "facets[product][]": "EPM0",
            "facets[duoarea][]": "R50",
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": "4",
            "api_key": self.eia_key,
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        series = r.json().get("response", {}).get("data", [])
        if series:
            return {
                "price": float(series[0]["value"]),
                "period": series[0]["period"],
                "region": "PADD 5 (West Coast)",
            }
        raise ValueError("No gas price data")

    # ── FRED Mortgage Rate ──────────────────────────────────
    def _fetch_mortgage_rate(self):
        if self.demo:
            return {"rate": 6.87, "date": "2026-02-20"}
        if not self.fred_key:
            raise ValueError("Set FRED_API_KEY env var (free at fred.stlouisfed.org)")
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": "MORTGAGE30US",
            "api_key": self.fred_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": "4",
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        if obs:
            return {"rate": float(obs[0]["value"]), "date": obs[0]["date"]}
        raise ValueError("No FRED data")
