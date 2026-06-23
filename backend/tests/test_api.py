from conftest import insert_chunk, insert_document
from fastapi.testclient import TestClient

import main


def test_health(memdb):
    with TestClient(main.app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}


def test_documents_empty(memdb):
    with TestClient(main.app) as client:
        res = client.get("/api/documents")
        assert res.status_code == 200
        assert res.json() == {"documents": []}


def test_graph_empty(memdb):
    with TestClient(main.app) as client:
        res = client.get("/api/graph")
        assert res.json() == {"nodes": [], "edges": []}


def test_old_unprefixed_path_is_gone(memdb):
    # The API lives under /api now. The old root paths must not serve the API,
    # whether or not the static SPA is mounted (which would answer GET / POST
    # with 404 / 405 respectively).
    with TestClient(main.app) as client:
        assert client.get("/process").status_code in (404, 405)
        assert client.post("/process").status_code in (404, 405)


def test_document_detail_and_references(memdb):
    d1 = insert_document(memdb, filename="09.1 AF.pdf", doc_code="09.1", content="body")
    d2 = insert_document(memdb, filename="10.1 Mängd.pdf", doc_code="10.1")
    insert_chunk(memdb, d1, 0, 1, "Enligt handling 10.1 gäller detta.")
    memdb.commit()
    import references

    references.build_references()
    with TestClient(main.app) as client:
        res = client.get(f"/api/document/{d1}")
        assert res.status_code == 200
        assert res.json()["filename"] == "09.1 AF.pdf"

        refs = client.get(f"/api/document/{d1}/references").json()
        assert {r["document_id"] for r in refs["outgoing"]} == {d2}

        missing = client.get("/api/document/9999")
        assert missing.status_code == 404
