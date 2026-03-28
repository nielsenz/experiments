"""Entity resolution for Greek/Latin personal names in papyri."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional

def normalize_greek(name: str) -> str:
    """Normalize Greek name: remove accents, lowercase."""
    decomposed = unicodedata.normalize('NFD', name)
    without_accents = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
    return unicodedata.normalize('NFC', without_accents).lower().strip()

def extract_name_parts(name: str) -> list[str]:
    """Break name into parts."""
    normalized = normalize_greek(name)
    return [p for p in normalized.split() if len(p) > 1]

def name_similarity(name1: str, name2: str) -> float:
    """Calculate similarity between two names (0-1)."""
    parts1 = extract_name_parts(name1)
    parts2 = extract_name_parts(name2)
    
    if not parts1 or not parts2:
        return 0.0
    
    if len(parts1) == 1 and len(parts2) == 1:
        return 1.0 if parts1[0] == parts2[0] else 0.0
    
    shared = set(parts1) & set(parts2)
    total = set(parts1) | set(parts2)
    
    if not total:
        return 0.0
    
    return len(shared) / len(total)

def ranges_overlap(
    r1: tuple[int, int],
    r2: tuple[int, int],
    tolerance: int = 200,
) -> bool:
    """Return True if two year ranges come within *tolerance* years of each other.

    A tolerance of 200 means names from different centuries can still merge if
    they are within 200 years of each other — necessary because many papyri are
    only dated to a broad range.  Increase tolerance to be more permissive,
    decrease it for stricter temporal separation.
    """
    return r1[0] - tolerance <= r2[1] and r2[0] - tolerance <= r1[1]


def are_same_person(
    name1: str,
    name2: str,
    range1: Optional[tuple[int, int]] = None,
    range2: Optional[tuple[int, int]] = None,
) -> bool:
    """Determine if two name variants refer to the same person.

    If both *range1* and *range2* are provided and the date ranges do not
    overlap (within the default 200-year tolerance), the names are considered
    distinct regardless of textual similarity.
    """
    if range1 is not None and range2 is not None:
        if not ranges_overlap(range1, range2):
            return False

    if normalize_greek(name1) == normalize_greek(name2):
        return True

    sim = name_similarity(name1, name2)
    return sim >= 0.5


@dataclass
class CanonicalPerson:
    """A canonical person with all their name variants."""
    canonical_name: str
    variants: list[str] = field(default_factory=list)
    mention_count: int = 0
    year_range: Optional[tuple[int, int]] = None

    def add_variant(self, name: str, count: int = 1, date_range: Optional[tuple[int, int]] = None):
        if name not in self.variants:
            self.variants.append(name)
        self.mention_count += count
        # Extend the canonical year_range to encompass the new variant's range.
        if date_range is not None:
            if self.year_range is None:
                self.year_range = date_range
            else:
                self.year_range = (
                    min(self.year_range[0], date_range[0]),
                    max(self.year_range[1], date_range[1]),
                )


def resolve_entities(
    name_counts: dict[str, int],
    name_date_ranges: Optional[dict[str, tuple[int, int]]] = None,
) -> list[CanonicalPerson]:
    """Group name variants into canonical persons.

    Args:
        name_counts: mapping of name string → mention count.
        name_date_ranges: optional mapping of name string → (year_from, year_to).
            When provided, names whose date ranges don't overlap will not be merged
            even if they are textually similar.
    """
    sorted_names = sorted(name_counts.items(), key=lambda x: -x[1])
    name_date_ranges = name_date_ranges or {}

    canonical_persons: list[CanonicalPerson] = []

    for name, count in sorted_names:
        name_range = name_date_ranges.get(name)
        found_match = False
        for person in canonical_persons:
            if are_same_person(name, person.canonical_name, name_range, person.year_range):
                person.add_variant(name, count, name_range)
                found_match = True
                break

        if not found_match:
            person = CanonicalPerson(
                canonical_name=name,
                variants=[name],
                mention_count=count,
                year_range=name_range,
            )
            canonical_persons.append(person)

    return canonical_persons

def load_and_resolve_from_analysis(json_path: str) -> list[CanonicalPerson]:
    """Load analysis JSON and resolve entities."""
    import json
    
    with open(json_path) as f:
        data = json.load(f)
    
    # Parse [[name, count], ...] format
    all_names = {name: count for name, count in data['top_names']}
    print(f"Resolving {len(all_names)} names...")
    
    canonical = resolve_entities(all_names)
    print(f"Resolved into {len(canonical)} canonical persons")
    print(f"Reduction: {100*(1-len(canonical)/len(all_names)):.1f}%")
    
    return canonical

if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python3 entity_resolution.py <analysis.json>")
        sys.exit(1)
    
    canonical = load_and_resolve_from_analysis(sys.argv[1])
    
    # Save results
    output_data = {
        'canonical_persons': [
            {
                'canonical_name': p.canonical_name,
                'variants': p.variants,
                'mention_count': p.mention_count,
                'year_range': list(p.year_range) if p.year_range else None,
            }
            for p in sorted(canonical, key=lambda p: -p.mention_count)
        ]
    }
    
    output_path = sys.argv[1].replace('.json', '_resolved.json')
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to {output_path}")
    
    print("\nTop 20 canonical persons:")
    for person in sorted(canonical, key=lambda p: -p.mention_count)[:20]:
        range_str = ""
        if person.year_range:
            y0 = f"{abs(person.year_range[0])}{'BCE' if person.year_range[0] < 0 else 'CE'}"
            y1 = f"{abs(person.year_range[1])}{'BCE' if person.year_range[1] < 0 else 'CE'}"
            range_str = f", {y0}–{y1}"
        print(f"  {person.canonical_name} ({person.mention_count} mentions, {len(person.variants)} variants{range_str})")
        if len(person.variants) > 1:
            variants_str = ', '.join(person.variants[:3])
            if len(person.variants) > 3:
                variants_str += f" (+{len(person.variants)-3} more)"
            print(f"    variants: {variants_str}")
