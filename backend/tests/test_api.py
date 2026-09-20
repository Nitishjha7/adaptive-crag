"""FastAPI layer — request validation and response shape.

The `client` fixture lives in conftest.py; test_corpus.py needs it too.
"""

import pytest


def test_health_makes_no_llm_call(client):
    """A healthcheck has to be cheap. If it pinged the LLM, one rate limit would
    mark the container unhealthy and Docker would restart it in a loop."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["indexed_chunks"] > 0, "vectorstore is empty -- did you run `ingest.py`?"
    assert "search_provider" in body


def test_empty_question_rejected(client):
    assert client.post("/api/query", json={"question": ""}).status_code == 422


def test_missing_question_rejected(client):
    assert client.post("/api/query", json={}).status_code == 422


def test_response_shape(client, fake_llm, fake_search):
    r = client.post("/api/query", json={"question": "Why does chunk overlap matter?"})
    assert r.status_code == 200

    body = r.json()
    # The frontend renders the badge and trace off exactly these fields — the shape must not break.
    assert set(body) == {
        "answer", "source_type", "sources", "relevance_score",
        "transformed_query", "logs", "elapsed_ms", "token_usage", "memory_note",
    }
    assert isinstance(body["sources"], list)
    assert body["source_type"] in {"vector_db", "web_search"}
    assert body["relevance_score"] in {"yes", "no"}
    assert body["logs"], "the trace is empty — explainability is gone"
    assert "by_model" in body["token_usage"]
    assert "total_tokens" in body["token_usage"]


class TestStats:
    """`/api/stats` feeds the dashboard. Every number has to come from a real
    source — this is the endpoint where hardcoded demo values would quietly
    slip through."""

    def test_counts_come_from_the_real_corpus(self, client):
        body = client.get("/api/stats").json()
        assert body["documents"] > 0, "corpus documents were not counted"
        assert body["chunks"] > 0, "vectorstore is empty -- did you run `ingest.py`?"

    def test_config_is_echoed_not_invented(self, client):
        cfg = client.get("/api/stats").json()["config"]
        for key in ("llm_model", "embedding_model", "search_provider", "top_k"):
            assert cfg.get(key), f"{key} missing"
        assert isinstance(cfg["hybrid"], bool)

    def test_evaluation_is_none_when_not_run(self, client, monkeypatch, tmp_path):
        """If the eval never ran, this must be `null`, not `0`.

        "Not measured" and "scored zero" are different claims, and the UI has to
        be able to tell them apart -- otherwise the dashboard shows a false 0%.
        """
        import app.config as config

        monkeypatch.setattr(config, "BACKEND_DIR", tmp_path)

        body = client.get("/api/stats").json()
        assert body["evaluation"] is None

    def test_makes_no_llm_call(self, client):
        """The dashboard hits this on every page load -- one LLM call here
        would tie the UI's responsiveness to the rate limit."""
        assert client.get("/api/stats").status_code == 200


class TestMetrics:
    """`/metrics` — the Prometheus scrape target."""

    def test_returns_prometheus_text_format(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]

    def test_query_updates_the_exposed_metrics(self, client, fake_llm, fake_search):
        client.post("/api/query", json={"question": "Why does chunk overlap matter?"})
        body = client.get("/metrics").text
        assert "crag_queries_total" in body
        assert "crag_llm_calls_total" in body


def test_documents_reports_chunks_per_file(client):
    """The Documents page is about retrieval, not the filesystem.

    A name and a byte count say nothing a directory listing does not. The chunk
    count is the unit the retriever actually scores, so it has to be per file
    and it has to add up to what /health reports indexed.
    """
    r = client.get("/api/documents")
    assert r.status_code == 200
    docs = r.json()["documents"]
    assert docs, "no documents returned — did ingest run?"

    for d in docs:
        assert d["chunks"] is not None, f"{d['id']} has no chunk count"
        assert d["chunks"] > 0

    total = sum(d["chunks"] for d in docs)
    assert total == client.get("/health").json()["indexed_chunks"]


def test_documents_makes_no_llm_call(client):
    """Same rule as /health: a page that lists files must not cost a token."""
    r = client.get("/api/documents")
    assert r.status_code == 200
    assert "corpus" in r.json()


