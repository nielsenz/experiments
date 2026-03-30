from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import networkx as nx

try:
    import spacy
    from spacy.language import Language
    from spacy.pipeline import EntityRuler
except ImportError:  # pragma: no cover
    spacy = None
    Language = None
    EntityRuler = None


PAPYRI_BASE_URL = "https://papyri.info"
PAPYRI_SEARCH_URL = f"{PAPYRI_BASE_URL}/search"
TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_NS = "{http://www.w3.org/XML/1998/namespace}"
DEFAULT_QUERIES = ["letter", "receipt", "petition"]
NAME_STOPWORDS = {
    "Document",
    "Edition",
    "Greek",
    "Latin",
    "Letter",
    "Petition",
    "Receipt",
    "Papyri",
    "Papyrology",
    "Source",
    "Text",
    # Publication metadata
    "Duke",
    "Databank",
    "Documentary",
    "Creative",
    "Commons",
    "Attribution",
    "License",
    "This",
    "Automated",
    "Collaboratory",
    "Classics",
    "Computing",
    "DC3",
    # Place names that leak through as person names (genitive forms)
    "Καρανίδος",
    "Χάρακος",
    "Σοκνοπαίου",
    "Νήσου",
    "Σοκνοπαίου Νήσου",
    "Ὀξυρύγχων",
    "Ἑρμοπόλεως",
    "Ἀρσινοΐτου",
    "Ἡρακλεοπολίτου",
    "Πτολεμαΐδος",
    "Ἀλεξανδρείας",
    "Θεαδελφείας",
    "Φιλαδελφείας",
    "Τεβτύνεως",
    "Ἀφροδίτης",
    # Script and language labels that bleed through from XML metadata
    "Demotic",
    "Coptic",
    "Arabic",
    "Hieratic",
    "Aramaic",
    # Physical/structural terms
    "Recto",
    "Verso",
    "Column",
    "Fragment",
    # Publication sigla
    "SB",
    "BGU",
    "PSI",
    "POxy",
    "PMich",
    "PTebt",
    "BL",
    "CPR",
    "SPP",
    # Egyptian months (Greek forms) — all common orthographic variants
    "Θὼθ",
    "Θωῦθ",
    "Θῶυθ",
    "Θωθ",
    "Φαῶφι",
    "Φαωφι",
    "Ἁθύρ",
    "Ἁθυρ",
    "Αθυρ",
    "Χοίακ",
    "Χοιὰκ",
    "Χοιάκ",
    "Χοίαχ",
    "Χοιαχ",
    "Χοιακ",
    "Τῦβι",
    "Tubia",
    "Τυβι",
    "Μεχείρ",
    "Μεχεὶρ",
    "Μεχιρ",
    "Μεχίρ",
    "Φαμενώθ",
    "Φαμενὼθ",
    "Φαμενωθ",
    "Φαρμοῦθι",
    "Φαρμοῦθ",
    "Φαρμοθι",
    "Φαρμουθι",
    "Παχών",
    "Παχὼν",
    "Παχων",
    "Παῦνι",
    "Παυνι",
    "Ἐπείφ",
    "Ἐπιφ",
    "Επειφ",
    "Μεσορή",
    "Μεσορὴ",
    "Μεσορ",
    # Macedonian months (common in Ptolemaic texts)
    "Δῖος",
    "Ἀπελλαῖος",
    "Αὐδναῖος",
    "Περίτιος",
    "Περιτίου",
    "Δύστρος",
    "Ξανδικός",
    "Ξανθικός",
    "Ἀρτεμίσιος",
    "Δαίσιος",
    "Πάνημος",
    "Λῷος",
    "Γορπιαῖος",
    "Ὑπερβερεταῖος",
    # Additional month variants
    "Παχὼνς",  # variant of Pachon
    # Place names (genitive/oblique forms that masquerade as person names)
    "Αἰγύπτου",  # Egypt (genitive)
    "Αἴγυπτος",
    "Θηβαίδος",  # Thebaid region
    "Κροκοδίλων",  # Krokodilon Polis
    "Μεμνονείων",  # Ta Memnoneia (Theban necropolis)
    "Καισαρείου",  # Caesareum (temple/building)
    "Κερκεσούχων",  # Kerkesouch(a) village
    "Βακχιάδος",  # Bakchias village
    "Διονυσιάδος",  # Dionysias village
    "Μέμφιν",  # Memphis (accusative)
    "Μέμφεως",  # Memphis (genitive)
    "Μέμφει",  # Memphis (dative)
    "Τεπτύνεως",  # Tebtynis variant
    "Θεαδελφίας",  # Theadelphia variant
    "Φιλαδελφίας",  # Philadelphia variant
    # Religious/institutional terms that appear as false person names
    "Χριστοῦ",  # "of Christ"
    "Θεοῦ",  # "of God"
    "Θεῷ",  # "to God"
    # Geographic/directional terms
    "Νότου",  # "south" (wind/compass direction)
    "Λιβὸς",  # "west" / Libya
    # Ethnic labels
    "Πέρσης",  # "Persian"
    # Metadata artifacts from publication/collection provenance
    "Βομπαή",  # Bombay/Mumbai — collection provenance, not a person
    "Reprinted",
}

