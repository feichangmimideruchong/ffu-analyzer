import references
from conftest import insert_chunk, insert_document


class TestNormalizeCode:
    def test_strips_leading_zeros(self):
        assert references._normalize_code("09.1") == "9.1"
        assert references._normalize_code("13.1") == "13.1"

    def test_none(self):
        assert references._normalize_code(None) is None

    def test_non_numeric_passthrough(self):
        assert references._normalize_code("KFU") == "KFU"


class TestHandlingRegex:
    def test_anchored_words_match(self):
        text = "se handling 13.1 och enligt 10.1 samt bilaga 13.13"
        found = references.HANDLING_RE.findall(text)
        assert "13.1" in found
        assert "10.1" in found
        assert "13.13" in found

    def test_se_anchor_single_space(self):
        # Regression: the 'se' anchor used to require a double space.
        assert references.HANDLING_RE.findall("se 13.1") == ["13.1"]

    def test_se_aven(self):
        assert references.HANDLING_RE.findall("se även 10.2") == ["10.2"]

    def test_bare_number_not_matched(self):
        # No anchoring word -> no match (avoids measurements/AMA noise).
        assert references.HANDLING_RE.findall("the value 13.1 meters") == []


class TestDrawingRegex:
    def test_matches_drawing_number(self):
        assert references.DRAWING_RE.findall("ritning M-10.2-2001 visar") == ["M-10.2-2001"]


class TestBuildGraph:
    def _seed(self, conn):
        d1 = insert_document(conn, filename="09.1 AF.pdf", doc_code="09.1", doc_kind="base")
        d2 = insert_document(conn, filename="10.1 Mängd.pdf", doc_code="10.1", doc_kind="base")
        d3 = insert_document(conn, filename="13.1 Anbud.xlsx", doc_code="13.1", doc_kind="base")
        insert_chunk(conn, d1, 0, 1, "Priser anges enligt handling 10.1 och se 13.1.")
        insert_chunk(conn, d3, 0, 2, "CV bifogas enligt handling 9.1.")
        conn.commit()
        return d1, d2, d3

    def test_build_creates_expected_edges(self, memdb):
        d1, d2, d3 = self._seed(memdb)
        result = references.build_references()
        assert result["edges"] == 3
        g = references.graph()
        pairs = {(e["source"], e["target"]) for e in g["edges"]}
        assert (d1, d2) in pairs  # 09.1 -> 10.1
        assert (d1, d3) in pairs  # 09.1 -> 13.1
        assert (d3, d1) in pairs  # 13.1 -> 9.1

    def test_self_reference_skipped(self, memdb):
        d1 = insert_document(memdb, filename="09.1 AF.pdf", doc_code="09.1", doc_kind="base")
        insert_chunk(memdb, d1, 0, 1, "See handling 9.1 for details.")
        memdb.commit()
        result = references.build_references()
        assert result["edges"] == 0

    def test_document_references_directions(self, memdb):
        d1, d2, d3 = self._seed(memdb)
        references.build_references()
        refs = references.document_references(d1)
        out_targets = {r["document_id"] for r in refs["outgoing"]}
        in_sources = {r["document_id"] for r in refs["incoming"]}
        assert out_targets == {d2, d3}
        assert in_sources == {d3}

    def test_unresolved_counted(self, memdb):
        d1 = insert_document(memdb, filename="09.1 AF.pdf", doc_code="09.1", doc_kind="base")
        insert_chunk(memdb, d1, 0, 1, "Refers to handling 99.9 which does not exist.")
        memdb.commit()
        result = references.build_references()
        assert result["edges"] == 0
        assert result["unresolved"] >= 1

    def test_revision_prefers_base_target(self, memdb):
        base = insert_document(memdb, filename="10.1 base.pdf", doc_code="10.1", doc_kind="base")
        insert_document(
            memdb, filename="10.1 rev.pdf", doc_code="10.1", doc_kind="revision", is_revision=1
        )
        src = insert_document(memdb, filename="09.1 AF.pdf", doc_code="09.1", doc_kind="base")
        insert_chunk(memdb, src, 0, 1, "Enligt handling 10.1 gäller följande.")
        memdb.commit()
        references.build_references()
        g = references.graph()
        targets = {e["target"] for e in g["edges"] if e["source"] == src}
        assert targets == {base}
