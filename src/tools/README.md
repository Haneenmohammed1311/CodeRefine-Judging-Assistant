# src/tools/

Everything the grading agent uses to actually read a team's submission. Nothing in here decides scores it only fetches and parses raw content.

## Files

**`github_tool.py`** all GitHub access, read-only:
- `find_submission_files()` locates the README, Deep Dives file, BOTE file, and `.excalidraw` file in a repo, matching by filename pattern since naming varies a lot between teams (confirmed against several real submissions). Also flags image files, PDFs, and external diagram links (draw.io, Figma, Miro, etc.) that it can't read directly, so nothing goes silently unnoticed.
- `fetch_repo_file_tree()` walks the whole repo, skipping noisy folders like `node_modules` and `.git`.
- `fetch_readme()`, `fetch_file_content()` read one specific file's content.
- `find_external_resource_links()` scans README text for a link to an external diagramming tool, used when no `.excalidraw` file was committed.

**`excalidraw_parser.py`** turns a raw `.excalidraw` file (which is JSON, not an image) into plain text: what shapes exist, what they're labeled, and which ones connect to which. This is what lets the agent "read" an architecture diagram without needing a vision model.

## Nothing here calls the LLM

This whole folder is plain data-fetching and parsing the actual reasoning happens in `src/agent/nodes.py`, which imports from here.
