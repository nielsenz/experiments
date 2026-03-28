from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

try:
    import polars as pl
except ImportError:  # pragma: no cover
    pl = None

try:
    import pint
except ImportError:  # pragma: no cover
    pint = None


DEFAULT_TEXT_COLUMNS = ["text", "name", "entry", "spelling"]


def load_csv(path: str, use_polars: bool = False):
    file_path = Path(path)
    if use_polars and pl is not None:
        return pl.read_csv(file_path)
    return pd.read_csv(file_path)


def normalize_token(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return (
        text.replace("ǣ", "ae")
        .replace("æ", "ae")
        .replace("ꝛ", "r")
        .replace("u", "v")
    )


def best_match(query: str, choices: list[str]):
    if not query or not choices:
        return None
    match = process.extractOne(
        query,
        choices,
        scorer=fuzz.WRatio,
    )
    if match is None:
        return None
    choice, score, index = match
    return {"match": choice, "score": score, "index": index}


def main() -> None:
    parser = argparse.ArgumentParser(description="Load medieval CSV data and fuzz-match spellings.")
    parser.add_argument("csv_path", help="Path to a CSV file containing medieval data")
    parser.add_argument(
        "--text-column",
        default="text",
        help="Column to match against; defaults to text",
    )
    parser.add_argument(
        "--query",
        help="A spelling to compare against the loaded data",
    )
    parser.add_argument(
        "--use-polars",
        action="store_true",
        help="Read the CSV with polars instead of pandas when available",
    )
    args = parser.parse_args()

    data = load_csv(args.csv_path, use_polars=args.use_polars)
    print(data.head())

    if args.query:
        if hasattr(data, "to_dicts"):
            rows = data.to_dicts()
            values = [normalize_token(row.get(args.text_column, "")) for row in rows]
        else:
            values = [normalize_token(value) for value in data[args.text_column].tolist()]

        result = best_match(normalize_token(args.query), values)
        print(result)


if __name__ == "__main__":
    main()
