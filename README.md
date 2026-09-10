# MindWeave MVP

Where conversations become collective knowledge.

For continuation by Codex, Gemini, Claude, or another coding agent, start with [`AGENTS.md`](AGENTS.md). The current Gemini handoff is in [`docs/HANDOFF_GEMINI.md`](docs/HANDOFF_GEMINI.md).

This is a local, human-in-the-loop MVP. It imports WhatsApp exported chats, stores the original messages, creates **proposals** from learning-oriented discussions, and updates canonical knowledge only after a person approves a proposal.

## Why this shape?

- **FastAPI + server-rendered templates**: one Python process and no frontend build pipeline for a local MVP.
- **SQLite**: zero setup now; the repositories isolate persistence so PostgreSQL can replace it later.
- **Provider interface**: analysis is behind `LLMProvider`; the included heuristic provider makes the complete flow runnable without an API key. Add Gemini or Claude in that module without touching parsing, review, or knowledge storage.
- **Immutable raw messages and revision rows**: approved knowledge points back to its message sources and every change is versioned.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. Upload a WhatsApp `.txt` export or the `.zip` export WhatsApp creates when media is included, then choose **Analyze unprocessed messages**. The included sample is at `samples/whatsapp-learning-chat.txt`.

## WhatsApp export support

The parser accepts the common Android and iOS text export layouts, including multi-line messages. For ZIP exports, MindWeave imports the largest `.txt` transcript and ignores media files. System and media-placeholder messages are retained as raw source material but excluded from analysis.

## MVP boundaries

- The heuristic provider is intentionally conservative and offline. It detects messages that contain learning signals (questions, explanations, examples, definitions) and creates proposals. It is a test double, not a substitute for an LLM.
- Daily scheduling is left to a local cron/Task Scheduler command for now: `uvicorn` hosting plus a future CLI job. This prevents a background worker from silently changing state; it may create proposals only.
- Knowledge is structured in SQLite. Markdown export and a graph visualizer are natural next steps once the review workflow is validated.

## Tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## CLI + UI workflow

The CLI and web UI use the same SQLite database, so either interface can be used at each step. Both preserve the human approval boundary.

```bash
# Import and create proposals (offline heuristic provider for now)
.venv/bin/python -m app.cli import "WhatsApp Chat - Learning.zip"
.venv/bin/python -m app.cli analyze

# Create a local review artifact, or publish the same proposals to Google Docs
.venv/bin/python -m app.cli export-review --output mindweave-review.md
.venv/bin/pip install -r requirements-google.txt
.venv/bin/python -m app.cli publish-google-doc --client-secrets /safe/path/google-oauth-client.json

# After human review, approve deliberately in either interface
.venv/bin/python -m app.cli approve 12 --note "Reviewed in Google Docs"
.venv/bin/python -m app.cli approve-all --confirm
```

`publish-google-doc` opens a one-time Google OAuth consent flow, then creates a Doc containing pending proposals. The generated document is a review surface, not an approval API: approving canonical knowledge still requires the UI or an explicit CLI approval command. Store OAuth client files and generated tokens outside the repository.
