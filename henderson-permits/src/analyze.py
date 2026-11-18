"""Analyze Henderson permits: who pulls them, how long they take, how many expire.

Reads the CSV written by fetch_permits.py and writes tables to results/ plus a
SUMMARY.md. Three questions drive it:

1. Who are the top pullers in each small-residential trade, and how
   concentrated is each trade?
2. Does time-to-issue vary by contractor within a trade? (If it does, packet
   quality plausibly matters.)
3. What share of each contractor's permits end up Expired?

"Days" is the city's own field: working days between application and issuance.
It includes the applicant's time (resubmittals, paying fees), not just review.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

DAYS = "WorkingDaysBetweenApplyDateAndIssueDate"
NO_PRO = "(none / owner-builder)"
SENTINELS = {"", "NA", "N A", "NONE", "OWNER", "OWNER BUILDER", "OWNERBUILDER", "HOMEOWNER", "OWNER BUILDER PERMIT"}

# Trade -> boolean mask builder. Definitions come from the city's own
# PermitType / WorkClass values.
TRADES = {
    "pool_spa": lambda d: d.PermitType.eq("BLDG - Pool and Spa"),
    "patio_deck": lambda d: d.WorkClass.str.startswith("Patio", na=False),
    "solar": lambda d: d.PermitType.eq("BLDG - Photovoltaic"),
    "hvac": lambda d: d.WorkClass.eq("HVAC"),
    "water_heater": lambda d: d.WorkClass.isin(["Water Heater", "Tankless Water Heater"]),
    "wall": lambda d: d.PermitType.eq("BLDG - Wall"),
    "remodel_addition": lambda d: d.PermitType.eq("BLDG - Dwelling") & d.WorkClass.isin(["Remodel", "Addition"]),
}
LABELS = {
    "pool_spa": "Pool and spa", "patio_deck": "Patio / deck", "solar": "Solar (PV)",
    "hvac": "HVAC swap", "water_heater": "Water heater", "wall": "Block wall",
    "remodel_addition": "Remodel / addition",
}


def norm_name(s: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", str(s).upper())
    s = re.sub(r"\b(LLC|INC|CORP|CO|LTD|COMPANY|INCORPORATED|CORPORATION|DBA)\b", " ", s)
    return " ".join(s.split())


def load(path: Path) -> pd.DataFrame:
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    for c in ("ApplyDate", "IssueDate", "FinalizedDate", "ExpireDate"):
        d[c] = pd.to_datetime(d[c], errors="coerce")
    d[DAYS] = pd.to_numeric(d[DAYS], errors="coerce")
    d["ApplyDateFY"] = pd.to_numeric(d["ApplyDateFY"], errors="coerce")
    name = d.ProfessionalName.map(norm_name)
    lic = d.ProfessionalStateLicNbr.str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    lic = lic.where(~lic.isin(["", "NA", "NONE", "0"]), "")
    has_pro = ~name.isin(SENTINELS)
    # One contractor can appear under several spellings; the state license
    # number is the steadier key when it is present.
    d["pro_key"] = (("LIC:" + lic).where(lic.ne(""), "NAME:" + name)).where(has_pro, NO_PRO)
    d["pro_name_norm"] = name.where(has_pro, NO_PRO)
    return d


def pct(x: float) -> str:
    return "–" if pd.isna(x) else f"{100 * x:.0f}%"


def num(x: float, nd: int = 0) -> str:
    return "–" if pd.isna(x) else f"{x:,.{nd}f}"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(v) for v in row) + " |")
    return "\n".join(lines)


def timing(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return dict(issued=0, median_days=float("nan"), p75_days=float("nan"), p90_days=float("nan"),
                    share_le1=float("nan"), share_gt10=float("nan"), share_gt30=float("nan"))
    return dict(issued=len(s), median_days=s.median(), p75_days=s.quantile(.75), p90_days=s.quantile(.90),
                share_le1=(s <= 1).mean(), share_gt10=(s > 10).mean(), share_gt30=(s > 30).mean())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="henderson-permits/data/dsc_permits.csv.gz")
    ap.add_argument("--out", default="henderson-permits/results")
    ap.add_argument("--months", type=int, default=24, help="look-back window for contractor stats")
    ap.add_argument("--min-permits", type=int, default=10, help="minimum permits for a contractor to count in the spread")
    ap.add_argument("--aged-days", type=int, default=365, help="a permit must be at least this old to judge expiry")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    d = load(Path(args.data))
    asof = d.ApplyDate.max()
    start = asof - pd.DateOffset(months=args.months)
    win = d[d.ApplyDate >= start]
    aged_cut = asof - pd.Timedelta(days=args.aged_days)

    masks = {t: f(d) for t, f in TRADES.items()}

    # --- volume by fiscal year -------------------------------------------------
    vol = pd.DataFrame({LABELS[t]: d[m].groupby("ApplyDateFY").size() for t, m in masks.items()}).fillna(0).astype(int)
    vol.index = vol.index.astype(int)
    vol.index.name = "fiscal_year"
    vol.to_csv(out / "volume_by_fiscal_year.csv")

    rows_time, rows_conc, rows_spread, rows_exp = [], [], [], []
    leaders: dict[str, pd.DataFrame] = {}
    for t, m in masks.items():
        w = win[m.loc[win.index]]
        rows_time.append(dict(trade=LABELS[t], applied=len(w), **timing(w[DAYS])))

        # Expiry is judged on permits old enough to have had a fair chance to close.
        aged = d[m & (d.IssueDate >= start - pd.Timedelta(days=args.aged_days)) & (d.IssueDate <= aged_cut)]
        st = aged.PermitStatus
        rows_exp.append(dict(trade=LABELS[t], aged_permits=len(aged),
                             share_done=st.eq("Done").mean() if len(aged) else float("nan"),
                             share_expired=st.eq("Expired").mean() if len(aged) else float("nan"),
                             share_still_active=st.eq("Active - Issued").mean() if len(aged) else float("nan")))

        g = w.groupby("pro_key")
        lb = pd.DataFrame({
            "contractor": g.ProfessionalName.agg(lambda s: s.mode().iat[0]),
            "license": g.ProfessionalStateLicNbr.agg(lambda s: s.mode().iat[0]),
            "phone": g.ProfessionalPhone.agg(lambda s: s.mode().iat[0]),
            "permits": g.size(),
            "median_days": g[DAYS].median(),
            "p75_days": g[DAYS].quantile(.75),
            "share_gt10": g[DAYS].agg(lambda s: (s.dropna() > 10).mean()),
        })
        ag = aged.groupby("pro_key")
        lb["aged_permits"] = ag.size().reindex(lb.index).fillna(0).astype(int)
        lb["share_expired"] = ag.PermitStatus.agg(lambda s: s.eq("Expired").mean()).reindex(lb.index)
        lb["share_of_trade"] = lb.permits / max(len(w), 1)
        if NO_PRO in lb.index:
            lb.loc[NO_PRO, ["contractor", "license", "phone"]] = [NO_PRO, "", ""]
        lb = lb.sort_values("permits", ascending=False)
        lb.to_csv(out / f"contractors_{t}.csv", index_label="contractor_key")
        leaders[t] = lb

        named = lb.drop(index=NO_PRO, errors="ignore")
        tot = max(len(w), 1)
        rows_conc.append(dict(trade=LABELS[t], permits=len(w), contractors=len(named),
                              no_contractor_share=(lb.permits.get(NO_PRO, 0)) / tot,
                              top1_share=named.permits.head(1).sum() / tot,
                              top5_share=named.permits.head(5).sum() / tot,
                              top10_share=named.permits.head(10).sum() / tot,
                              top20_share=named.permits.head(20).sum() / tot,
                              contractors_10plus=int((named.permits >= args.min_permits).sum())))

        big = named[named.permits >= args.min_permits]
        med = big.median_days.dropna()
        rows_spread.append(dict(trade=LABELS[t], contractors=len(med),
                                fastest=med.min() if len(med) else float("nan"),
                                p25=med.quantile(.25) if len(med) else float("nan"),
                                median=med.median() if len(med) else float("nan"),
                                p75=med.quantile(.75) if len(med) else float("nan"),
                                slowest=med.max() if len(med) else float("nan"),
                                gt10_share_p25=big.share_gt10.quantile(.25) if len(big) else float("nan"),
                                gt10_share_p75=big.share_gt10.quantile(.75) if len(big) else float("nan")))

    T = pd.DataFrame(rows_time); T.to_csv(out / "time_to_issue.csv", index=False)
    C = pd.DataFrame(rows_conc); C.to_csv(out / "concentration.csv", index=False)
    S = pd.DataFrame(rows_spread); S.to_csv(out / "contractor_spread.csv", index=False)
    E = pd.DataFrame(rows_exp); E.to_csv(out / "expiry.csv", index=False)

    # --- SUMMARY.md --------------------------------------------------------------
    L = [f"# Henderson permits: summary", "",
         f"Data through {asof:%Y-%m-%d}; {len(d):,} permits in the table since 2017. Contractor stats cover permits applied "
         f"for since {start:%Y-%m-%d} ({args.months} months). Generated by `src/analyze.py`; do not edit by hand.", "",
         "## Time to issue (working days, application to issuance)", ""]
    L.append(md_table(pd.DataFrame({
        "Trade": T.trade, "Applied": T.applied.map(num), "Issued": T.issued.map(num),
        "Median": T.median_days.map(num), "75th pct": T.p75_days.map(num), "90th pct": T.p90_days.map(num),
        "≤1 day": T.share_le1.map(pct), ">10 days": T.share_gt10.map(pct), ">30 days": T.share_gt30.map(pct)})))
    L += ["", "## Concentration", ""]
    L.append(md_table(pd.DataFrame({
        "Trade": C.trade, "Permits": C.permits.map(num), "Contractors": C.contractors.map(num),
        f"With {args.min_permits}+": C.contractors_10plus.map(num), "No contractor listed": C.no_contractor_share.map(pct),
        "Top 1": C.top1_share.map(pct), "Top 5": C.top5_share.map(pct), "Top 10": C.top10_share.map(pct),
        "Top 20": C.top20_share.map(pct)})))
    L += ["", f"## Spread between contractors (those with {args.min_permits}+ permits)", "",
          "Each contractor's own median days to issue; the table shows how those medians are distributed.", ""]
    L.append(md_table(pd.DataFrame({
        "Trade": S.trade, "Contractors": S.contractors.map(num), "Fastest": S.fastest.map(lambda x: num(x, 1)),
        "25th pct": S.p25.map(lambda x: num(x, 1)), "Median": S["median"].map(lambda x: num(x, 1)),
        "75th pct": S.p75.map(lambda x: num(x, 1)), "Slowest": S.slowest.map(lambda x: num(x, 1)),
        ">10-day share, 25th–75th pct": S.gt10_share_p25.map(pct) + " – " + S.gt10_share_p75.map(pct)})))
    L += ["", f"## Expiry (permits issued at least {args.aged_days} days before the data date)", ""]
    L.append(md_table(pd.DataFrame({
        "Trade": E.trade, "Permits": E.aged_permits.map(num), "Done": E.share_done.map(pct),
        "Expired": E.share_expired.map(pct), "Still active": E.share_still_active.map(pct)})))
    for t, lb in leaders.items():
        top = lb.drop(index=NO_PRO, errors="ignore").head(15)
        L += ["", f"## Top pullers: {LABELS[t]}", ""]
        L.append(md_table(pd.DataFrame({
            "Contractor": top.contractor, "Permits": top.permits.map(num), "Share": top.share_of_trade.map(pct),
            "Median days": top.median_days.map(lambda x: num(x, 1)), ">10 days": top.share_gt10.map(pct),
            "Expired (aged)": top.share_expired.map(pct)})))
    (out / "SUMMARY.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:60]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
