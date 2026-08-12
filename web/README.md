# web/

**`index.html`**  the whole website: one file, no build step, no separate CSS/JS files. Two views (Team Portal, Judge Panel) toggled by JavaScript, both behind a real login gate that calls `src/api/main.py`'s `/login/team` and `/login/judge`. A floating chatbot widget talks to `/chat`.

Nothing here has its own logic worth documenting beyond what's already in the HTML/JS comments every place that calls the backend is a plain `fetch()` call to one of the endpoints listed in `src/api/README.md`. If something on the website isn't working, that table is the first place to check find which endpoint the broken button should be calling, and test that endpoint directly first.

Served automatically by `src/api/main.py` at its root address (`/`) this file is never opened directly in a browser during normal use, it's served by the backend.
