# src/chatbot/

The team support chatbot. Answers questions using only the rules document (via `src/ingestion/`) no connection to the grading agent at all.

## Files

**`prompts.py`** the system prompt, and it's doing more work than it looks like. Draws a hard line between three things: facts stated in the actual rules (must be quoted accurately, never embellished), general concepts explained from common knowledge (allowed, but must be clearly labeled as not an official rule), and this organization's real procedures like registration or deadlines (never guessed at, even when labeled if it's not in the rules doc, the answer is "not specified, contact the organizers"). Includes worked examples of right vs. wrong answers, since plain instructions alone weren't reliably followed in testing.

**`state.py`** defines the conversation's memory shape. One field, `messages`, using LangGraph's `add_messages` so new messages get appended to the conversation instead of replacing it this one detail is the entire mechanism behind the chatbot remembering earlier questions in the same session.

**`graph.py`** the actual chatbot logic: retrieve relevant rule sections for the latest question, send the full conversation history plus that context to the LLM, save the result under a `thread_id` so it's remembered for the rest of that session. Also caps how much of any single retrieved chunk gets used, so one oversized chunk can't blow through the LLM's rate limit by itself.

**`chatbot.py`** a thin wrapper exposing `answer_question()`, which is what everything else (the CLI, the API) actually calls. Also runnable directly for a quick manual memory test.

## One session = one conversation

Every call to `answer_question()` needs a `thread_id`. The same `thread_id` across multiple calls means the bot remembers earlier turns; a different one starts a completely fresh conversation with no memory of the first.