# Pre-compute accent-stripped lowercase versions so variant orthographies
# that aren't explicitly listed still get caught.
def _normalize_stopword(s: str) -> str:
    import unicodedata as _ud
    d = _ud.normalize("NFD", s)
    return _ud.normalize("NFC", "".join(c for c in d if _ud.category(c) != "Mn")).lower()

_STOPWORDS_NORMALIZED = {_normalize_stopword(w) for w in NAME_STOPWORDS}


def _is_stopword(candidate: str) -> bool:
    """Check if a candidate name matches any stopword (exact or accent-stripped)."""
    if candidate in NAME_STOPWORDS:
        return True
    return _normalize_stopword(candidate) in _STOPWORDS_NORMALIZED



@dataclass
class PapyriDocument:
    """A single papyrological document and the people extracted from it."""

    record_id: str
    title: str
    source_url: str
    xml: str
    text: str
    tm_id: Optional[str] = None
    hgv_id: Optional[str] = None
    date: Optional[str] = None
    place: Optional[str] = None
    date_range: Optional[tuple[int, int]] = None  # (year_from, year_to); negative = BCE
    cross_refs: dict[str, object] = field(default_factory=dict)
    explicit_names: list[str] = field(default_factory=list)
    person_names: list[str] = field(default_factory=list)
    sender: Optional[str] = None
    recipient: Optional[str] = None


# ---------------------------------------------------------------------------
# Small helper functions
# ---------------------------------------------------------------------------

def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_person_name(value: str) -> str:
    value = html.unescape(normalize_whitespace(value))
    return value.strip(" 	\r\n.,;:·—–-[](){}<>")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def fetch_text(url: str, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; PapyriLinkedIn/0.1)",
            "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


# ---------------------------------------------------------------------------
# Papyri.info fetchers
# ---------------------------------------------------------------------------

def build_search_url(query: str, limit: int = 5, target: str = "metadata") -> str:
    params = {
        "STRING": query,
        "target": target,
        "DOCS_PER_PAGE": str(limit),
        "PRINT": "on",
    }
    return f"{PAPYRI_SEARCH_URL}?{urlencode(params)}"


def parse_search_result_urls(search_html: str) -> list[str]:
    """Extract record URLs from a Papyri.info search results page."""

    urls: list[str] = []
    patterns = (
        r'href="(?P<url>/ddbdp/[^"#?]+(?:\?[^"#]*)?)"',
        r'(?P<url>https://papyri\.info/ddbdp/[^"\'<>\s]+)',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, search_html):
            raw_url = match.group("url")
            if raw_url.startswith("/ddbdp/"):
                raw_url = urljoin(PAPYRI_BASE_URL, raw_url)
            raw_url = raw_url.split("?", 1)[0].rstrip("/") + "/source"
            if raw_url not in urls:
                urls.append(raw_url)
    return urls


def fetch_sample_document_urls(
    queries: Iterable[str] | None = None,
    limit: int = 6,
    per_query_limit: int = 5,
) -> list[str]:
    """Fetch a small, diverse set of documentary papyri record URLs.

    The default queries intentionally bias toward documentary genres that
    frequently expose personal names and epistolary relationships.
    """

    queries = list(queries or DEFAULT_QUERIES)
    urls: list[str] = []
    for query in queries:
        search_html = fetch_text(build_search_url(query, limit=per_query_limit))
        for url in parse_search_result_urls(search_html):
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                return urls
    return urls


def fetch_document_xml(source_url: str) -> str:
    return fetch_text(source_url)


