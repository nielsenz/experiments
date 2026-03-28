"""Geographic network analysis of the papyri corpus.

Builds a place-to-place network where two places are connected if the same
person name appears in documents from both locations. This reveals communication
and migration patterns across ancient Egypt and the Mediterranean.

Usage:
    uv run python geographic_network.py [--data-dir DATA_DIR] [--min-shared N]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import networkx as nx

from analyze_metadata import build_hgv_index, enrich_from_hgv, find_xml_files, parse_metadata_only
from starter import (
    PapyriDocument,
    classify_period,
    fallback_name_candidates,
    normalize_person_name,
)
from entity_resolution import normalize_greek, stem_greek


DEFAULT_DATA_DIR = Path("data/idp.data")


def normalize_place(place: str) -> str:
    """Normalize place name for grouping.

    Strips parenthetical qualifiers like '(Arsinoites)' and '(?)' to group
    variants like 'Karanis (Arsinoites)' and 'Karanis' together.
    """
    import re
    # Remove trailing (?) uncertainty markers
    place = re.sub(r"\s*\(\?\)\s*$", "", place)
    # Keep the base name but strip district qualifiers for grouping
    base = re.sub(r"\s*\([^)]*\)\s*$", "", place).strip()
    return base if base else place


def build_place_person_index(
    docs: list[PapyriDocument],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build bidirectional indexes: place → person names, person → places.

    Returns (place_to_persons, person_to_places).
    """
    place_to_persons: dict[str, set[str]] = defaultdict(set)
    person_to_places: dict[str, set[str]] = defaultdict(set)

    for doc in docs:
        if not doc.place:
            continue
        place = normalize_place(doc.place)
        if place in ("unbekannt", "Fundort:", ""):
            continue

        # Extract names from text using fallback NER
        names = doc.person_names
        if not names and doc.text:
            names = fallback_name_candidates(doc.text)

        for name in names:
            # Normalize: accent-strip + stem to nominative
            key = stem_greek(normalize_greek(normalize_person_name(name)))
            if len(key) < 3:
                continue
            place_to_persons[place].add(key)
            person_to_places[key].add(place)

    return dict(place_to_persons), dict(person_to_places)


def build_place_network(
    person_to_places: dict[str, set[str]],
    min_shared: int = 5,
) -> nx.Graph:
    """Build a place-to-place graph weighted by number of shared person names.

    An edge between place A and place B means at least `min_shared` distinct
    person name stems appear in documents from both locations.
    """
    # Count shared persons between each pair of places
    pair_counts: Counter = Counter()
    pair_names: dict[tuple[str, str], set[str]] = defaultdict(set)

    for person, places in person_to_places.items():
        if len(places) < 2:
            continue
        place_list = sorted(places)
        for i, p1 in enumerate(place_list):
            for p2 in place_list[i + 1 :]:
                pair = (p1, p2)
                pair_counts[pair] += 1
                pair_names[pair].add(person)

    graph = nx.Graph()
    for (p1, p2), count in pair_counts.items():
        if count >= min_shared:
            graph.add_edge(p1, p2, weight=count, shared_names=len(pair_names[(p1, p2)]))

    return graph


def analyze_place_connectivity(
    graph: nx.Graph,
    place_to_persons: dict[str, set[str]],
) -> dict:
    """Compute network statistics for the place graph."""
    if graph.number_of_nodes() == 0:
        return {"status": "empty graph"}

    # Degree centrality (most connected places)
    degrees = sorted(
        [(node, graph.degree(node, weight="weight")) for node in graph.nodes()],
        key=lambda x: -x[1],
    )

    # Betweenness centrality (places that bridge between regions)
    betweenness = nx.betweenness_centrality(graph, weight=None)
    top_bridges = sorted(betweenness.items(), key=lambda x: -x[1])

    # Identify clusters/communities
    components = list(nx.connected_components(graph))
    components.sort(key=len, reverse=True)

    # Top edges by weight (strongest connections)
    edges = sorted(graph.edges(data=True), key=lambda x: -x[2]["weight"])

    return {
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "components": len(components),
        "largest_component": len(components[0]) if components else 0,
        "top_20_by_degree": [
            {
                "place": p,
                "weighted_degree": d,
                "unique_persons": len(place_to_persons.get(p, set())),
                "neighbors": graph.degree(p),
            }
            for p, d in degrees[:20]
        ],
        "top_15_bridges": [
            {"place": p, "betweenness": round(b, 4)} for p, b in top_bridges[:15]
        ],
        "top_20_edges": [
            {
                "from": e[0],
                "to": e[1],
                "shared_persons": e[2]["weight"],
            }
            for e in edges[:20]
        ],
        "component_sizes": [len(c) for c in components[:10]],
    }


