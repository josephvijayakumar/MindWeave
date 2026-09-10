# MindWeave: shared instructions for coding agents

Read this file before changing the project. These rules apply to Codex, Gemini, Claude, Antigravity, and human contributors.

## Product boundary

MindWeave turns learning-group conversations into a connected, reviewable knowledge base. The immutable pipeline is:

`raw conversation → analysis → proposed change → human approval → canonical knowledge`

**Never allow an LLM, scheduler, import job, or background task to write directly to canonical knowledge.** Only the explicit approval workflow may create a knowledge item, update it, create a relationship, or append a version.

## Current stack and local commands

- Python 3.9+; FastAPI; Jinja templates; SQLite.
- Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Tests: `.venv/bin/python -m unittest discover -s tests -v`
- App: `.venv/bin/uvicorn app.main:app --reload`
- Default local URL: `http://localhost:8000`
- Use `MINDWEAVE_DB=/absolute/path/to/test.db` for isolated manual or automated test data. Do not commit databases, exports, media, API keys, or personal chat content.

## System map

| Area | Location | Contract |
| --- | --- | --- |
| WhatsApp parsing | `app/parser.py` | Return `ParsedMessage`; preserve multiline messages and mark system entries. |
| Import + web routes | `app/main.py` | Accept `.txt` or media ZIP exports; keep errors user-facing. |
| Persistence + approval | `app/db.py` | Raw source is retained. `review(..., approved=True)` is the only canonical-write path. |
| Analysis providers | `app/llm.py` | Implement `LLMProvider.propose(messages, existing_knowledge)` and return structured `ProposedChange` values only. |
| Data structures | `app/models.py` | Keep proposal kinds and source IDs explicit. |
| Dashboard | `app/templates/` + `app/static/` | Keep approval/rejection visible and deliberate. |
| CLI + Google Docs review | `app/cli.py` + `app/google_docs.py` | Same database as UI; publishing is proposal-only and OAuth credentials stay local. |

## Working rules

1. Make the smallest change that achieves the requested outcome; preserve the simple local-MVP architecture unless a change is justified in writing.
2. Add or update tests for parser, database, or provider behavior. Verify the full test suite before handoff.
3. Keep LLM provider credentials in environment variables only. Do not hard-code, log, commit, or echo secrets.
4. Treat ZIP uploads as untrusted: do not extract them to disk unless needed, do not process media by default, cap transcript size, and provide clear errors.
5. Maintain source-message IDs, confidence, contributors, timestamps, and version history when extending knowledge records.
6. Preserve compatibility with Python 3.9 unless the project explicitly raises its minimum version.
7. Before broad changes, explain the trade-offs and choose the simplest extensible route.

## Definition of done

- Relevant tests pass.
- A manual flow remains possible: import → analyze → review → approved knowledge.
- No workflow bypasses human approval.
- README and `docs/HANDOFF_GEMINI.md` reflect material architecture or run-command changes.
