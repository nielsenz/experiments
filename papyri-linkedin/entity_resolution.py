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

def are_same_person(name1: str, name2: str) -> bool:
    """Determine if two name variants refer to same person."""
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
    
    def add_variant(self, name: str, count: int = 1):
        if name not in self.variants:
            self.variants.append(name)
        self.mention_count += count

def resolve_entities(name_counts: dict[str, int]) -> list[CanonicalPerson]:
    """Group name variants into canonical persons."""
    sorted_names = sorted(name_counts.items(), key=lambda x: -x[1])
    
    canonical_persons: list[CanonicalPerson] = []
    
    for name, count in sorted_names:
        found_match = False
        for person in canonical_persons:
            if are_same_person(name, person.canonical_name):
                person.add_variant(name, count)
                found_match = True
                break
        
        if not found_match:
            person = CanonicalPerson(
                canonical_name=name,
                variants=[name],
                mention_count=count
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
                'mention_count': p.mention_count
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
        print(f"  {person.canonical_name} ({person.mention_count} mentions, {len(person.variants)} variants)")
        if len(person.variants) > 1:
            variants_str = ', '.join(person.variants[:3])
            if len(person.variants) > 3:
                variants_str += f" (+{len(person.variants)-3} more)"
            print(f"    variants: {variants_str}")
