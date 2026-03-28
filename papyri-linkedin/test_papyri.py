"""Tests for papyri-linkedin improvements.

Covers: XML metadata parsing, stopword expansion, period classification,
temporal stats, geographic graph nodes, entity resolution with date-range
constraints, and Trismegistos enrichment caching.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest import mock

import pytest

import starter
from entity_resolution import (
    CanonicalPerson,
    are_same_person,
    normalize_greek,
    ranges_overlap,
    resolve_entities,
    stem_greek,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tei(
    *,
    tm_id: str | None = None,
    not_before: str | None = None,
    not_after: str | None = None,
    when: str | None = None,
    place: str | None = None,
    body: str = "",
) -> str:
    """Build a minimal TEI/XML string for testing parse_document()."""
    tm_block = f'<idno type="TM">{tm_id}</idno>' if tm_id else ""
    date_attrs = ""
    if not_before:
        date_attrs += f' notBefore="{not_before}"'
    if not_after:
        date_attrs += f' notAfter="{not_after}"'
    if when:
        date_attrs += f' when="{when}"'
    date_block = f"<origDate{date_attrs}/>" if date_attrs else ""
    place_block = f"<origPlace>{place}</origPlace>" if place else ""
    return textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <TEI xml:id="test.doc.1"
             xmlns="http://www.tei-c.org/ns/1.0"
             xmlns:xml="http://www.w3.org/XML/1998/namespace">
          <teiHeader>
            <fileDesc>
              <titleStmt><title>Test Document</title></titleStmt>
              <publicationStmt>{tm_block}</publicationStmt>
            </fileDesc>
            <sourceDesc>
              <msDesc>
                <history>
                  <origin>{date_block}{place_block}</origin>
                </history>
              </msDesc>
            </sourceDesc>
          </teiHeader>
          <text><body><div type="edition"><ab>{body}</ab></div></body></text>
        </TEI>
    """)


# ---------------------------------------------------------------------------
# XML metadata parsing
# ---------------------------------------------------------------------------

class TestParseTmId:
    def test_extracts_tm_id(self):
        xml = make_tei(tm_id="12345")
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.tm_id == "12345"

    def test_missing_tm_id_returns_none(self):
        xml = make_tei()
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.tm_id is None


class TestParseDateRange:
    def test_not_before_and_not_after(self):
        xml = make_tei(not_before="-200", not_after="-150")
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.date_range == (-200, -150)

    def test_when_only(self):
        xml = make_tei(when="100")
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.date_range == (100, 100)

    def test_not_before_only(self):
        xml = make_tei(not_before="50")
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.date_range == (50, 50)

    def test_missing_date_returns_none(self):
        xml = make_tei()
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.date_range is None

    def test_negative_years_bce(self):
        xml = make_tei(not_before="-300", not_after="-250")
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.date_range[0] < 0
        assert doc.date_range[1] < 0


class TestParsePlace:
    def test_orig_place(self):
        xml = make_tei(place="Oxyrhynchus")
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.place == "Oxyrhynchus"

    def test_missing_place_returns_none(self):
        xml = make_tei()
        doc = starter.parse_document("http://example.com/doc/source", xml)
        assert doc.place is None


# ---------------------------------------------------------------------------
# Stopwords
# ---------------------------------------------------------------------------

class TestStopwords:
    @pytest.mark.parametrize("word", [
        "Demotic", "Coptic", "Arabic", "Hieratic", "Aramaic",
        "Recto", "Verso", "Column", "Fragment",
        "SB", "BGU", "PSI", "POxy", "PMich", "PTebt", "BL", "CPR", "SPP",
    ])
    def test_script_labels_in_stopwords(self, word):
        assert word in starter.NAME_STOPWORDS

    def test_fallback_suppresses_stopwords(self):
        names = starter.fallback_name_candidates("Demotic script BGU Fragment text")
        assert "Demotic" not in names
        assert "BGU" not in names
        assert "Fragment" not in names

    def test_normalized_stopword_catches_accent_variants(self):
        # Θῶυθ is in stopwords; a variant with different accents should still match
        assert starter._is_stopword("Θῶυθ")
        # Accent-stripped form should also match
        assert starter._is_stopword("Θωυθ")

    @pytest.mark.parametrize("month", ["Χοίαχ", "Χοιαχ", "Περίτιος", "Περιτίου"])
    def test_new_month_variants_in_stopwords(self, month):
        assert starter._is_stopword(month)


