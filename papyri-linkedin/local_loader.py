"""Local XML file loading for papyri-linkedin.

Clone the dataset:
    python3 local_loader.py --setup

Load documents:
    python3 local_loader.py --load 100
"""

from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Optional

from starter import PapyriDocument, parse_document

DEFAULT_DATA_DIR = Path(__file__).parent / "data" / "idp.data"


def setup_local_data(data_dir: Optional[Path] = None) -> Path:
    """Clone and set up the idp.data repository if not present."""
    data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    if data_dir.exists() and (data_dir / "DDB_EpiDoc_XML").exists():
        print(f"Data directory ready: {data_dir}")
        return data_dir

    print(f"Cloning idp.data repository to {data_dir}...")
    parent = data_dir.parent
    parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "git", "clone",
            "--depth", "1",
            "--filter=blob:none",
            "--sparse",
            "https://github.com/papyri/idp.data.git",
            str(data_dir),
        ],
        check=True,
    )

    # Set up sparse checkout for main content directories
    subprocess.run(
        ["git", "sparse-checkout", "init", "--cone"],
        cwd=str(data_dir),
        check=True,
    )
    subprocess.run(
        ["git", "sparse-checkout", "set", "DDB_EpiDoc_XML", "HGV_meta_EpiDoc"],
        cwd=str(data_dir),
        check=True,
    )

    print(f"Data directory ready: {data_dir}")
    return data_dir


def find_local_xml_files(data_dir: Path, limit: Optional[int] = None) -> list[Path]:
    """Find all XML files in the local idp.data repository."""
    ddb_dir = data_dir / "DDB_EpiDoc_XML"
    if not ddb_dir.exists():
        return []

    xml_files = []
    for root, _dirs, files in os.walk(ddb_dir):
        for f in files:
            if f.endswith(".xml"):
                xml_files.append(Path(root) / f)
                if limit and len(xml_files) >= limit:
                    return xml_files
    return xml_files


def load_local_xml_file(file_path: Path) -> Optional[PapyriDocument]:
    """Parse a single local XML file into a PapyriDocument."""
    try:
        xml_text = file_path.read_text(encoding="utf-8")
        return parse_document(str(file_path), xml_text)
    except Exception as e:
        print(f"Warning: Failed to parse {file_path}: {e}", file=sys.stderr)
        return None


def load_local_documents(
    data_dir: Path,
    limit: int = 10,
    sample: bool = True,
) -> list[PapyriDocument]:
    """Load documents from local idp.data repository.

    Args:
        data_dir: Path to idp.data repository
        limit: Maximum number of documents to load
        sample: If True, sample randomly across collections
    """
    xml_files = find_local_xml_files(data_dir)

    if sample and limit and len(xml_files) > limit:
        random.seed(42)  # Reproducible sampling
        xml_files = random.sample(xml_files, limit)
    elif limit:
        xml_files = xml_files[:limit]

    documents: list[PapyriDocument] = []
    for file_path in xml_files:
        doc = load_local_xml_file(file_path)
        if doc:
            documents.append(doc)

    return documents


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load local papyri XML files.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Clone and set up the idp.data repository.",
    )
    parser.add_argument(
        "--load",
        type=int,
        metavar="N",
        help="Load N documents from local data.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Path to the idp.data directory.",
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        default=True,
        help="Sample randomly (default True).",
    )
    parser.add_argument(
        "--no-sample",
        action="store_false",
        dest="sample",
        help="Don't sample, take first N files.",
    )
    args = parser.parse_args()

    if args.setup:
        setup_local_data(args.data_dir)
        return

    if args.load:
        if not args.data_dir.exists():
            print(f"Data directory not found: {args.data_dir}")
            print("Run with --setup first to clone the dataset.")
            return

        print(f"Loading {args.load} documents...")
        docs = load_local_documents(args.data_dir, limit=args.load, sample=args.sample)
        print(f"Loaded {len(docs)} documents")
        for doc in docs[:5]:
            names = ", ".join(doc.explicit_names[:3]) if doc.explicit_names else "(none)"
            print(f"  {doc.record_id}: {names}")
        return

    print("Use --setup to clone data or --load N to load documents.")


if __name__ == "__main__":
    main()
