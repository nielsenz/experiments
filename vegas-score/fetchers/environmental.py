"""
Environmental health data fetchers for Las Vegas / Seven Hills area.

APIs used (all free, most require no key):
  - NWS (weather.gov)       — Forecast, temperature, wind, alerts. No key.
  - AirNow (airnow.gov)     — AQI, PM2.5, ozone. No key for public REST.
  - EPA Envirofacts          — UV index by ZIP. No key.
  - USGS Water Services      — River gauge / flow data. No key.
  - USBR RISE               — Lake Mead elevation. No key.
  - US Drought Monitor       — Drought severity by county. No key.
"""

import requests
from datetime import datetime, timedelta

SEVEN_HILLS_LAT = 36.0611
SEVEN_HILLS_LON = -115.1747
HEADERS = {"User-Agent": "VegasHealthScore/1.0 (github.com/vegashealthscore)"}


class EnvironmentalFetcher:
    def __init__(self, demo=False, verbose=False, quiet=False):
        self.demo = demo
        self.verbose = verbose
        self.quiet = quiet

    def _log(self, source, data):
        if self.verbose and not self.quiet:
            print(f"    [DEBUG] {source}: {data}")

    def fetch_all(self):
        """Fetch all environmental indicators. Returns dict of raw data."""
        data = {}
        sources = [
            ("weather", self._fetch_weather),
            ("alerts", self._fetch_alerts),
            ("aqi", self._fetch_aqi),
            ("uv", self._fetch_uv),
            ("water_level", self._fetch_lake_mead),
            ("river_flow", self._fetch_usgs_water),
            ("drought", self._fetch_drought),
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
        """One-line summary for CLI output."""
        if "error" in data:
            return f"unavailable ({data['error'][:40]})"
        summaries = {
            "weather": lambda d: f"{d.get('temperature', '?')} — {d.get('short_forecast', '?')}",
            "alerts": lambda d: f"{d.get('clark_county_alerts', 0)} active alert(s)",
            "aqi": lambda d: f"AQI {d.get('aqi', '?')} ({d.get('category', '?')}) — {d.get('pollutant', '?')}",
            "uv": lambda d: f"UV Index {d.get('uv_index', '?')} {'⚠️  ALERT' if d.get('uv_alert') else ''}",
            "water_level": lambda d: f"{d.get('elevation_ft', '?')} ft ({d.get('pct_capacity', '?')}% capacity)",
            "river_flow": lambda d: f"{d.get('value', '?')} {d.get('unit', '')} at {d.get('site', '?')}",
            "drought": lambda d: f"{d.get('category', '?')} — {d.get('pct_area', '?')}% of county",
        }
        fn = summaries.get(key, lambda d: str(d)[:60])
        try:
            return fn(data)
        except Exception:
            return str(data)[:60]

    # ── NWS Weather ─────────────────────────────────────────
    def _fetch_weather(self):
        if self.demo:
            return self._demo_weather()
        url = f"https://api.weather.gov/points/{SEVEN_HILLS_LAT},{SEVEN_HILLS_LON}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        forecast_url = r.json()["properties"]["forecast"]
        r2 = requests.get(forecast_url, headers=HEADERS, timeout=15)
        r2.raise_for_status()
        p = r2.json()["properties"]["periods"][0]
        return {
            "temperature": f"{p['temperature']}°{p['temperatureUnit']}",
            "wind_speed": p["windSpeed"],
            "wind_dir": p["windDirection"],
            "short_forecast": p["shortForecast"],
            "detailed": p["detailedForecast"],
            "is_daytime": p["isDaytime"],
            "period_name": p["name"],
        }

    def _demo_weather(self):
        return {
            "temperature": "72°F",
            "wind_speed": "10 to 15 mph",
            "wind_dir": "SW",
            "short_forecast": "Sunny",
            "detailed": "Sunny, with a high near 72. Southwest wind 10 to 15 mph.",
            "is_daytime": True,
            "period_name": "This Afternoon",
        }

    # ── NWS Alerts ──────────────────────────────────────────
    def _fetch_alerts(self):
        if self.demo:
            return {"clark_county_alerts": 0, "alerts": []}
        url = "https://api.weather.gov/alerts/active?area=NV"
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        features = r.json().get("features", [])
        clark = [
            {
                "event": f["properties"]["event"],
                "severity": f["properties"]["severity"],
                "headline": f["properties"]["headline"],
            }
            for f in features
            if "Clark" in str(f.get("properties", {}).get("areaDesc", ""))
        ]
        return {"clark_county_alerts": len(clark), "alerts": clark}

    # ── AirNow AQI ──────────────────────────────────────────
    def _fetch_aqi(self):
        if self.demo:
            return self._demo_aqi()
        # The official AirNow API requires a free key (https://docs.airnowapi.org/account/request/)
        # Set AIRNOW_API_KEY env var to enable
        import os
        api_key = os.environ.get("AIRNOW_API_KEY", "")
        if api_key:
            url = "https://www.airnowapi.org/aq/observation/zipCode/current/"
            params = {
                "format": "application/json",
                "zipCode": "89052",
                "distance": 25,
                "API_KEY": api_key,
            }
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data:
                # Find PM2.5 entry or use first available
                pm25 = [d for d in data if d.get("ParameterName") == "PM2.5"]
                e = pm25[0] if pm25 else data[0]
                return {
                    "aqi": e.get("AQI"),
                    "category": e.get("Category", {}).get("Name"),
                    "pollutant": e.get("ParameterName"),
                    "reporting_area": e.get("ReportingArea"),
                }
        raise ValueError("Set AIRNOW_API_KEY env var (free at docs.airnowapi.org)")

    def _demo_aqi(self):
        return {
            "aqi": 42,
            "category": "Good",
            "pollutant": "PM2.5",
            "reporting_area": "Las Vegas-Henderson",
        }

    # ── EPA UV Index ────────────────────────────────────────
    def _fetch_uv(self):
        if self.demo:
            return {"uv_index": 7, "uv_alert": False, "zip": "89052"}
        # Try both EPA Envirofacts hosts (the API has moved between domains)
        urls = [
            "https://enviro.epa.gov/enviro/efservice/getEnvirofactsUVDAILY/ZIP/89052/JSON",
            "https://data.epa.gov/efservice/getEnvirofactsUVDAILY/ZIP/89052/JSON",
        ]
        for url in urls:
            try:
                r = requests.get(url, timeout=15, allow_redirects=True)
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list) and data:
                    return {
                        "uv_index": data[0].get("UV_INDEX"),
                        "uv_alert": bool(data[0].get("UV_ALERT")),
                        "zip": "89052",
                    }
                # API returned but with an error message
                if isinstance(data, dict) and "error" in str(data).lower():
                    continue
            except Exception:
                continue
        raise ValueError("EPA UV API unavailable — endpoints may be offline")

    # ── Lake Mead (USBR RISE) ──────────────────────────────
    def _fetch_lake_mead(self):
        if self.demo:
            return self._demo_lake_mead()
        end = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        # Item 6123 = Lake Mead Elevation (ft); 6124 = Storage (af)
        url = "https://data.usbr.gov/rise/api/result/download"
        params = {"itemId": "6123", "after": start, "before": end, "order": "DESC"}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data:
            # /result/download returns a dict with metadata + numbered keys for data points
            elev = None
            date_str = ""
            if "0" in data:
                elev = data["0"].get("result")
                date_str = data["0"].get("dateTime", "")
            elif isinstance(data, list) and data:
                elev = data[0].get("result", data[0].get("value"))
                date_str = data[0].get("dateTime", "")
            if elev is not None:
                # Lake Mead max capacity at ~1,229 ft; dead pool ~895 ft
                pct = round((float(elev) - 895) / (1229 - 895) * 100, 1)
                return {
                    "elevation_ft": elev,
                    "pct_capacity": pct,
                    "date": date_str,
                }
        raise ValueError("No Lake Mead elevation data returned")

    def _demo_lake_mead(self):
        return {
            "elevation_ft": 1067.5,
            "pct_capacity": round((1067.5 - 895) / (1229 - 895) * 100, 1),
            "date": "2026-02-22",
        }

    # ── USGS Water Services ─────────────────────────────────
    def _fetch_usgs_water(self):
        if self.demo:
            return {
                "site": "Colorado R below Hoover Dam",
                "value": 47.0,
                "unit": "ft",
                "datetime": "2026-02-22T12:00:00",
            }
        url = "https://waterservices.usgs.gov/nwis/iv/"
        params = {
            "sites": "09421500",  # Colorado River below Hoover Dam
            "format": "json",
            "parameterCd": "00065",  # Gage height (ft) — discharge not available at this site
            "period": "P7D",
        }
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        ts = r.json()["value"]["timeSeries"]
        if ts:
            vals = ts[0]["values"][0]["value"]
            latest = vals[-1] if vals else None
            return {
                "site": ts[0]["sourceInfo"]["siteName"],
                "value": float(latest["value"]) if latest else None,
                "unit": ts[0]["variable"]["unit"]["unitCode"],
                "datetime": latest["dateTime"] if latest else None,
            }
        raise ValueError("No USGS data returned")

    # ── US Drought Monitor ──────────────────────────────────
    def _fetch_drought(self):
        if self.demo:
            return {
                "category": "D1 (Moderate Drought)",
                "pct_area": 62.3,
                "none_pct": 12.0,
                "d0_pct": 25.7,
                "d1_pct": 62.3,
            }
        end = datetime.now().strftime("%m/%d/%Y")
        start = (datetime.now() - timedelta(days=14)).strftime("%m/%d/%Y")
        # Try both the old and new domain — the API has been unstable
        urls = [
            "https://droughtmonitor.unl.edu/api/county_statistics/GetDroughtSeverityStatisticsByAreaPercent",
            "https://usdm.unl.edu/api/county_statistics/GetDroughtSeverityStatisticsByAreaPercent",
        ]
        for url in urls:
            try:
                params = {"aoi": "32003", "startdate": start, "enddate": end, "statisticsType": "1"}
                r = requests.get(url, params=params, timeout=15)
                r.raise_for_status()
                data = r.json()
                if data:
                    latest = data[-1] if isinstance(data, list) else data
                    # Determine worst drought category present
                    for level in ["d4", "d3", "d2", "d1", "d0"]:
                        pct = latest.get(level, 0)
                        if pct and float(pct) > 0:
                            labels = {"d0": "D0 (Abnormally Dry)", "d1": "D1 (Moderate Drought)",
                                      "d2": "D2 (Severe Drought)", "d3": "D3 (Extreme Drought)",
                                      "d4": "D4 (Exceptional Drought)"}
                            return {
                                "category": labels.get(level, level.upper()),
                                "pct_area": float(pct),
                                "none_pct": latest.get("none", 0),
                                "d0_pct": latest.get("d0", 0),
                                "d1_pct": latest.get("d1", 0),
                            }
                    return {
                        "category": "None",
                        "pct_area": 0,
                        "none_pct": latest.get("none", 100),
                        "d0_pct": 0,
                        "d1_pct": 0,
                    }
            except Exception:
                continue
        raise ValueError("Drought Monitor API unavailable on both domains")