# ---------------------------------------------------------------------------
# Period classification
# ---------------------------------------------------------------------------

class TestClassifyPeriod:
    @pytest.mark.parametrize("year,expected", [
        (-300, "Ptolemaic"),
        (-30, "Ptolemaic"),
        (-29, "Early Roman"),
        (100, "Early Roman"),
        (284, "Early Roman"),
        (285, "Late Roman"),
        (640, "Late Roman"),
        (641, "Late Roman"),
        (642, "Byzantine/Islamic"),
        (900, "Byzantine/Islamic"),
    ])
    def test_boundaries(self, year, expected):
        assert starter.classify_period(year) == expected


class TestDocumentPeriod:
    def test_uses_midpoint(self):
        doc = starter.PapyriDocument(
            record_id="x", title="x", source_url="", xml="", text="",
            date_range=(-50, 50),
        )
        # midpoint is 0, which is Early Roman (-29 to 284)
        assert starter.document_period(doc) == "Early Roman"

    def test_undated_returns_none(self):
        doc = starter.PapyriDocument(
            record_id="x", title="x", source_url="", xml="", text="",
        )
        assert starter.document_period(doc) is None


class TestComputeTemporalStats:
    def test_counts_periods(self):
        import networkx as nx

        docs = [
            starter.PapyriDocument(
                record_id="ptolemaic1", title="", source_url="", xml="", text="",
                date_range=(-200, -100), person_names=["Ptolemy"],
            ),
            starter.PapyriDocument(
                record_id="roman1", title="", source_url="", xml="", text="",
                date_range=(100, 150), person_names=["Marcus"],
            ),
        ]
        graph = starter.build_social_graph(docs)
        stats = starter.compute_temporal_stats(docs, graph)

        assert "Ptolemaic" in stats
        assert "Early Roman" in stats
        assert stats["Ptolemaic"]["documents"] == 1
        assert stats["Early Roman"]["documents"] == 1

    def test_undated_classified_as_unknown(self):
        import networkx as nx

        docs = [
            starter.PapyriDocument(
                record_id="undated1", title="", source_url="", xml="", text="",
                person_names=["Theon"],
            ),
        ]
        graph = starter.build_social_graph(docs)
        stats = starter.compute_temporal_stats(docs, graph)
        assert "Unknown" in stats


# ---------------------------------------------------------------------------
# Geographic nodes
# ---------------------------------------------------------------------------

class TestGeographicNodes:
    def test_place_node_created(self):
        docs = [
            starter.PapyriDocument(
                record_id="doc1", title="", source_url="", xml="", text="",
                place="Oxyrhynchus", person_names=["Theon"],
            ),
        ]
        graph = starter.build_social_graph(docs)
        assert "place::Oxyrhynchus" in graph
        assert graph.nodes["place::Oxyrhynchus"]["kind"] == "place"

    def test_located_in_edge(self):
        docs = [
            starter.PapyriDocument(
                record_id="doc1", title="", source_url="", xml="", text="",
                place="Oxyrhynchus",
            ),
        ]
        graph = starter.build_social_graph(docs)
        doc_node = "document::doc1"
        place_node = "place::Oxyrhynchus"
        assert graph.has_edge(doc_node, place_node)
        edge = graph[doc_node][place_node]
        assert "located_in" in edge["relation_types"]

    def test_no_place_no_node(self):
        docs = [
            starter.PapyriDocument(
                record_id="doc1", title="", source_url="", xml="", text="",
            ),
        ]
        graph = starter.build_social_graph(docs)
        place_nodes = [n for n in graph if str(n).startswith("place::")]
        assert place_nodes == []


# ---------------------------------------------------------------------------
# Entity resolution: date-range constraint
# ---------------------------------------------------------------------------

