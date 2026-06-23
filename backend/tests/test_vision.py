from conftest import insert_document

import vision


class TestViewPageGuards:
    """The guard branches return human-readable strings without any network call."""

    def test_document_not_found(self, memdb):
        assert vision.view_page(999, 1) == "Document not found."

    def test_missing_rel_path(self, memdb):
        doc_id = insert_document(memdb, filename="x.pdf", rel_path=None)
        memdb.commit()
        assert vision.view_page(doc_id, 1) == "Document has no file on disk."

    def test_non_pdf_rejected(self, memdb):
        doc_id = insert_document(memdb, filename="x.xlsx", rel_path="ffu/x.xlsx")
        memdb.commit()
        assert vision.view_page(doc_id, 1) == "Visual view is only available for PDF documents."

    def test_path_traversal_blocked(self, memdb):
        doc_id = insert_document(memdb, filename="x.pdf", rel_path="../../../etc/passwd.pdf")
        memdb.commit()
        assert vision.view_page(doc_id, 1) == "Invalid document path."
