"""Load SSA national name files into a dense name x year share matrix."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
Y0, Y1 = 1880, 2024
YEARS = np.arange(Y0, Y1 + 1)


def load_counts():
    frames = []
    for y in YEARS:
        d = pd.read_csv(RAW / f"yob{y}.txt", names=["name", "sex", "n"])
        d["year"] = y
        frames.append(d)
    return pd.concat(frames, ignore_index=True)


def build():
    """Returns (index DataFrame with name, sex), counts[N, T], share[N, T].

    share = babies with the name / all babies of that sex in the SSA file that year.
    Name-years below the SSA's 5-baby disclosure floor are zero.
    """
    long = load_counts()
    keys = long[["name", "sex"]].drop_duplicates().reset_index(drop=True)
    keys["id"] = np.arange(len(keys))
    long = long.merge(keys, on=["name", "sex"])
    counts = np.zeros((len(keys), len(YEARS)), dtype=np.float64)
    counts[long["id"].to_numpy(), long["year"].to_numpy() - Y0] = long["n"].to_numpy()
    share = np.zeros_like(counts)
    for s in ("F", "M"):
        m = (keys["sex"] == s).to_numpy()
        share[m] = counts[m] / counts[m].sum(axis=0, keepdims=True)
    return keys, counts, share


def smooth(x, w):
    """Trailing mean over the last w years (uses only current and past years)."""
    c = np.cumsum(np.concatenate([np.zeros((x.shape[0], 1)), x], axis=1), axis=1)
    out = np.empty_like(x)
    for t in range(x.shape[1]):
        a = max(0, t - w + 1)
        out[:, t] = (c[:, t + 1] - c[:, a]) / (t + 1 - a)
    return out
