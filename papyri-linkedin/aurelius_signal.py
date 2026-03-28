"""Test the Constitutio Antoniniana hypothesis.

In 212 CE, Caracalla extended Roman citizenship to all free inhabitants of the
Empire.  Every new citizen adopted "Aurelius" as their gentilicium.  If this
event is visible in the papyri, we should see a sharp spike in Aurelius
mentions after 212 CE.

This script scans all 70K documents (enriched with HGV dates), extracts
Aurelius mentions per decade, and prints a histogram.

Usage:
    uv run python aurelius_signal.py [--data-dir DATA_DIR]
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from analyze_metadata import build_hgv_index, enrich_from_hgv, find_xml_files, parse_metadata_only
from starter import PapyriDocument, classify_period


DEFAULT_DATA_DIR = Path("data/idp.data")

# All forms of "Aurelius" that appear in the corpus (nominative, genitive, dative, accusative).
AURELIUS_PATTERN = re.compile(
    r"Α[ὐυ]ρ[ήη]λι|Aureli",
    flags=re.IGNORECASE | re.UNICODE,
)

# A few other high-frequency names for comparison.
COMPARISON_NAMES = {
    "Ptolemaios": re.compile(r"Πτολεμα[ίι]", re.UNICODE),
    "Sarapion": re.compile(r"Σαραπ[ίι]ων", re.UNICODE),
    "Phoibammon": re.compile(r"Φοιβ[άα]μμων", re.UNICODE),
    "Flavius": re.compile(r"Φλα[ουο]υ[ίι]|Flavi", re.IGNORECASE | re.UNICODE),
}


def count_mentions(text: str, pattern: re.Pattern) -> int:
    return len(pattern.findall(text))


def decade_bin(year: int) -> int:
    """Round a year down to its decade."""
    return (year // 10) * 10


def histogram_line(count: int, max_count: int, width: int = 50) -> str:
    if max_count == 0:
        return ""
    bars = int(round(count / max_count * width))
    return "█" * bars


def main():
    parser = argparse.ArgumentParser(description="Aurelius frequency analysis by decade")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    # Load HGV dates
    hgv_index = build_hgv_index(data_dir)
    xml_files = find_xml_files(data_dir, "DDB_EpiDoc_XML")

    print("Scanning documents...")
    aurelius_by_decade: Counter = Counter()
    docs_by_decade: Counter = Counter()
    comparison_by_decade: dict[str, Counter] = {name: Counter() for name in COMPARISON_NAMES}

    total = 0
    dated = 0
    aurelius_total = 0

    for i, path in enumerate(xml_files):
        doc = parse_metadata_only(path)
        if doc is None:
            continue
        total += 1

        # Enrich with HGV date
        if doc.tm_id and doc.tm_id in hgv_index:
            meta = hgv_index[doc.tm_id]
            if "date_range" in meta:
                doc.date_range = meta["date_range"]

        if doc.date_range is None:
            continue
        dated += 1

        # Use midpoint of date range for binning
        midpoint = (doc.date_range[0] + doc.date_range[1]) // 2
        decade = decade_bin(midpoint)

        # Skip obviously bad dates
        if decade < -400 or decade > 1000:
            continue

        docs_by_decade[decade] += 1

        # Search the full XML (includes both text and markup — catches all name occurrences)
        search_text = doc.text or ""
        xml_text = doc.xml or ""
        combined = search_text + " " + xml_text

        a_count = count_mentions(combined, AURELIUS_PATTERN)
        if a_count > 0:
            aurelius_by_decade[decade] += a_count
            aurelius_total += a_count

        for name, pattern in COMPARISON_NAMES.items():
            c = count_mentions(combined, pattern)
            if c > 0:
                comparison_by_decade[name][decade] += c

        if (i + 1) % 10000 == 0:
            print(f"  {i+1}/{len(xml_files)}...")

    print(f"\nTotal: {total} docs, {dated} dated, {aurelius_total} Aurelius mentions\n")

    # Print Aurelius histogram
    all_decades = sorted(set(docs_by_decade.keys()))
    # Focus on the interesting range: 200 BCE to 700 CE
    decades = [d for d in all_decades if -200 <= d <= 700]

    max_rate = 0
    rates = {}
    for d in decades:
        doc_count = docs_by_decade[d]
        if doc_count >= 5:  # skip decades with too few docs
            rate = aurelius_by_decade.get(d, 0) / doc_count
            rates[d] = rate
            max_rate = max(max_rate, rate)

    print("=" * 80)
    print("AURELIUS MENTIONS PER DOCUMENT BY DECADE")
    print("(Constitutio Antoniniana = 212 CE)")
    print("=" * 80)
    print()

    for d in decades:
        if d not in rates:
            continue
        rate = rates[d]
        doc_count = docs_by_decade[d]
        raw = aurelius_by_decade.get(d, 0)
        label = f"{abs(d):>4d}{'BCE' if d < 0 else ' CE'}"
        marker = " ◄── 212 CE" if d == 210 else ""
        bar = histogram_line(rate, max_rate)
        print(f"  {label}  {bar:50s}  {rate:.2f}/doc ({raw:>4d} in {doc_count:>4d} docs){marker}")

    # Print comparison names
    print()
    print("=" * 80)
    print("COMPARISON: OTHER NAME FREQUENCIES PER DOCUMENT BY DECADE")
    print("=" * 80)

    for name, by_decade in comparison_by_decade.items():
        print(f"\n--- {name} ---")
        name_rates = {}
        name_max = 0
        for d in decades:
            doc_count = docs_by_decade[d]
            if doc_count >= 5:
                rate = by_decade.get(d, 0) / doc_count
                name_rates[d] = rate
                name_max = max(name_max, rate)

        for d in decades:
            if d not in name_rates:
                continue
            rate = name_rates[d]
            doc_count = docs_by_decade[d]
            raw = by_decade.get(d, 0)
            label = f"{abs(d):>4d}{'BCE' if d < 0 else ' CE'}"
            bar = histogram_line(rate, name_max)
            print(f"  {label}  {bar:50s}  {rate:.2f}/doc ({raw:>4d} in {doc_count:>4d} docs)")

    # Summary stats
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    pre_212 = sum(aurelius_by_decade[d] for d in aurelius_by_decade if d < 210)
    post_212 = sum(aurelius_by_decade[d] for d in aurelius_by_decade if d >= 210)
    pre_docs = sum(docs_by_decade[d] for d in docs_by_decade if d < 210 and -200 <= d <= 700)
    post_docs = sum(docs_by_decade[d] for d in docs_by_decade if d >= 210 and d <= 700)
    pre_rate = pre_212 / pre_docs if pre_docs else 0
    post_rate = post_212 / post_docs if post_docs else 0
    print(f"  Pre-212 CE:  {pre_212:>5d} Aurelius mentions in {pre_docs:>5d} docs ({pre_rate:.3f}/doc)")
    print(f"  Post-212 CE: {post_212:>5d} Aurelius mentions in {post_docs:>5d} docs ({post_rate:.3f}/doc)")
    if pre_rate > 0:
        print(f"  Ratio: {post_rate/pre_rate:.1f}x increase after Constitutio Antoniniana")


if __name__ == "__main__":
    main()
