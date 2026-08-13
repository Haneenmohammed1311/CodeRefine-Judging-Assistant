# Packages the whole backend (grading agent, chatbot, API) into one
# portable container runs identically on any Docker-capable server,
# regardless of what's already installed there.

FROM python:3.11-slim

WORKDIR /app

# Install Poetry itself first (this layer is cached only re-runs if
# the Python base image changes, not on every code edit)
RUN pip install --no-cache-dir poetry==1.8.3

# Copy only dependency files first, so Docker can cache the slow
# "install everything" step separately from your actual code editing
# a .py file won't force re-downloading every dependency again.
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Now copy the actual project code
COPY . .

# The knowledge base needs to exist before the API can answer chatbot
# not on every container start
RUN poetry run python -m src.ingestion.build_knowledge_base || true

ENV PORT=7860
EXPOSE $PORT

CMD ["sh", "-c", "poetry run uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT}"]
