import json

import pymupdf

from src.tools import diagram_reader


class _Response:
    content = json.dumps({"observations": ["API connects to PostgreSQL."], "limitations": []})


class _VisionLlm:
    def invoke(self, _messages):
        return _Response()


def test_excalidraw_uses_existing_parser(monkeypatch):
    monkeypatch.setattr(diagram_reader, "parse_excalidraw", lambda _raw: "Diagram shapes/components found:\n- API")

    evidence = diagram_reader.analyze_diagram_file("architecture.excalidraw", b'{"elements": []}')

    assert evidence[0]["source_type"] == "excalidraw"
    assert "API" in evidence[0]["observation"]


def test_raster_image_returns_vision_evidence(monkeypatch):
    monkeypatch.setattr(diagram_reader, "get_vision_llm", lambda **_kwargs: _VisionLlm())

    evidence = diagram_reader.analyze_diagram_file("architecture.png", b"small-image")

    assert evidence == [{
        "file_path": "architecture.png",
        "line_range": "N/A",
        "excerpt": "API connects to PostgreSQL.",
        "observation": "API connects to PostgreSQL.",
        "source_type": "image",
    }]


def test_pdf_pages_are_rendered_then_analysed(monkeypatch):
    calls = []

    def fake_analyze(file_path, content, mime_type, source_type):
        calls.append((file_path, mime_type, source_type, content))
        return [{"file_path": file_path, "line_range": "N/A", "excerpt": "diagram", "observation": "diagram", "source_type": source_type}]

    monkeypatch.setattr(diagram_reader, "_analyze_image", fake_analyze)
    document = pymupdf.open()
    document.new_page()
    document.new_page()
    pdf_bytes = document.tobytes()
    document.close()

    evidence = diagram_reader.analyze_diagram_file("architecture.pdf", pdf_bytes)

    assert len(evidence) == 2
    assert [call[0] for call in calls] == ["architecture.pdf (page 1)", "architecture.pdf (page 2)"]
    assert all(call[2] == "pdf" for call in calls)