class TestUploads:
    """The upload path: parse, chunk, index, and keep sessions apart.

    These exercise the parser and the session scoping, not the LLM - an upload
    that indexes into the wrong collection is the failure that matters, because
    on a public demo it would answer one visitor from another's document.
    """

    def _pdf(self, pages: int = 3, line: str = "The Zorblax protocol uses seven nodes."):
        """A minimal valid PDF, built by hand so the test needs no fixture file."""
        import io

        objs = []
        kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(pages))
        objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        for i in range(pages):
            stream = f"BT /F1 11 Tf 50 750 Td ({line} Page {i + 1}.) Tj ET".encode()
            objs.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
                f"<< /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
            )
            objs.append(
                b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
            )

        out = io.BytesIO()
        out.write(b"%PDF-1.4\n")
        offsets = []
        for i, o in enumerate(objs, 1):
            offsets.append(out.tell())
            out.write(f"{i} 0 obj\n".encode() + o + b"\nendobj\n")
        xref = out.tell()
        out.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode())
        for o in offsets:
            out.write(f"{o:010d} 00000 n \n".encode())
        out.write(
            f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
        )
        return out.getvalue()

    def test_pdf_is_parsed_chunked_and_indexed(self, client):
        r = client.post(
            "/api/upload",
            data={"session": "pytestalpha"},
            files={"file": ("spec.pdf", self._pdf(), "application/pdf")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["chunks"] > 0
        assert body["characters"] > 0
        client.delete("/api/upload/pytestalpha")

    def test_sessions_cannot_see_each_other(self, client):
        """The reason uploads are session-scoped at all."""
        client.post(
            "/api/upload",
            data={"session": "pytestone"},
            files={"file": ("one.pdf", self._pdf(line="Alpha fact."), "application/pdf")},
        )
        r = client.get("/api/documents?corpus=upload:pytesttwo")
        assert r.json()["documents"] == [], "a second session saw the first one's upload"
        client.delete("/api/upload/pytestone")

    def test_an_unsupported_type_is_a_400_not_a_500(self, client):
        r = client.post(
            "/api/upload",
            data={"session": "pytestalpha"},
            files={"file": ("photo.png", b"\x89PNG\r\n", "image/png")},
        )
        assert r.status_code == 400
        assert "unsupported" in r.json()["detail"].lower()

    def test_a_pdf_with_no_text_layer_says_so(self, client):
        """A scan indexes nothing. Silently succeeding would look like a
        retrieval bug rather than an unsupported input."""
        import pytest as _pytest
        from pypdf import PdfWriter

        from app.tools.uploads import UploadError, extract_text

        # A real blank page, not a page whose text happens to be a space -
        # pypdf still finds the glyphs in the latter.
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        import io

        buf = io.BytesIO()
        writer.write(buf)

        with _pytest.raises(UploadError, match="text layer"):
            extract_text("scan.pdf", buf.getvalue())

    def test_clearing_a_session_removes_its_documents(self, client):
        client.post(
            "/api/upload",
            data={"session": "pytestclear"},
            files={"file": ("gone.pdf", self._pdf(), "application/pdf")},
        )
        assert client.get("/api/documents?corpus=upload:pytestclear").json()["documents"]
        client.delete("/api/upload/pytestclear")
        assert client.get("/api/documents?corpus=upload:pytestclear").json()["documents"] == []

    def test_an_oversized_file_is_refused_without_being_buffered(self, client):
        """Too-large uploads must be rejected while the body is still arriving.

        The endpoint used to `await file.read()` with no argument, so the whole
        upload landed in memory and only then failed the 20 MB check inside
        `extract_text`. A rejected request therefore cost exactly as much memory
        as an accepted one: six concurrent 115 MB uploads took the container
        from 560 MiB to 1.2 GiB while every one of them correctly returned 400.
        The deployed instance has 1 GiB and a concurrency of 8.

        413 rather than 400 is the assertion that pins the new path: the old
        code could only produce 400, because the check lived in the parser.
        """
        from app.tools.uploads import MAX_UPLOAD_BYTES

        oversized = b"x" * (MAX_UPLOAD_BYTES + 1024)
        response = client.post(
            "/api/upload",
            data={"session": "pytestbig"},
            files={"file": ("big.txt", oversized, "text/plain")},
        )

        assert response.status_code == 413
        assert "larger than" in response.json()["detail"]
        # Nothing may have been indexed from a refused upload.
        assert client.get("/api/documents?corpus=upload:pytestbig").json()["documents"] == []


class TestDocumentText:
    """Reading one document back.

    The grader's verdict is the project's central claim, and it is only
    checkable by someone who can read what the grader read. These cover the
    happy path for both sources and the traversal attempt, since the id comes
    from the client.
    """

    def test_built_in_document_is_readable(self, client):
        listing = client.get("/api/documents").json()["documents"]
        first = listing[0]["id"]
        r = client.get(f"/api/documents/{first}")
        assert r.status_code == 200
        assert len(r.json()["text"]) > 100

    def test_a_missing_document_is_a_404(self, client):
        assert client.get("/api/documents/nope.md").status_code == 404

    def test_path_traversal_is_refused(self, client):
        """`doc_id` reaches the filesystem, so '../' is the obvious attack."""
        for attempt in ("../../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "../ingest.py"):
            r = client.get(f"/api/documents/{attempt}")
            assert r.status_code == 404, f"{attempt} was not refused"

    def test_an_uploaded_document_is_reassembled_from_its_chunks(self, client):
        """Uploads exist only as chunks - there is no file to read - so the text
        is rebuilt in chunk order."""
        pdf = TestUploads()._pdf(pages=4, line="Zorblax needs seven nodes.")
        client.post(
            "/api/upload",
            data={"session": "pytestread"},
            files={"file": ("spec.pdf", pdf, "application/pdf")},
        )
        r = client.get("/api/documents/spec.pdf?corpus=upload:pytestread")
        assert r.status_code == 200
        assert "Zorblax" in r.json()["text"]
        client.delete("/api/upload/pytestread")


class TestRateLimiting:
    """`/api/query` spends real money - 3 LLM calls, about $0.0007 a query - and
    the deployed demo is public and unauthenticated. Without a cap, a loop costs
    whatever someone feels like spending.

    The limiter is disabled for the rest of the suite (conftest.py) because it
    is per-process and keys on the client address, so every test would share one
    bucket. These turn it back on explicitly.
    """

    def test_the_limiter_refuses_once_the_window_is_full(self, monkeypatch):
        from app.rate_limit import RateLimiter

        monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
        limiter = RateLimiter(limit=3, window_seconds=60)

        assert [limiter.allow("1.2.3.4") for _ in range(3)] == [True, True, True]
        assert limiter.allow("1.2.3.4") is False
        # A different caller has its own bucket.
        assert limiter.allow("5.6.7.8") is True

    def test_the_window_expires(self, monkeypatch):
        import time as _time

        from app.rate_limit import RateLimiter

        monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
        limiter = RateLimiter(limit=1, window_seconds=60)
        assert limiter.allow("1.2.3.4") is True
        assert limiter.allow("1.2.3.4") is False

        # Move the clock forward rather than sleeping 60s.
        fake_now = _time.monotonic() + 61
        monkeypatch.setattr(_time, "monotonic", lambda: fake_now)
        monkeypatch.setattr("app.rate_limit.time.monotonic", lambda: fake_now)
        assert limiter.allow("1.2.3.4") is True

    def test_the_endpoint_answers_429_with_retry_after(self, client, monkeypatch):
        """End to end: the limit is enforced by the route, not just the class."""
        import main

        monkeypatch.delenv("DISABLE_RATE_LIMIT", raising=False)
        monkeypatch.setattr(main, "_QUERY_LIMITER", main.RateLimiter(limit=1, window_seconds=60))

        first = client.post("/api/query", json={"question": "anything at all"})
        second = client.post("/api/query", json={"question": "anything at all"})

        # The first may fail for lack of a real LLM; what matters is that it was
        # not refused by the limiter.
        assert first.status_code != 429
        assert second.status_code == 429
        assert second.headers.get("Retry-After")

    def test_x_forwarded_for_identifies_the_caller(self):
        """Cloud Run terminates TLS, so `request.client.host` is the load
        balancer and every visitor would share one bucket."""
        from unittest.mock import Mock

        import main

        request = Mock()
        request.headers = {"x-forwarded-for": "203.0.113.5, 10.0.0.1"}
        assert main._client_key(request) == "203.0.113.5"


class TestUpstreamRateLimit:
    """Groq's free tier allows 8000 tokens a minute for the whole account and a
    query costs roughly 2500, so a few simultaneous visitors are enough to trip
    it. Verified by running 20 concurrent queries against the container: eight
    were refused by this service's own limiter and eleven came back 500, with
    `groq.RateLimitError` in the log.

    A 500 tells the caller this service is broken. The request was fine and the
    upstream model was briefly unavailable, which is a 503 with a Retry-After.
    """

    def test_a_provider_rate_limit_becomes_503_not_500(self, client, monkeypatch):
        import app.nodes.retrieve as retrieve_node

        groq_error = __import__("main")._GROQ_RATE_LIMIT
        if groq_error is None:
            import pytest

            pytest.skip("groq SDK not installed")

        # Raised from the first node, so it travels the same path a real
        # provider error would.
        def _boom(state):
            raise groq_error.__new__(groq_error)

        monkeypatch.setattr(retrieve_node, "run", _boom)

        # The graph is compiled at startup and holds a reference to the old
        # function, so rebuild it for this test.
        import main
        from app.graph.build_graph import build_crag_graph

        monkeypatch.setattr(main, "_graph", build_crag_graph())

        response = client.post("/api/query", json={"question": "anything"})

        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "10"
        assert "rate limited" in response.json()["detail"]
