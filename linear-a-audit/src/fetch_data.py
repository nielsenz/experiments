"""Download the Linear A inscription file from github.com/mwenge/lineara.xyz (pinned commit) into data/raw/.

The file is only ever read as text by corpus.py.  data/raw/ is git-ignored; data/tokens.csv, the parsed
table the analysis runs on, is committed.
"""
import urllib.request
from pathlib import Path

COMMIT = "9c81beba669a4ffec3f5b29d4e7748d02c060eff"   # 2026-09-28
URL = f"https://raw.githubusercontent.com/mwenge/lineara.xyz/{COMMIT}/LinearAInscriptions.js"

if __name__ == "__main__":
    raw = Path(__file__).resolve().parents[1] / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, raw / "LinearAInscriptions.js")
    print("saved", raw / "LinearAInscriptions.js")
