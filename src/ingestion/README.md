# src/ingestion/

Builds and queries the knowledge base the chatbot answers questions from. Has nothing to do with grading this is entirely for the team-support side.

## Files

**`build_knowledge_base.py`** run this once, and again any time the rules document changes:
- Accepts either `data/rules.pdf` (extracted with PyMuPDF) or `data/rules.md`, whichever exists
- Cleans the raw text (strips layout noise from the original PDF export — garbled characters, image placeholders)
- Splits it into one chunk per rule section
- Embeds each chunk with a self-hosted BGE-M3 model (no API key needed for this step, on purpose keeps this piece dependency-free)
- Saves everything into a local Chroma vector database at `data/chroma_db/`

**`retriever.py`** `load_retriever()` reconnects to that saved database so other code (the chatbot) can search it. Also runnable directly as a quick manual test — searches one hardcoded question and prints what comes back.

## Run order

`build_knowledge_base.py` has to run at least once before `retriever.py` (or the chatbot) will find anything it's what actually creates the database the other files read from.