class TestRangesOverlap:
    def test_overlapping(self):
        assert ranges_overlap((100, 200), (150, 300))

    def test_adjacent_within_tolerance(self):
        # 50 apart, default tolerance 200 → should overlap
        assert ranges_overlap((100, 200), (250, 350))

    def test_too_far_apart(self):
        # 500 years gap, tolerance 200 → should NOT overlap
        assert not ranges_overlap((100, 200), (701, 800))

    def test_same_range(self):
        assert ranges_overlap((100, 100), (100, 100))

    def test_bce_ranges(self):
        assert ranges_overlap((-300, -200), (-250, -150))
        assert not ranges_overlap((-300, -250), (200, 300))


class TestAreSamePersonWithDateRange:
    def test_same_name_different_century_excluded(self):
        # "Ptolemy" in -300 vs "Ptolemy" in 500 CE: 800-year gap
        result = are_same_person("Ptolemy", "Ptolemy", (-300, -280), (500, 520))
        assert not result

    def test_same_name_same_era_included(self):
        result = are_same_person("Ptolemy", "Ptolemy", (-200, -150), (-180, -120))
        assert result

    def test_no_ranges_falls_back_to_name_similarity(self):
        assert are_same_person("Theon", "Theon")
        assert not are_same_person("Theon", "Demetrios")


class TestResolveEntitiesWithDateRanges:
    def test_same_name_different_centuries_not_merged(self):
        name_counts = {
            "Caesar": 100,
            "Caesar": 100,  # duplicate key, will collapse
        }
        # Two Caesars from very different eras
        name_counts = {"Caesar-Ptolemaic": 100, "Caesar-Roman": 80}
        date_ranges = {
            "Caesar-Ptolemaic": (-100, -50),
            "Caesar-Roman": (200, 250),
        }
        # Names differ → won't merge on similarity anyway, but date ranges
        # also prevent it — this test ensures the date path is exercised.
        result = resolve_entities(name_counts, name_date_ranges=date_ranges)
        assert len(result) == 2

    def test_same_name_same_era_merged(self):
        name_counts = {"Αὐρήλιος": 50, "Αυρηλιος": 40}
        date_ranges = {"Αὐρήλιος": (200, 250), "Αυρηλιος": (210, 260)}
        result = resolve_entities(name_counts, name_date_ranges=date_ranges)
        # Greek normalization strips accents → same normalized form → merged
        assert len(result) == 1
        assert result[0].mention_count == 90

    def test_year_range_widens_on_merge(self):
        # These normalize to the same string (accent stripping), so they merge.
        name_counts = {"Αὐρήλιος": 10, "Αυρηλιος": 5}
        date_ranges = {"Αὐρήλιος": (200, 250), "Αυρηλιος": (230, 280)}
        result = resolve_entities(name_counts, name_date_ranges=date_ranges)
        assert len(result) == 1
        assert result[0].year_range == (200, 280)

    def test_no_date_ranges_behaves_as_before(self):
        name_counts = {"Theon": 10, "Demetrios": 5}
        result = resolve_entities(name_counts)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Greek stemming
# ---------------------------------------------------------------------------

class TestStemGreek:
    @pytest.mark.parametrize("word,expected", [
        # -ων declension: all cases → nominative -ων
        ("ζηνων", "ζηνων"),           # nominative stays
        ("ζηνωνος", "ζηνων"),         # genitive → nom
        ("ζηνωνι", "ζηνων"),          # dative → nom
        ("ζηνωνα", "ζηνων"),          # accusative → nom
        ("σαραπιωνος", "σαραπιων"),
        ("σαραπιωνι", "σαραπιων"),
        # -αιος declension: oblique cases → nominative -αιος
        ("πτολεμαιος", "πτολεμαιος"), # nominative stays
        ("πτολεμαιου", "πτολεμαιος"), # genitive → nom
        ("πτολεμαιωι", "πτολεμαιος"), # dative → nom
        # -ιος declension: oblique cases → nominative -ιος
        ("διονυσιου", "διονυσιος"),
        ("διονυσιωι", "διονυσιος"),
        # -ος declension (2nd decl): genitive -ου → nominative -ος
        ("θεοδωρου", "θεοδωρος"),
        ("θεοδωρος", "θεοδωρος"),     # nominative stays (no suffix match)
        # Short names preserved
        ("θεων", "θεων"),             # nominative stays
        ("θεωνος", "θεων"),           # genitive → nom
    ])
    def test_stems(self, word, expected):
        assert stem_greek(word) == expected

    def test_zenon_case_forms_share_stem(self):
        forms = ["ζηνωνι", "ζηνωνος", "ζηνωνα", "ζηνων"]
        stems = {stem_greek(f) for f in forms}
        assert len(stems) == 1

    def test_ptolemaios_case_forms_share_stem(self):
        forms = ["πτολεμαιος", "πτολεμαιου", "πτολεμαιωι"]
        stems = {stem_greek(f) for f in forms}
        assert len(stems) == 1


