# Handoff: MindWeave MVP → Gemini coding agent

<handoff>
You are continuing work from Codex on MindWeave, a local AI-assisted collective-learning system.

## Goal

Build the MVP incrementally: import WhatsApp learning-group chats, generate structured proposed knowledge changes, require human approval, retain approved versioned knowledge and its source references, and display its relationships. The guiding rule is that AI may propose but may never directly modify canonical knowledge.

## Repository

`/Users/josephvijayakumarj/Projects2026/MindWeave`

This directory is **not currently a Git repository**. Create a repository only if the user authorizes it; until then, inspect current files directly and do not assume commit history exists.

## Read first

1. `AGENTS.md` — shared constraints and operational commands.
2. `GEMINI.md` — Gemini-specific continuation assignment.
3. `README.md` — product scope and local setup.

## Completed

- Created a FastAPI + Jinja + SQLite local MVP.
- Added WhatsApp text parsing for common Android and iOS formats, multiline messages, timestamp seconds, AM/PM, bracketed lines, and direction-marker characters.
- Added import support for `.txt` and WhatsApp media ZIP exports. ZIP handling selects the largest embedded `.txt` transcript and ignores media.
- Stored raw messages, proposal records, approved knowledge, knowledge versions, and `related_to` relationships in SQLite.
- Created a dashboard that imports chats, analyzes unprocessed messages, approves/rejects individual proposals, and approves all pending proposals.
- Created a knowledge page for approved items and relationships.
- Added an offline heuristic provider so the full workflow is usable without an API key.
- Added a shared CLI (`app/cli.py`) for import, analysis, local Markdown review export, explicit approval, and guarded bulk approval. It uses the same SQLite database as the UI.
- Added an optional OAuth-backed Google Docs publisher (`app/google_docs.py`). It creates a review document only; it cannot approve or modify canonical knowledge.
- Added parser, ZIP-import, and CLI tests. Current result: **7 tests pass**.

## Current process state

- A local Uvicorn server was started at `http://127.0.0.1:8000` / `http://localhost:8000`.
- At handoff time it was PID `38964`; re-check rather than relying on that PID. If needed: `.venv/bin/uvicorn app.main:app --reload`.
- Dependencies are installed in the local `.venv`; `mindweave.db` is generated locally and ignored.

## Important files

| File | Purpose |
| --- | --- |
| `app/main.py` | FastAPI routes; ZIP/text import and dashboard flow. |
| `app/parser.py` | WhatsApp parsing. |
| `app/db.py` | SQLite schema and approval transaction—the sole canonical-write path. |
| `app/llm.py` | `LLMProvider` abstraction plus offline heuristic implementation. |
| `app/cli.py` | Shared command-line workflow: import, analyze, review export/publish, explicit approval. |
| `app/google_docs.py` | Optional Google OAuth + Docs publisher. |
| `app/models.py` | Shared message/proposal data structures. |
| `app/templates/dashboard.html` | Approval dashboard. |
| `app/templates/knowledge.html` | Approved knowledge and relationship view. |
| `tests/` | Parser and ZIP-import coverage. |

## Known limitations and risks

- `HeuristicProvider` is a demo/test implementation, not real semantic analysis.
- ZIP selection uses the largest `.txt` file. This is appropriate for normal WhatsApp exports but could be improved by ranking parsable-message counts if real exports reveal ambiguity.
- Duplicate imports are not deduplicated across separate import batches because uniqueness is scoped to an import ID.
- Relationship generation currently creates only `related_to`, only after both related knowledge items are approved.
- The UI has no proposal editing workflow yet despite accepting an optional review note.
- No daily job exists; a future job must only create proposals, never approval or canonical updates.
- Google Docs publishing needs a user-created OAuth desktop-client JSON and the optional packages in `requirements-google.txt`. No OAuth credentials are present in this workspace.

## Recommended next task: Gemini provider

Implement a real Gemini provider behind `LLMProvider` while keeping the heuristic provider as the offline default.

1. Consult the current official Gemini Python SDK documentation before selecting its SDK/API syntax.
2. Add configuration to select `heuristic` (default) or `gemini` via environment variable; use `GEMINI_API_KEY` only at runtime.
3. Give the provider clearly scoped, minimal message batches plus existing knowledge summaries. Require JSON structured to the `ProposedChange` schema.
4. Strictly validate JSON: allow only proposal kinds `CREATE`, `UPDATE`, `CONTRADICTION`, and `QUESTION`; constrain confidence to 0–1; ensure source IDs are a subset of the supplied messages.
5. On provider failure or invalid output, do not mark messages analyzed and do not create proposals. Show a dashboard error.
6. Write mock-based tests for valid output, malformed output, source-ID validation, and provider failure. No live Gemini calls in tests.
7. Run `.venv/bin/python -m unittest discover -s tests -v`.

## Later roadmap, in priority order

1. Proposal edit UI and a human-readable source-message preview; keep the CLI review export in sync.
2. Add Google Docs review-status synchronization only if it remains explicitly human-triggered and preserves an audit trail.
3. Cross-import deduplication and import metadata.
4. Relationship types beyond `related_to`, generated as reviewable changes.
5. Batch/date-range processing and a scheduler that only proposes.
6. Markdown knowledge export and a relationship graph visualization.
7. Additional connectors (Telegram, Slack, meeting transcripts, documents).

## Validation commands

```bash
cd /Users/josephvijayakumarj/Projects2026/MindWeave
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/uvicorn app.main:app --reload
```

## Non-negotiable acceptance criteria

- Raw content and source references remain intact.
- A model can create proposals only; it must not write `knowledge_items`, `knowledge_versions`, or `relationships` directly.
- Approval remains explicit and human-initiated.
- No API key, chat export, media, database, or other private information is committed.
</handoff>