# ---------------------------------------------------------------------------
# XML parsing and name extraction
# ---------------------------------------------------------------------------

def extract_text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return normalize_whitespace("".join(elem.itertext()))


def collect_explicit_people(root: ET.Element) -> tuple[list[str], Optional[str], Optional[str]]:
    """Collect name mentions and any explicitly encoded sender/recipient values."""

    names: list[str] = []
    sender: Optional[str] = None
    recipient: Optional[str] = None

    for elem in root.iter():
        tag = local_name(elem.tag)
        attrs = {local_name(key): value for key, value in elem.attrib.items()}
        role_bits = " ".join(
            value
            for value in (
                attrs.get("type", ""),
                attrs.get("subtype", ""),
                attrs.get("role", ""),
                attrs.get("resp", ""),
                attrs.get("corresp", ""),
            )
            if value
        ).lower()
        text = normalize_person_name("".join(elem.itertext()))
        if not text:
            continue

        if tag in {"persName", "name"} or any(
            marker in role_bits
            for marker in ("person", "sender", "recipient", "addressee", "correspondent", "author")
        ):
            names.append(text)

        if any(marker in role_bits for marker in ("sender", "author", "from")):
            sender = sender or text
        if any(marker in role_bits for marker in ("recipient", "addressee", "to")):
            recipient = recipient or text

    deduped: list[str] = []
    for name in names:
        if name not in deduped:
            deduped.append(name)
    return deduped, sender, recipient


def extract_document_text(root: ET.Element) -> str:
    sections: list[str] = []
    # Only extract actual ancient text from edition divs, skip metadata headers
    for path in (
        ".//tei:div[@type='edition']",
        ".//tei:ab",
    ):
        for elem in root.findall(path, TEI_NS):
            text = extract_text(elem)
            if text:
                sections.append(text)
    return normalize_whitespace(" \n ".join(sections))


def _parse_tm_id(root: ET.Element) -> Optional[str]:
    """Extract the Trismegistos document ID from the TEI header."""
    for elem in root.iter():
        tag = local_name(elem.tag)
        if tag == "idno":
            id_type = elem.attrib.get("type", "").lower()
            if id_type == "tm":
                value = (elem.text or "").strip()
                if value:
                    return value
    return None


def _parse_date_range(root: ET.Element) -> Optional[tuple[int, int]]:
    """Extract the document date as a (year_from, year_to) integer tuple.

    Searches for <origDate> with notBefore/notAfter or when attrs.
    Negative values represent BCE years.
    """
    for elem in root.iter():
        if local_name(elem.tag) != "origDate":
            continue
        not_before = elem.attrib.get("notBefore") or elem.attrib.get("notBefore-custom")
        not_after = elem.attrib.get("notAfter") or elem.attrib.get("notAfter-custom")
        when = elem.attrib.get("when") or elem.attrib.get("when-custom")
        try:
            if not_before and not_after:
                return (int(not_before), int(not_after))
            if not_before:
                return (int(not_before), int(not_before))
            if not_after:
                return (int(not_after), int(not_after))
            if when:
                year = int(when)
                return (year, year)
        except (ValueError, TypeError):
            continue
    return None


def _parse_place(root: ET.Element) -> Optional[str]:
    """Extract the document provenance or origin place from the TEI header."""
    # Prefer explicit provenance/origPlace in the header
    for path in (
        ".//tei:origPlace",
        ".//tei:provenance[@type='located']",
        ".//tei:provenance",
    ):
        elem = root.find(path, TEI_NS)
        if elem is not None:
            text = normalize_whitespace("".join(elem.itertext())).strip()
            if text:
                return text
    # Fall back to any placeName in the header settingDesc / sourceDesc area
    header = root.find(".//tei:teiHeader", TEI_NS)
    if header is not None:
        for elem in header.iter():
            if local_name(elem.tag) == "placeName":
                text = normalize_whitespace("".join(elem.itertext())).strip()
                if text:
                    return text
    return None


def parse_document(source_url: str, xml_text: str) -> PapyriDocument:
    root = ET.fromstring(xml_text)
    record_id = root.attrib.get(f"{XML_NS}id") or source_url.rstrip("/").split("/")[-2]
    title = extract_text(root.find(".//tei:titleStmt/tei:title", TEI_NS)) or record_id
    text = extract_document_text(root)
    explicit_names, sender, recipient = collect_explicit_people(root)
    return PapyriDocument(
        record_id=record_id,
        title=title,
        source_url=source_url,
        xml=xml_text,
        text=text,
        tm_id=_parse_tm_id(root),
        date_range=_parse_date_range(root),
        place=_parse_place(root),
        explicit_names=explicit_names,
        sender=sender,
        recipient=recipient,
    )


