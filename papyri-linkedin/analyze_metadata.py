"""Fast metadata-only analysis of the full papyri corpus.

Scans all XML files for TM IDs, date ranges, and places WITHOUT running NER.
Produces:
  1. Temporal stats (document counts by period)
  2. Place-name frequency list (to identify place-name leakage into person names)
  3. Zenon Archive extraction and mini social-network analysis

Usage:
    uv run python analyze_metadata.py [--data-dir DATA_DIR] [--zenon-limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from starter import (
    PapyriDocument,
    classify_period,
    compute_temporal_stats,
    document_period,
    parse_document,
    build_social_graph,
    extract_person_names,
    fallback_name_candidates,
    normalize_person_name,
)


DEFAULT_DATA_DIR = Path("data/idp.data")


def find_xml_files(data_dir: Path, subdir: str = "DDB_EpiDoc_XML") -> list[Path]:
    """Find all XML files in a subdirectory."""
    xml_dir = data_dir / subdir
    if not xml_dir.exists():
        print(f"ERROR: {xml_dir} does not exist. Run: uv run python local_loader.py --setup")
        sys.exit(1)
    files = sorted(xml_dir.rglob("*.xml"))
    print(f"Found {len(files)} XML files in {subdir}")
    return files


def parse_metadata_only(xml_path: Path) -> PapyriDocument | None:
    """Parse a single XML file for metadata. Returns None on failure."""
    try:
        xml_text = xml_path.read_text(encoding="utf-8", errors="replace")
        doc = parse_document(str(xml_path), xml_text)
        return doc
    except Exception:
        return None


def build_hgv_index(data_dir: Path) -> dict[str, dict]:
    """Build a TM ID -> {date_range, place} lookup from HGV metadata files.

    The HGV (Heidelberger Gesamtverzeichnis) files contain the authoritative
    date and provenance metadata that the DDB text files lack.
    """
    hgv_dir = data_dir / "HGV_meta_EpiDoc"
    if not hgv_dir.exists():
        print("WARNING: HGV_meta_EpiDoc not found — dates/places will be unavailable")
        return {}

    hgv_files = sorted(hgv_dir.rglob("*.xml"))
    print(f"Building HGV index from {len(hgv_files)} metadata files...")

    index: dict[str, dict] = {}
    for i, path in enumerate(hgv_files):
        try:
            xml_text = path.read_text(encoding="utf-8", errors="replace")
            doc = parse_document(str(path), xml_text)
            if doc.tm_id:
                entry: dict = {}
                if doc.date_range:
                    entry["date_range"] = doc.date_range
                if doc.place:
                    entry["place"] = doc.place
                if entry:
                    index[doc.tm_id] = entry
        except Exception:
            pass
        if (i + 1) % 10000 == 0:
            print(f"  {i+1}/{len(hgv_files)} HGV files indexed")

    print(f"HGV index: {len(index)} entries with date/place metadata")
    return index


def enrich_from_hgv(docs: list[PapyriDocument], hgv_index: dict[str, dict]) -> int:
    """Enrich DDB documents with date_range and place from HGV metadata."""
    enriched = 0
    for doc in docs:
        if not doc.tm_id or doc.tm_id not in hgv_index:
            continue
        meta = hgv_index[doc.tm_id]
        if "date_range" in meta and doc.date_range is None:
            doc.date_range = meta["date_range"]
            enriched += 1
        if "place" in meta and doc.place is None:
            doc.place = meta["place"]
    return enriched


# ---------------------------------------------------------------------------
# Analysis 1: Temporal stats
# ---------------------------------------------------------------------------

def temporal_analysis(docs: list[PapyriDocument]) -> dict:
    """Compute period breakdown from parsed metadata."""
    period_counts: Counter = Counter()
    dated_count = 0
    date_ranges: list[tuple[int, int]] = []

    for doc in docs:
        period = document_period(doc)
        period_counts[period or "Unknown"] += 1
        if doc.date_range is not None:
            dated_count += 1
            date_ranges.append(doc.date_range)

    # Compute date coverage stats
    if date_ranges:
        earliest = min(r[0] for r in date_ranges)
        latest = max(r[1] for r in date_ranges)
    else:
        earliest = latest = 0

    return {
        "total_documents": len(docs),
        "dated_documents": dated_count,
        "undated_documents": len(docs) - dated_count,
        "date_coverage_pct": round(100 * dated_count / len(docs), 1) if docs else 0,
        "earliest_year": earliest,
        "latest_year": latest,
        "period_breakdown": dict(sorted(period_counts.items())),
    }


# ---------------------------------------------------------------------------
# Analysis 2: Place-name leakage detection
# ---------------------------------------------------------------------------

def place_analysis(docs: list[PapyriDocument]) -> dict:
    """Identify place names and check which ones appear in the old top-names list."""
    place_counts: Counter = Counter()
    for doc in docs:
        if doc.place:
            place_counts[doc.place] += 1

    # Load the old analysis to find place-name leakage
    old_analysis = Path("papyri_analysis_full.json")
    leaked_places = []
    if old_analysis.exists():
        data = json.loads(old_analysis.read_text())
        old_names = {name for name, _ in data.get("top_names", [])}
        for place, count in place_counts.most_common(100):
            # Check if the place name (or its genitive) appears in person names
            # Common genitive pattern: add -ος, -ου, etc.
            for old_name in old_names:
                normalized_place = place.lower().strip()
                normalized_name = old_name.lower().strip()
                if normalized_place in normalized_name or normalized_name in normalized_place:
                    leaked_places.append({
                        "place": place,
                        "doc_count": count,
                        "matched_person_name": old_name,
                    })
                    break

    return {
        "unique_places": len(place_counts),
        "documents_with_place": sum(place_counts.values()),
        "top_30_places": [
            {"place": p, "count": c} for p, c in place_counts.most_common(30)
        ],
        "place_names_leaked_as_persons": leaked_places[:20],
    }


# ---------------------------------------------------------------------------
# Analysis 3: Zenon Archive
# ---------------------------------------------------------------------------

def zenon_analysis(
    docs: list[PapyriDocument],
    limit: int = 500,
) -> dict:
    """Extract Zenon Archive documents and build a focused social network.

    The Zenon Archive dates to ~260-240 BCE. We identify documents from the
    Ptolemaic period that mention Zenon or are from the p.cair.zen / p.zen
    collections (the main Zenon papyrus publications).
    """
    zenon_docs: list[PapyriDocument] = []

    for doc in docs:
        record_lower = doc.record_id.lower()
        title_lower = doc.title.lower()
        text_lower = doc.text.lower() if doc.text else ""

        is_zenon_collection = any(
            marker in record_lower
            for marker in ("p.cair.zen", "psi;5", "psi;4", "p.lond;7", "p.col;3", "p.col;4", "p.mich;1", "p.edgar", "p.zen")
        )

        is_ptolemaic = (
            doc.date_range is not None
            and doc.date_range[0] <= -230
            and doc.date_range[1] >= -270
        )

        mentions_zenon = "zenon" in title_lower or "ζήνων" in text_lower or "ζηνων" in text_lower

        if is_zenon_collection or (is_ptolemaic and mentions_zenon):
            # Extract names from text using fallback (no spaCy needed)
            if not doc.person_names and doc.text:
                doc.person_names = fallback_name_candidates(doc.text)
            zenon_docs.append(doc)
            if len(zenon_docs) >= limit:
                break

    if not zenon_docs:
        return {"status": "no_zenon_docs_found", "note": "Data may not include Zenon collections"}

    # Build a mini social graph for just the Zenon Archive
    graph = build_social_graph(zenon_docs)

    # Extract person nodes ranked by degree
    person_nodes = [
        (node, data)
        for node, data in graph.nodes(data=True)
        if data.get("kind") == "person"
    ]
    person_degrees = sorted(
        [(data.get("name", node), graph.degree(node)) for node, data in person_nodes],
        key=lambda x: -x[1],
    )

    # Place nodes
    place_nodes = [
        (data.get("name", node), graph.degree(node))
        for node, data in graph.nodes(data=True)
        if data.get("kind") == "place"
    ]
    place_nodes.sort(key=lambda x: -x[1])

    # Date range of the archive
    dated = [d for d in zenon_docs if d.date_range]
    if dated:
        archive_start = min(d.date_range[0] for d in dated)
        archive_end = max(d.date_range[1] for d in dated)
    else:
        archive_start = archive_end = None

    return {
        "documents": len(zenon_docs),
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "archive_date_range": [archive_start, archive_end] if archive_start else None,
        "top_30_persons": [
            {"name": name, "degree": deg} for name, deg in person_degrees[:30]
        ],
        "places": [
            {"name": name, "degree": deg} for name, deg in place_nodes
        ],
        "sample_docs": [
            {
                "record_id": d.record_id,
                "title": d.title,
                "date_range": list(d.date_range) if d.date_range else None,
                "place": d.place,
                "names": d.person_names[:10],
            }
            for d in zenon_docs[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fast metadata analysis of papyri corpus")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Path to idp.data clone")
    parser.add_argument("--zenon-limit", type=int, default=500, help="Max Zenon docs to process")
    parser.add_argument("--output", default="metadata_analysis.json", help="Output JSON file")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    # Step 1: Build HGV index (date + place metadata, keyed by TM ID)
    hgv_index = build_hgv_index(data_dir)

    # Step 2: Parse all DDB documents
    xml_files = find_xml_files(data_dir, "DDB_EpiDoc_XML")
    print("Parsing DDB XML documents...")
    docs: list[PapyriDocument] = []
    failed = 0
    for i, path in enumerate(xml_files):
        doc = parse_metadata_only(path)
        if doc:
            docs.append(doc)
        else:
            failed += 1
        if (i + 1) % 10000 == 0:
            print(f"  {i+1}/{len(xml_files)} parsed ({failed} failures)")
    print(f"Parsed {len(docs)} documents ({failed} failures)")

    # Step 3: Enrich DDB docs with HGV dates/places
    docs_with_tm = sum(1 for d in docs if d.tm_id)
    enriched = enrich_from_hgv(docs, hgv_index)
    print(f"TM IDs found: {docs_with_tm}/{len(docs)}")
    print(f"Enriched with HGV date/place: {enriched} documents")

    # Run all three analyses
    print("\n=== TEMPORAL ANALYSIS ===")
    temporal = temporal_analysis(docs)
    for key, val in temporal.items():
        if key == "period_breakdown":
            print(f"\n  Period breakdown:")
            for period, count in val.items():
                pct = round(100 * count / temporal["total_documents"], 1)
                print(f"    {period:25s} {count:>6,d} docs ({pct}%)")
        else:
            print(f"  {key}: {val}")

    print("\n=== PLACE ANALYSIS ===")
    places = place_analysis(docs)
    print(f"  Unique places: {places['unique_places']}")
    print(f"  Documents with place: {places['documents_with_place']}")
    print(f"\n  Top 15 places:")
    for p in places["top_30_places"][:15]:
        print(f"    {p['place']:40s} {p['count']:>5,d} docs")
    if places["place_names_leaked_as_persons"]:
        print(f"\n  Place names found in person-name list ({len(places['place_names_leaked_as_persons'])} detected):")
        for leak in places["place_names_leaked_as_persons"]:
            print(f"    {leak['place']:30s} -> matched person: {leak['matched_person_name']}")

    print("\n=== ZENON ARCHIVE ANALYSIS ===")
    zenon = zenon_analysis(docs, limit=args.zenon_limit)
    if "status" in zenon:
        print(f"  {zenon['status']}: {zenon.get('note', '')}")
    else:
        print(f"  Documents: {zenon['documents']}")
        print(f"  Graph: {zenon['graph_nodes']} nodes, {zenon['graph_edges']} edges")
        if zenon["archive_date_range"]:
            y0, y1 = zenon["archive_date_range"]
            print(f"  Date range: {abs(y0)} BCE – {abs(y1)} BCE")
        print(f"\n  Top 20 persons in Zenon's network:")
        for p in zenon["top_30_persons"][:20]:
            print(f"    {p['name']:40s} degree {p['degree']:>4d}")
        if zenon["places"]:
            print(f"\n  Places:")
            for p in zenon["places"][:10]:
                print(f"    {p['name']:40s} degree {p['degree']:>4d}")

    # Save everything
    output = {
        "temporal": temporal,
        "places": places,
        "zenon_archive": zenon,
    }
    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()
