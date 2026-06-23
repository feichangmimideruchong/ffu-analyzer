import ingest


class TestParseMetadata:
    def test_base_document(self):
        meta = ingest.parse_metadata("09.1 AF Ekalunds Industriområde.pdf")
        assert meta["doc_kind"] == "base"
        assert meta["is_revision"] == 0
        assert meta["doc_code"] == "09.1"

    def test_revision_document(self):
        meta = ingest.parse_metadata(
            "10.1 - Ej prissatt mängdbeskrivning Mark och VA rev. 2025-05-13.pdf"
        )
        assert meta["doc_kind"] == "revision"
        assert meta["is_revision"] == 1
        assert meta["revision_label"] == "2025-05-13"
        assert meta["doc_code"] == "10.1"

    def test_amendment_kfu(self):
        meta = ingest.parse_metadata("KFU 2 Ändrings PM 2025-05-21.pdf")
        assert meta["doc_kind"] == "amendment"
        assert meta["is_revision"] == 1
        assert meta["revision_label"] and "KFU" in meta["revision_label"]

    def test_doc_number_extracted(self):
        meta = ingest.parse_metadata("Ritning M-10.2-2001 something.pdf")
        assert meta["doc_number"] == "M-10.2-2001"

    def test_no_code(self):
        meta = ingest.parse_metadata("Random file without code.pdf")
        assert meta["doc_kind"] == "base"


class TestChunkPage:
    def test_short_text_single_chunk(self):
        chunks = ingest.chunk_page("A short paragraph of text.")
        assert chunks == ["A short paragraph of text."]

    def test_empty_text(self):
        assert ingest.chunk_page("") == []

    def test_long_text_splits(self):
        para = "word " * 2000  # well over CHUNK_CHARS
        chunks = ingest.chunk_page(para)
        assert len(chunks) > 1

    def test_paragraphs_preserved(self):
        text = "First paragraph.\n\nSecond paragraph."
        chunks = ingest.chunk_page(text)
        joined = " ".join(chunks)
        assert "First paragraph." in joined
        assert "Second paragraph." in joined


class TestFirstHeading:
    def test_markdown_heading(self):
        assert ingest.first_heading("# Title\nbody") == "Title"

    def test_no_heading(self):
        assert ingest.first_heading("just body text") is None

    def test_heading_truncated(self):
        long = "## " + ("x" * 200)
        assert len(ingest.first_heading(long)) <= 120