def fallback_name_candidates(text: str) -> list[str]:
    """Regex-based fallback for names when spaCy is unavailable."""

    candidates: list[str] = []
    pattern = re.compile(
        r"\b(?:[A-ZΑ-ΩΆ-Ώ][\w'’·-]+(?:\s+[A-ZΑ-ΩΆ-Ώ][\w'’·-]+){0,2})\b",
        flags=re.UNICODE,
    )
    for match in pattern.finditer(text):
        candidate = normalize_person_name(match.group(0))
        if not candidate:
            continue
        if _is_stopword(candidate):
            continue
        if len(candidate) < 3:
            continue
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def build_name_pipeline(seed_names: Iterable[str], model_name: str = "en_core_web_sm") -> Language | None:
    """Create a lightweight spaCy pipeline for personal-name extraction.

    If a statistical model is available it is used; otherwise the pipeline falls
    back to a blank multi-language pipeline with an EntityRuler seeded from
    document metadata and generic capitalized-name patterns.
    """

    if spacy is None:
        return None

    try:
        nlp = spacy.load(model_name)
    except Exception:
        nlp = spacy.blank("xx")

    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")

    try:
        ruler = nlp.add_pipe("entity_ruler", before="ner") if "ner" in nlp.pipe_names else nlp.add_pipe("entity_ruler")
    except ValueError:
        ruler = nlp.get_pipe("entity_ruler")

    patterns: list[dict[str, object]] = []
    seen = set()
    for name in seed_names:
        candidate = normalize_person_name(name)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        tokens = candidate.split()
        patterns.append({"label": "PERSON", "pattern": candidate})
        if len(tokens) > 1:
            patterns.append({"label": "PERSON", "pattern": [{"TEXT": token} for token in tokens]})

    patterns.extend(
        [
            {
                "label": "PERSON",
                "pattern": [
                    {"TEXT": {"REGEX": r"^[A-ZΑ-ΩΆ-Ώ][^\s]+$"}},
                ],
            },
            {
                "label": "PERSON",
                "pattern": [
                    {"TEXT": {"REGEX": r"^[A-ZΑ-ΩΆ-Ώ][^\s]+$"}},
                    {"TEXT": {"REGEX": r"^[A-ZΑ-ΩΆ-Ώ][^\s]+$"}},
                ],
            },
        ]
    )

    ruler.add_patterns(patterns)
    return nlp


def extract_person_names(text: str, nlp: Language | None = None) -> list[str]:
    """Return a de-duplicated list of person names from a document body."""

    if nlp is None:
        return fallback_name_candidates(text)

    doc = nlp(text)
    extracted: list[str] = []
    for ent in getattr(doc, "ents", []):
        if ent.label_ not in {"PERSON", "PER"}:
            continue
        candidate = normalize_person_name(ent.text)
        if not candidate or candidate in NAME_STOPWORDS:
            continue
        if candidate not in extracted:
            extracted.append(candidate)
    return extracted or fallback_name_candidates(text)


# ---------------------------------------------------------------------------
# Temporal classification
# ---------------------------------------------------------------------------

def classify_period(year: int) -> str:
    """Map a calendar year to a broad historical period."""
    if year <= -30:
        return "Ptolemaic"
    if year <= 284:
        return "Early Roman"
    if year <= 641:
        return "Late Roman"
    return "Byzantine/Islamic"


def document_period(doc: "PapyriDocument") -> Optional[str]:
    """Return the period label for a document, or None if undated."""
    if doc.date_range is None:
        return None
    midpoint = (doc.date_range[0] + doc.date_range[1]) // 2
    return classify_period(midpoint)


