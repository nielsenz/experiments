"""
History storage and trend rendering for Vegas Health Score.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SPARK_CHARS = " .:-=+*#%@"


def append_snapshot(path: str, snapshot: dict[str, Any]) -> None:
    """Append one JSON snapshot to JSONL history file."""
    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot) + "\n")


def load_history(path: str) -> list[dict[str, Any]]:
    """Load JSONL history snapshots."""
    history_path = Path(path)
    if not history_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with history_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)

    rows.sort(key=lambda r: str(r.get("timestamp", "")))
    return rows


def _spark(values: list[float]) -> str:
    if not values:
        return ""
    lo = min(values)
    hi = max(values)
    if hi == lo:
        mid = SPARK_CHARS[len(SPARK_CHARS) // 2]
        return mid * len(values)
    out: list[str] = []
    steps = len(SPARK_CHARS) - 1
    for v in values:
        idx = round((v - lo) / (hi - lo) * steps)
        idx = max(0, min(steps, idx))
        out.append(SPARK_CHARS[idx])
    return "".join(out)


def _extract_metric(rows: list[dict[str, Any]], field: str) -> list[float]:
    vals: list[float] = []
    for r in rows:
        raw = r.get(field)
        if raw is None:
            continue
        try:
            vals.append(float(raw))
        except (TypeError, ValueError):
            continue
    return vals


def render_trend(rows: list[dict[str, Any]]) -> str:
    """Render a compact multi-metric trend summary."""
    if not rows:
        return "No score history found yet. Run with --save-history to start collecting."

    last = rows[-1]
    lines = []
    lines.append(f"History points: {len(rows)}")
    lines.append(
        f"Range: {rows[0].get('timestamp', '?')} -> {rows[-1].get('timestamp', '?')}"
    )
    lines.append("")

    labels = [
        ("composite", "Composite"),
        ("env_overall", "Environmental"),
        ("econ_overall", "Economic"),
    ]
    for key, label in labels:
        vals = _extract_metric(rows, key)
        if not vals:
            lines.append(f"{label:<14} n/a")
            continue
        latest = vals[-1]
        delta = vals[-1] - vals[0] if len(vals) > 1 else 0.0
        trend = _spark(vals[-40:])
        lines.append(
            f"{label:<14} {latest:5.1f}  ({delta:+5.1f} vs first)  {trend}"
        )
    return "\n".join(lines)
