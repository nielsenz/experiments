"""Download the SSA national name files (yob1880.txt ... yob2024.txt) into data/raw/.

The SSA publishes these as names.zip at https://www.ssa.gov/oact/babynames/limits.html.
This script pulls the same files from a GitHub mirror (dxdc/babynames), which is what the
analysis here was run on.  data/raw/ is git-ignored.
"""
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
BASE = "https://raw.githubusercontent.com/dxdc/babynames/main/raw/yob{}.txt"

if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    for y in range(1880, 2025):
        dest = RAW / f"yob{y}.txt"
        if not dest.exists():
            urllib.request.urlretrieve(BASE.format(y), dest)
    print(len(list(RAW.glob("yob*.txt"))), "files in", RAW)