def compute_temporal_stats(
    documents: Iterable["PapyriDocument"], graph: nx.Graph
) -> dict[str, object]:
    """Return per-period counts of documents, distinct persons, and graph edges."""
    from collections import defaultdict

    period_docs: dict[str, list] = defaultdict(list)
    for doc in documents:
        period = document_period(doc) or "Unknown"
        period_docs[period].append(doc)

    stats: dict[str, object] = {}
    for period, docs in sorted(period_docs.items()):
        doc_node_ids = {f"document::{d.record_id}" for d in docs}
        persons: set[str] = set()
        edge_count = 0
        for node_id in doc_node_ids:
            if node_id not in graph:
                continue
            for neighbor in graph.neighbors(node_id):
                if graph.nodes[neighbor].get("kind") == "person":
                    persons.add(neighbor)
                edge_count += 1
        stats[period] = {
            "documents": len(docs),
            "persons": len(persons),
            "edges": edge_count,
        }
    return stats


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def ensure_node(graph: nx.Graph, node_id: str, **attrs: object) -> None:
    if node_id in graph:
        graph.nodes[node_id].update(attrs)
    else:
        graph.add_node(node_id, **attrs)


def add_edge_metadata(
    graph: nx.Graph,
    source: str,
    target: str,
    relation: str,
    document_id: str,
) -> None:
    if graph.has_edge(source, target):
        data = graph[source][target]
        data["weight"] = int(data.get("weight", 0)) + 1
        data["documents"] = sorted(set(data.get("documents", [])) | {document_id})
        relation_types = set(data.get("relation_types", []))
        relation_types.add(relation)
        data["relation_types"] = sorted(relation_types)
    else:
        graph.add_edge(
            source,
            target,
            weight=1,
            documents=[document_id],
            relation_types=[relation],
        )


def build_social_graph(documents: Iterable[PapyriDocument]) -> nx.Graph:
    graph = nx.Graph()

    for document in documents:
        doc_node = f"document::{document.record_id}"
        period = document_period(document)
        ensure_node(
            graph,
            doc_node,
            kind="document",
            title=document.title,
            source_url=document.source_url,
            period=period,
            date_range=document.date_range,
            place=document.place,
            tm_id=document.tm_id,
        )

        people = list(dict.fromkeys(document.person_names + document.explicit_names))
        if document.sender:
            people.append(document.sender)
        if document.recipient:
            people.append(document.recipient)
        people = list(dict.fromkeys(normalize_person_name(person) for person in people if person))

        for person in people:
            person_node = f"person::{person}"
            ensure_node(graph, person_node, kind="person", name=person)
            add_edge_metadata(graph, doc_node, person_node, "mentioned_in_document", document.record_id)

        for left, right in itertools.combinations(people, 2):
            add_edge_metadata(
                graph,
                f"person::{left}",
                f"person::{right}",
                "co_occurs_in_document",
                document.record_id,
            )

        if document.sender and document.recipient:
            add_edge_metadata(
                graph,
                f"person::{normalize_person_name(document.sender)}",
                f"person::{normalize_person_name(document.recipient)}",
                "epistolary_link",
                document.record_id,
            )

        if document.place:
            place_node = f"place::{document.place}"
            ensure_node(graph, place_node, kind="place", name=document.place)
            add_edge_metadata(graph, doc_node, place_node, "located_in", document.record_id)

    return graph


# ---------------------------------------------------------------------------
# Trismegistos enrichment
# ---------------------------------------------------------------------------

def enrich_with_trismegistos(
    documents: list[PapyriDocument],
    cache_path: str | None = None,
) -> None:
    """Fetch Trismegistos cross-reference metadata for documents that have a TM ID.

    Results are stored in-place on each document's ``cross_refs`` dict.  A
    simple JSON file cache (keyed by TM ID) avoids redundant HTTP requests
    across runs — pass *cache_path* to enable it.
    """
    from trismegistos import fetch_tm_metadata, resolve_cross_refs

    cache: dict[str, dict] = {}
    if cache_path:
        cache_file = Path(cache_path)
        if cache_file.exists():
            try:
                cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                cache = {}

    changed = False
    for doc in documents:
        if not doc.tm_id:
            continue
        if doc.tm_id in cache:
            doc.cross_refs = cache[doc.tm_id]
            continue
        raw = fetch_tm_metadata(doc.tm_id)
        if raw:
            refs = resolve_cross_refs(raw)
            doc.cross_refs = refs
            cache[doc.tm_id] = refs
            changed = True

    if cache_path and changed:
        Path(cache_path).write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---------------------------------------------------------------------------
# Local-file support retained for convenience
# ---------------------------------------------------------------------------

