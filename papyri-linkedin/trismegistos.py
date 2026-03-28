"""Trismegistos API helper for resolving TM IDs to cross-references."""

from __future__ import annotations

import json
import sys
from urllib.request import Request, urlopen

TRISMEGISTOS_API_URL = "https://www.trismegistos.org/dataservices/texrelations"


def fetch_tm_metadata(tm_id: str) -> dict:
    """Fetch cross-reference metadata for a Trismegistos ID.
    
    Returns mapping to other databases (DDBDP, HGV, EDB, etc.)
    Example: fetch_tm_metadata("9") returns links for TM#9
    """
    if not tm_id or not tm_id.strip():
        return {}
    
    try:
        url = f"{TRISMEGISTOS_API_URL}/{tm_id}"
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; PapyriLinkedIn/0.1)",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            text = response.read().decode(charset, errors="replace")
            return json.loads(text)
    except Exception as e:
        print(f"Warning: Failed to fetch TM#{tm_id}: {e}", file=sys.stderr)
        return {}


def resolve_cross_refs(metadata: dict) -> dict:
    """Normalize Trismegistos JSON into a cleaner mapping."""
    result: dict = {"tm_id": metadata.get("TM_ID", [None])[0]}
    
    for key in ["DDB", "EDB", "EDH", "EDCS", "EDR", "HE", "UOXF", "RIB", "PHI", "HGV"]:
        value = metadata.get(key)
        if value:
            result[key.lower()] = value
    
    return result


def main():
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: python3 trismegistos.py <TM_ID>")
        print(f"Example: python3 trismegistos.py 100")
        sys.exit(1)
    
    tm_id = sys.argv[1]
    print(f"Fetching metadata for TM#{tm_id}...")
    
    metadata = fetch_tm_metadata(tm_id)
    if metadata:
        print(json.dumps(metadata, indent=2))
        
        resolved = resolve_cross_refs(metadata)
        print("\nResolved:")
        print(json.dumps(resolved, indent=2))
    else:
        print("No data found")


if __name__ == "__main__":
    main()