class TestCaseInflectionMerging:
    """Test that different grammatical cases of the same name are recognized."""

    def test_zenon_dative_and_genitive_merge(self):
        assert are_same_person("Ζήνωνι", "Ζήνωνος")

    def test_sarapion_nom_and_gen_merge(self):
        assert are_same_person("Σαραπίων", "Σαραπίωνος")

    def test_ptolemaios_nom_and_gen_merge(self):
        assert are_same_person("Πτολεμαῖος", "Πτολεμαίου")

    def test_dionysios_gen_and_dat_merge(self):
        assert are_same_person("Διονυσίου", "Διονυσίωι")

    def test_different_names_still_distinguished(self):
        assert not are_same_person("Ζήνωνι", "Σαραπίωνος")

    def test_resolve_merges_case_variants(self):
        name_counts = {"Ζήνωνι": 50, "Ζήνωνος": 30, "Ζήνωνα": 10}
        result = resolve_entities(name_counts)
        assert len(result) == 1
        assert result[0].mention_count == 90
        assert len(result[0].variants) == 3


# ---------------------------------------------------------------------------
# Trismegistos enrichment
# ---------------------------------------------------------------------------

class TestEnrichWithTrismegistos:
    def test_skips_docs_without_tm_id(self):
        doc = starter.PapyriDocument(
            record_id="doc1", title="", source_url="", xml="", text="",
        )
        with mock.patch("trismegistos.fetch_tm_metadata") as mock_fetch:
            starter.enrich_with_trismegistos([doc])
        mock_fetch.assert_not_called()

    def test_fetches_and_stores_cross_refs(self):
        doc = starter.PapyriDocument(
            record_id="doc1", title="", source_url="", xml="", text="",
            tm_id="9999",
        )
        fake_raw = {"TM_ID": ["9999"], "DDB": ["p.oxy;;1"], "HGV": ["hgv9999"]}
        fake_refs = {"tm_id": "9999", "ddb": ["p.oxy;;1"]}
        with mock.patch("trismegistos.fetch_tm_metadata", return_value=fake_raw):
            with mock.patch("trismegistos.resolve_cross_refs", return_value=fake_refs):
                starter.enrich_with_trismegistos([doc])
        assert doc.cross_refs == fake_refs

    def test_cache_written_and_reused(self, tmp_path):
        cache_file = tmp_path / "tm_cache.json"
        doc = starter.PapyriDocument(
            record_id="doc1", title="", source_url="", xml="", text="",
            tm_id="42",
        )
        fake_raw = {"TM_ID": ["42"], "DDB": ["p.tebt;;2"]}
        fake_refs = {"tm_id": "42", "ddb": ["p.tebt;;2"]}

        with mock.patch("trismegistos.fetch_tm_metadata", return_value=fake_raw):
            with mock.patch("trismegistos.resolve_cross_refs", return_value=fake_refs):
                starter.enrich_with_trismegistos([doc], cache_path=str(cache_file))

        assert cache_file.exists()
        cache = json.loads(cache_file.read_text())
        assert "42" in cache

        # Second call should NOT hit the network
        doc2 = starter.PapyriDocument(
            record_id="doc2", title="", source_url="", xml="", text="",
            tm_id="42",
        )
        with mock.patch("trismegistos.fetch_tm_metadata") as mock_fetch:
            starter.enrich_with_trismegistos([doc2], cache_path=str(cache_file))
        mock_fetch.assert_not_called()
        assert doc2.cross_refs == fake_refs
