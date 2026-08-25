# src/tools/

Everything the grading agent uses to actually read a team's submission. Nothing in here decides scores it only fetches and parses raw content.

## Files

**`github_tool.py`** all GitHub access, read-only:
- `find_submission_files()` locates the README, Deep Dives file, BOTE file, and `.excalidraw` file in a repo, matching by filename pattern since naming varies a lot between teams (confirmed against several real submissions). Also flags image files, PDFs, and external diagram links (draw.io, Figma, Miro, etc.) that it can't read directly, so nothing goes silently unnoticed.
- `fetch_repo_file_tree()` walks the whole repo, skipping noisy folders like `node_modules` and `.git`.
- `fetch_readme()`, `fetch_file_content()` read one specific text file; `fetch_file_bytes()` returns original bytes for committed diagrams and PDFs.
- `find_external_resource_links()` scans README text for a link to an external diagramming tool, used when no `.excalidraw` file was committed.

**`excalidraw_parser.py`** turns a raw `.excalidraw` file (which is JSON, not an image) into plain text: what shapes exist, what they're labeled, and which ones connect to which. This is what lets the agent "read" an architecture diagram without needing a vision model.

**`diagram_reader.py`** adds factual evidence from committed diagrams without scoring them. It preserves the Excalidraw parser for `.excalidraw` files, sends committed PNG/JPG/WebP files to the separate Groq vision model, and renders the first five PDF pages with PyMuPDF before analysing them. SVG files and live external links remain manual judge-review material.

`diagram_reader.py` is the only tool-layer module that calls a model, and it uses the vision model strictly for factual visual observations. Scoring and grading decisions remain in `src/agent/nodes.py`.