def load_local_documents(path: str) -> list[dict[str, str]]:
    file_path = Path(path)
    if file_path.suffix.lower() == ".csv":
        with file_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [
                {
                    "doc_id": row.get("doc_id") or row.get("id") or file_path.stem,
                    "text": row.get("text", ""),
                }
                for row in reader
            ]
    return [{"doc_id": file_path.stem, "text": file_path.read_text(encoding="utf-8")}]


# ---------------------------------------------------------------------------
# Pipeline runner / CLI
# ---------------------------------------------------------------------------

def fetch_papyri_documents(queries: Iterable[str], limit: int = 6) -> list[PapyriDocument]:
    urls = fetch_sample_document_urls(queries=queries, limit=limit)
    documents: list[PapyriDocument] = []
    for url in urls:
        xml_text = fetch_document_xml(url)
        documents.append(parse_document(url, xml_text))
    return documents


def run_pipeline(
    queries: Iterable[str] | None = None,
    limit: int = 6,
    model_name: str = "en_core_web_sm",
    input_path: str | None = None,
    trismegistos_cache: str | None = None,
) -> tuple[list[PapyriDocument], nx.Graph]:
    if input_path:
        local_rows = load_local_documents(input_path)
        documents = [
            PapyriDocument(
                record_id=str(row["doc_id"]),
                title=str(row["doc_id"]),
                source_url=input_path,
                xml="",
                text=str(row["text"]),
            )
            for row in local_rows
        ]
    else:
        documents = fetch_papyri_documents(queries or DEFAULT_QUERIES, limit=limit)

    seed_names = []
    for document in documents:
        seed_names.extend(document.explicit_names)
        if document.sender:
            seed_names.append(document.sender)
        if document.recipient:
            seed_names.append(document.recipient)

    nlp = build_name_pipeline(seed_names, model_name=model_name)

    for document in documents:
        search_text = "\n".join(
            part for part in (document.title, document.text) if part
        )
        document.person_names = extract_person_names(search_text, nlp=nlp)
        for name in document.explicit_names:
            if name not in document.person_names:
                document.person_names.append(name)
        if document.sender and document.sender not in document.person_names:
            document.person_names.append(document.sender)
        if document.recipient and document.recipient not in document.person_names:
            document.person_names.append(document.recipient)

    if trismegistos_cache is not None:
        enrich_with_trismegistos(documents, cache_path=trismegistos_cache)

    graph = build_social_graph(documents)
    return documents, graph


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch a small papyrological sample from Papyri.info, extract names, and build a social graph.",
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        help="Optional local CSV/text file. If omitted, the script fetches sample papyri from Papyri.info.",
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        default=DEFAULT_QUERIES,
        help="Search terms used against Papyri.info when no local input file is provided.",
    )
    parser.add_argument("--limit", type=int, default=6, help="Maximum number of Papyri.info documents to fetch.")
    parser.add_argument(
        "--model",
        default="en_core_web_sm",
        help="spaCy model name to use when available.",
    )
    parser.add_argument(
        "--enrich-trismegistos",
        metavar="CACHE_FILE",
        default=None,
        help="Fetch Trismegistos cross-refs for documents that have a TM ID. "
             "Results are cached in CACHE_FILE (JSON) to avoid repeated HTTP calls.",
    )
    args = parser.parse_args()

    documents, graph = run_pipeline(
        queries=args.queries,
        limit=args.limit,
        model_name=args.model,
        input_path=args.input_path,
        trismegistos_cache=args.enrich_trismegistos,
    )

    print(f"documents={len(documents)} nodes={graph.number_of_nodes()} edges={graph.number_of_edges()}")
    for document in documents:
        sample_names = ", ".join(document.person_names[:5]) if document.person_names else "(none found)"
        meta = []
        if document.tm_id:
            meta.append(f"TM={document.tm_id}")
        if document.date_range:
            meta.append(f"dates={document.date_range[0]}–{document.date_range[1]}")
        if document.place:
            meta.append(f"place={document.place}")
        meta_str = f"  [{', '.join(meta)}]" if meta else ""
        print(f"{document.record_id}:{meta_str} {sample_names}")

    temporal = compute_temporal_stats(documents, graph)
    if temporal:
        print("\nTemporal breakdown:")
        for period, stats in temporal.items():
            print(f"  {period}: {stats['documents']} docs, {stats['persons']} persons, {stats['edges']} edges")


if __name__ == "__main__":
    main()
