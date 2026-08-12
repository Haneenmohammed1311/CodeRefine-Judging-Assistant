"""
Builds the shared knowledge base for both the grading agent and the team chatbot.

Reads the CodeRefine rules document (markdown, with section headings), splits it
into section-based chunks, embeds each chunk with a self-hosted BGE-M3 model, and
persists the result to a local Chroma vector store.

Run this once after any edit to the rules document:
    poetry run python -m src.ingestion.build_knowledge_base
"""

import re
from pathlib import Path

import fitz  # PyMuPDF
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.documents import Document

RULES_DOC_MD_PATH = Path("data/rules.md")
RULES_DOC_PDF_PATH = Path("data/rules.pdf")
CHROMA_PERSIST_DIR = "data/chroma_db"
COLLECTION_NAME = "coderefine_rules"

EMBEDDING_MODEL_NAME = "BAAI/bge-m3"


def _clean_line(line: str) -> str:
    """Strips known layout-extraction noise from a single raw line."""
    # Bold-wrapped non-ASCII glyphs left over from font/PDF extraction, e.g. **優雅**
    line = re.sub(r"\*\*[^\x00-\x7F]+\*\*", "", line)
    # Image placeholders like ![][image1] or ![][image12]
    line = re.sub(r"!\[\]\[image\d+\]\d*", "", line)
    # Literal escaped bullet markers "\-" -> normal "-"
    line = re.sub(r"^\\-\s*$", "-", line.strip())
    # Inline escaped bullets: "\- Functionality (...)" -> "- Functionality (...)"
    line = re.sub(r"^\\-\s+", "- ", line)
    # Stray backslash-escaped punctuation from extraction (\= \+ \# etc.)
    line = re.sub(r"\\([=+#])", r"\1", line)
    return line.strip()


def _is_heading(line: str) -> bool:
    """
    Heuristic: a line is a heading if it has no lowercase letters, is short,
    and isn't a bullet marker or empty. Raw extraction gives us ALL-CAPS
    section titles (ELIGIBILITY, DURATION, LOCATION, ...) with no markdown
    heading syntax at all.
    """
    if not line or line == "-":
        return False
    if len(line) > 60:
        return False
    letters = [c for c in line if c.isalpha()]
    if not letters:
        return False
    return all(c.isupper() for c in letters)


def _is_junk_line(line: str) -> bool:
    """
    Catches lines that are pure extraction noise with no textual meaning at
    all -- specifically, markdown image-reference definitions like
    "[image1]: <data:image/png;base64,iVBOR...>". These are raw image
    pixel data stored as base64 text (a leftover from the original PDF's
    embedded images/logos). They carry zero information for a text-based
    knowledge base, and one of them alone can be thousands of characters --
    this was the actual cause of one chunk coming out ~20x larger than
    every other section.
    """
    return bool(re.match(r"^\[image\d+\]:\s*<data:", line))


def split_by_section(raw_text: str) -> list[Document]:
    """
    Parses the raw (messily-extracted) rules text into section-based chunks.
    Consecutive heading-like lines are merged into one heading (the source
    document has running-header artifacts, e.g. a page title followed
    immediately by the real section heading). Bullet lines are reassembled
    with their content, since the source splits "\\-" markers onto their
    own line from the sentence that follows.
    """
    lines = [_clean_line(l) for l in raw_text.split("\n")]
    lines = [l for l in lines if l != "" and not _is_junk_line(l)]

    sections: list[tuple[str, list[str]]] = []
    current_heading = "Introduction"
    current_body: list[str] = []
    pending_bullet = False

    for line in lines:
        if _is_heading(line):
            # Merge into the previous heading if we haven't collected any
            # body content yet (handles adjacent running-header artifacts)
            if not current_body and sections == [] and current_heading == "Introduction":
                current_heading = line
            elif not current_body:
                current_heading = f"{current_heading} - {line}"
            else:
                sections.append((current_heading, current_body))
                current_heading = line
                current_body = []
            pending_bullet = False
            continue

        if line == "-":
            pending_bullet = True
            continue

        if pending_bullet:
            current_body.append(f"- {line}")
            pending_bullet = False
        else:
            current_body.append(line)

    if current_body:
        sections.append((current_heading, current_body))

    documents = []
    for heading, body_lines in sections:
        content = f"{heading}\n" + "\n".join(body_lines)
        documents.append(Document(page_content=content, metadata={"section": heading}))
    return documents


def extract_text_from_pdf(pdf_path: Path) -> str:
    """
    Uses PyMuPDF (fitz) -- fast and reliable for text-based PDFs like a
    rules document (not scanned images, which would need OCR instead).
    """
    doc = fitz.open(pdf_path)
    full_text = "\n".join(page.get_text("text") for page in doc)
    doc.close()
    return full_text


def build_vector_store() -> Chroma:
    if RULES_DOC_PDF_PATH.exists():
        print(f"Found {RULES_DOC_PDF_PATH}, extracting text with PyMuPDF...")
        raw_text = extract_text_from_pdf(RULES_DOC_PDF_PATH)
    elif RULES_DOC_MD_PATH.exists():
        raw_text = RULES_DOC_MD_PATH.read_text(encoding="utf-8")
    else:
        raise FileNotFoundError(
            f"Expected a rules document at {RULES_DOC_PDF_PATH} or "
            f"{RULES_DOC_MD_PATH}. Place one of these there first."
        )

    documents = split_by_section(raw_text)

    print(f"Split rules document into {len(documents)} section-based chunks.")
    for doc in documents:
        print(f"  - {doc.metadata['section']} ({len(doc.page_content)} chars)")

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    vector_store = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PERSIST_DIR,
    )

    print(f"\nVector store built and persisted to {CHROMA_PERSIST_DIR}/")
    return vector_store


if __name__ == "__main__":
    build_vector_store()