def fayum_analysis(
    person_to_places: dict[str, set[str]],
    place_to_persons: dict[str, set[str]],
) -> dict:
    """Test whether the Fayum is a self-contained social world or connected outward."""
    fayum_places = {
        "Karanis", "Tebtynis", "Philadelphia", "Theadelphia",
        "Soknopaiu Nesos", "Krokodilopolis", "Bacchias", "Narmouthis",
        "Arsinoites", "Hawara", "Euhemeria", "Dionysias",
    }

    fayum_persons: set[str] = set()
    for place in fayum_places:
        fayum_persons.update(place_to_persons.get(place, set()))

    # How many Fayum persons also appear elsewhere?
    external_connections: Counter = Counter()
    fayum_only = 0
    connected_outward = 0

    for person in fayum_persons:
        places = person_to_places.get(person, set())
        non_fayum = places - fayum_places
        if non_fayum:
            connected_outward += 1
            for place in non_fayum:
                external_connections[place] += 1
        else:
            fayum_only += 1

    return {
        "total_fayum_persons": len(fayum_persons),
        "fayum_only": fayum_only,
        "connected_outward": connected_outward,
        "outward_pct": round(100 * connected_outward / len(fayum_persons), 1) if fayum_persons else 0,
        "top_external_connections": [
            {"place": p, "shared_persons": c}
            for p, c in external_connections.most_common(20)
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Geographic network analysis of papyri corpus")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--min-shared", type=int, default=5, help="Min shared persons for a place-place edge")
    parser.add_argument("--output", default="geographic_analysis.json")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)

    # Load and enrich documents
    hgv_index = build_hgv_index(data_dir)
    xml_files = find_xml_files(data_dir, "DDB_EpiDoc_XML")

    print("Parsing documents and extracting names...")
    docs: list[PapyriDocument] = []
    for i, path in enumerate(xml_files):
        doc = parse_metadata_only(path)
        if doc is None:
            continue
        # Enrich with HGV
        if doc.tm_id and doc.tm_id in hgv_index:
            meta = hgv_index[doc.tm_id]
            if "date_range" in meta:
                doc.date_range = meta["date_range"]
            if "place" in meta and not doc.place:
                doc.place = meta["place"]

        # Extract names from text
        if doc.text:
            doc.person_names = fallback_name_candidates(doc.text)

        docs.append(doc)
        if (i + 1) % 10000 == 0:
            print(f"  {i+1}/{len(xml_files)}...")

    docs_with_place = [d for d in docs if d.place and normalize_place(d.place) not in ("unbekannt", "Fundort:", "")]
    print(f"Parsed {len(docs)} docs, {len(docs_with_place)} with known places")

    # Build indexes
    print("Building place-person index...")
    place_to_persons, person_to_places = build_place_person_index(docs)
    print(f"  {len(place_to_persons)} places, {len(person_to_places)} distinct person stems")

    # Build place network
    print(f"Building place network (min_shared={args.min_shared})...")
    graph = build_place_network(person_to_places, min_shared=args.min_shared)
    print(f"  {graph.number_of_nodes()} place nodes, {graph.number_of_edges()} edges")

    # Analyze
    print("\nAnalyzing network structure...")
    stats = analyze_place_connectivity(graph, place_to_persons)

    print("\n" + "=" * 80)
    print("PLACE NETWORK: MOST CONNECTED LOCATIONS")
    print("=" * 80)
    for p in stats["top_20_by_degree"]:
        print(f"  {p['place']:40s}  degree {p['neighbors']:>3d}  "
              f"weighted {p['weighted_degree']:>6d}  persons {p['unique_persons']:>5d}")

    print("\n" + "=" * 80)
    print("STRONGEST PLACE-TO-PLACE CONNECTIONS (shared persons)")
    print("=" * 80)
    for e in stats["top_20_edges"]:
        print(f"  {e['from']:30s} ↔ {e['to']:30s}  {e['shared_persons']:>5d} shared")

    print("\n" + "=" * 80)
    print("BRIDGE LOCATIONS (betweenness centrality)")
    print("=" * 80)
    for p in stats["top_15_bridges"]:
        print(f"  {p['place']:40s}  betweenness {p['betweenness']:.4f}")

    # Fayum analysis
    print("\n" + "=" * 80)
    print("FAYUM CONNECTIVITY: INSULAR OR CONNECTED?")
    print("=" * 80)
    fayum = fayum_analysis(person_to_places, place_to_persons)
    print(f"  Total persons in Fayum documents: {fayum['total_fayum_persons']:,d}")
    print(f"  Fayum-only (no external docs):    {fayum['fayum_only']:,d} ({100-fayum['outward_pct']:.1f}%)")
    print(f"  Also appear outside Fayum:         {fayum['connected_outward']:,d} ({fayum['outward_pct']}%)")
    print(f"\n  Top external connections:")
    for c in fayum["top_external_connections"]:
        print(f"    {c['place']:40s}  {c['shared_persons']:>4d} shared persons")

    # Save
    output = {
        "network_stats": stats,
        "fayum": fayum,
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
