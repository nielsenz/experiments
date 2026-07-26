"""
Quantify the gate-closure latency leak in our 'day-ahead' features.

CAISO DAM gate closes ~10:00 PACIFIC on day D-1 for all operating hours of day D.
Our previous_day1 weather feature for valid time T is (per Open-Meteo) the forecast
issued ~24h before T. So the vintage-lead of our feature RELATIVE TO the gate
varies by the local hour of the target:

  lead_vs_gate(T) = (issue_time_of_our_feature)  -  (CAISO gate time for T's day)

If our feature is issued AFTER the gate, we've used information CAISO didn't have
-> latency leak. This script computes, for each local target hour, how many hours
FRESHER (positive) or staler (negative) our feature is than the gate.
"""
import datetime as dt

# CAISO gate: 10:00 Pacific on D-1 for operating day D.
# Pacific is UTC-7 (PDT, summer) / UTC-8 (PST). Use -7 as representative; the
# structure (which hours leak) is the same either way.
PT_OFFSET = -7
GATE_HOUR_PT = 10  # 10:00 PT on D-1

print("target_local_hour | our_feature_issued(PT, rel to op-day D) | gate(PT) | our_lead_vs_gate_h | LEAK?")
for h_local in range(24):
    # operating time T = day D at hour h_local (PT). Anchor D at day 0.
    T = dt.datetime(2025, 6, 15, 0) + dt.timedelta(hours=h_local)  # D=Jun15
    # our previous_day1 feature issued ~24h before valid time T
    our_issue = T - dt.timedelta(hours=24)
    # CAISO gate = 10:00 PT on D-1 = Jun14 10:00
    gate = dt.datetime(2025, 6, 14, GATE_HOUR_PT)
    lead = (our_issue - gate).total_seconds() / 3600.0
    leak = "LEAK" if lead > 0 else "ok"
    print(f"   {h_local:02d}:00           {our_issue.strftime('%b%d %H:%M')}            "
          f"{gate.strftime('%b%d %H:%M')}      {lead:+6.1f}          {leak}")
