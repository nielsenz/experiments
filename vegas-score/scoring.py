"""
Scoring engine for the Las Vegas Health Score.

Each indicator is normalized to a 0-100 scale where:
  100 = excellent / best conditions
    0 = severe / worst conditions

Thresholds are calibrated for Las Vegas-specific conditions.
"""


class ScoreEngine:
    """Converts raw fetcher data into 0-100 normalized scores."""

    # ── Environmental Weights ───────────────────────────────
    ENV_WEIGHTS = {
        "air_quality": 0.25,
        "heat_comfort": 0.20,
        "water_supply": 0.20,
        "uv_exposure": 0.15,
        "drought": 0.10,
        "alerts": 0.10,
    }

    # ── Economic Weights ────────────────────────────────────
    ECON_WEIGHTS = {
        "unemployment": 0.20,
        "job_growth": 0.20,
        "hospitality_strength": 0.15,
        "cost_of_living": 0.15,
        "housing": 0.15,
        "gas_prices": 0.05,
        "mortgage": 0.10,
    }

    def _clamp(self, val, lo=0, hi=100):
        return max(lo, min(hi, val))

    # ════════════════════════════════════════════════════════
    # ENVIRONMENTAL SCORING
    # ════════════════════════════════════════════════════════

    def score_environmental(self, data):
        scores = {}

        # Air Quality: AQI 0-500, lower is better
        aqi_raw = data.get("aqi", {}).get("aqi")
        if aqi_raw is not None:
            # AQI 0→100, 50→90, 100→50, 150→20, 200+→0
            aqi_score = self._clamp(100 - (float(aqi_raw) * 0.6), 0, 100)
            scores["air_quality"] = {"score": round(aqi_score, 1), "raw": aqi_raw,
                                     "label": data["aqi"].get("category", "")}
        else:
            scores["air_quality"] = {"score": None, "raw": None, "label": "unavailable"}

        # Heat / Comfort: parse temperature
        temp_raw = data.get("weather", {}).get("temperature", "")
        if temp_raw and "error" not in data.get("weather", {}):
            try:
                temp_f = float(str(temp_raw).replace("°F", "").replace("°C", "").strip())
            except ValueError:
                temp_f = None
            if temp_f is not None:
                # Comfort curve: 65-80°F = 100, scales down outside that
                if 65 <= temp_f <= 80:
                    heat_score = 100
                elif temp_f < 65:
                    heat_score = self._clamp(100 - (65 - temp_f) * 2)
                else:  # > 80
                    # Vegas-specific: drops fast above 100
                    heat_score = self._clamp(100 - (temp_f - 80) * 1.5)
                scores["heat_comfort"] = {"score": round(heat_score, 1), "raw": temp_f,
                                          "label": f"{temp_f}°F"}
            else:
                scores["heat_comfort"] = {"score": None, "raw": None, "label": "parse error"}
        else:
            scores["heat_comfort"] = {"score": None, "raw": None, "label": "unavailable"}

        # Water Supply: Lake Mead % capacity
        pct_cap = data.get("water_level", {}).get("pct_capacity")
        if pct_cap is not None:
            # 100% capacity = 100, below 30% = critical
            water_score = self._clamp(float(pct_cap))
            scores["water_supply"] = {"score": round(water_score, 1), "raw": pct_cap,
                                      "label": f"{pct_cap}% capacity"}
        else:
            scores["water_supply"] = {"score": None, "raw": None, "label": "unavailable"}

        # UV Exposure: index 0-11+, lower is better for health
        uv_raw = data.get("uv", {}).get("uv_index")
        if uv_raw is not None:
            # UV 0-2: 100, 3-5: 80, 6-7: 60, 8-10: 30, 11+: 10
            uv = float(uv_raw)
            if uv <= 2:
                uv_score = 100
            elif uv <= 5:
                uv_score = 90 - (uv - 2) * 10
            elif uv <= 7:
                uv_score = 60 - (uv - 5) * 10
            elif uv <= 10:
                uv_score = 40 - (uv - 7) * 10
            else:
                uv_score = max(5, 10 - (uv - 10) * 5)
            scores["uv_exposure"] = {"score": round(uv_score, 1), "raw": uv_raw,
                                     "label": f"UV {uv_raw}"}
        else:
            scores["uv_exposure"] = {"score": None, "raw": None, "label": "unavailable"}

        # Drought: % area in drought, lower is better
        drought_pct = data.get("drought", {}).get("pct_area")
        if drought_pct is not None:
            drought_score = self._clamp(100 - float(drought_pct))
            cat = data["drought"].get("category", "")
            scores["drought"] = {"score": round(drought_score, 1), "raw": drought_pct,
                                 "label": cat}
        else:
            scores["drought"] = {"score": None, "raw": None, "label": "unavailable"}

        # Alerts: 0 alerts = 100, each alert drops 15 points
        alert_count = data.get("alerts", {}).get("clark_county_alerts")
        if alert_count is not None:
            alert_score = self._clamp(100 - int(alert_count) * 15)
            scores["alerts"] = {"score": round(alert_score, 1), "raw": alert_count,
                                "label": f"{alert_count} active"}
        else:
            scores["alerts"] = {"score": None, "raw": None, "label": "unavailable"}

        # Weighted overall
        scores["overall"] = self._weighted_avg(scores, self.ENV_WEIGHTS)
        return scores

    # ════════════════════════════════════════════════════════
    # ECONOMIC SCORING
    # ════════════════════════════════════════════════════════

    def score_economic(self, data):
        scores = {}

        # Unemployment: lower is better. 3% = 100, 6% = 50, 10%+ = 0
        unemp = data.get("unemployment", {}).get("rate")
        if unemp is not None:
            u = float(unemp)
            unemp_score = self._clamp(100 - (u - 3) * (100 / 7))  # 3%→100, 10%→0
            scores["unemployment"] = {"score": round(unemp_score, 1), "raw": u,
                                      "label": f"{u}%"}
        else:
            scores["unemployment"] = {"score": None, "raw": None, "label": "unavailable"}

        # Job Growth: YoY change in total nonfarm. +30K = 100, 0 = 50, -30K = 0
        yoy_str = data.get("employment_total", {}).get("yoy_change", "")
        if yoy_str and "K" in yoy_str:
            try:
                change = float(yoy_str.replace("K YoY", "").replace("+", "").strip())
                job_score = self._clamp(50 + change * (50 / 30))  # ±30K maps to 0-100
                scores["job_growth"] = {"score": round(job_score, 1), "raw": change,
                                        "label": f"{change:+.1f}K jobs YoY"}
            except ValueError:
                scores["job_growth"] = {"score": None, "raw": None, "label": "parse error"}
        else:
            scores["job_growth"] = {"score": None, "raw": None, "label": "unavailable"}

        # Hospitality Strength: L&H jobs as % of pre-pandemic peak (~290K)
        lh_jobs = data.get("employment_leisure", {}).get("jobs_k")
        if lh_jobs is not None:
            pct_peak = float(lh_jobs) / 290 * 100
            hosp_score = self._clamp(pct_peak)
            scores["hospitality_strength"] = {"score": round(hosp_score, 1), "raw": lh_jobs,
                                              "label": f"{lh_jobs}K ({pct_peak:.0f}% of peak)"}
        else:
            scores["hospitality_strength"] = {"score": None, "raw": None, "label": "unavailable"}

        # Cost of Living: CPI-based. National avg ~310, lower is better for affordability
        cpi = data.get("cpi", {}).get("index")
        if cpi is not None:
            # Score relative to national: if CPI < 300 → excellent, > 340 → poor
            cpi_score = self._clamp(100 - (float(cpi) - 300) * (100 / 40))
            scores["cost_of_living"] = {"score": round(cpi_score, 1), "raw": cpi,
                                        "label": f"CPI {cpi}"}
        else:
            scores["cost_of_living"] = {"score": None, "raw": None, "label": "unavailable"}

        # Housing: Median home value. Vegas sweet spot $300K-$400K = good, >$500K = stressed
        home_val = data.get("housing", {}).get("median_home_value")
        if home_val is not None:
            hv = float(home_val)
            # $250K → 100, $400K → 60, $600K → 20
            housing_score = self._clamp(100 - (hv - 250000) / 350000 * 80)
            rent = data["housing"].get("median_rent", 0)
            scores["housing"] = {
                "score": round(housing_score, 1), "raw": hv,
                "label": f"Home ${hv:,.0f} / Rent ${rent:,.0f}",
            }
        else:
            scores["housing"] = {"score": None, "raw": None, "label": "unavailable"}

        # Gas Prices: West Coast tends high. $3.00 = 100, $5.00 = 0
        gas = data.get("gas_prices", {}).get("price")
        if gas is not None:
            gas_score = self._clamp(100 - (float(gas) - 3.0) / 2.0 * 100)
            scores["gas_prices"] = {"score": round(gas_score, 1), "raw": gas,
                                    "label": f"${gas:.2f}/gal"}
        else:
            scores["gas_prices"] = {"score": None, "raw": None, "label": "unavailable"}

        # Mortgage Rate: 5% = 100, 7% = 40, 8%+ = 10
        mortgage = data.get("mortgage_rate", {}).get("rate")
        if mortgage is not None:
            m = float(mortgage)
            mort_score = self._clamp(100 - (m - 5.0) / 3.0 * 90)
            scores["mortgage"] = {"score": round(mort_score, 1), "raw": m,
                                  "label": f"{m}% 30yr"}
        else:
            scores["mortgage"] = {"score": None, "raw": None, "label": "unavailable"}

        scores["overall"] = self._weighted_avg(scores, self.ECON_WEIGHTS)
        return scores

    # ════════════════════════════════════════════════════════
    # COMPOSITE
    # ════════════════════════════════════════════════════════

    def composite(self, env_overall, econ_overall):
        """Combine environmental and economic into single 0-100 score."""
        if env_overall is not None and econ_overall is not None:
            return round(0.5 * env_overall + 0.5 * econ_overall, 1)
        return env_overall or econ_overall

    # ── Helpers ─────────────────────────────────────────────

    def _weighted_avg(self, scores, weights):
        """Compute weighted average, skipping None scores."""
        total_w = 0
        total_s = 0
        for key, w in weights.items():
            s = scores.get(key, {}).get("score")
            if s is not None:
                total_w += w
                total_s += s * w
        if total_w == 0:
            return None
        return round(total_s / total_w, 1)
