# Handoff: MindWeave MVP → Gemini coding agent

<handoff>
You are continuing work from Codex on MindWeave, a local AI-assisted collective-learning system.

## Goal

Build the MVP incrementally: import WhatsApp learning-group chats, generate structured proposed knowledge changes, require human approval, retain approved versioned knowledge and its source references, and display its relationships. The guiding rule is that AI may propose but may never directly modify canonical knowledge.

## Repository

`/Users/josephvijayakumarj/Projects2026/MindWeave`

This directory is **not currently a Git repository**. Create a repository only if the user authorizes it; until then, inspect current files directly and do not assume commit history exists.

## Read first

1. `docs/AGENTS.md` — shared constraints and operational commands.
2. `docs/GEMINI.md` — Gemini-specific continuation assignment.
3. `README.md` — product scope and local setup.

## Completed

- Created a FastAPI + Jinja + SQLite local MVP in `backend/`.
- Direct macOS WhatsApp integration (`backend/whatsapp_local.py`) pulling directly from native Desktop `ChatStorage.sqlite`.
- Retained file upload parser for fallback and legacy imports.
- Stored raw messages, proposal records, approved knowledge, knowledge versions, and semantic relationships in `database/mindweave.db`.
- Built executive Curation Suite (`backend/templates/dashboard.html`) with direct WhatsApp sync dropdown, one-click analysis, stats counters, and expandable message drawers.
- Built interactive Relationship Graph visualizer (`backend/templates/graph.html`) on `http://localhost:8000/graph` using Vis.js network, live search, and slide-out inspector.
- Built Next.js Q&A Portal (`portal/`) running on `http://localhost:3001` with real-time REST API consumption (`GET /api/knowledge`), StackOverflow-style Q&A cards, and expandable verbatim source WhatsApp threads.
- Milestone 10: Automatic and manual knowledge relationship inference and two-way Obsidian vault sync (`MindWeave_Vault/`) with `[[Wikilinks]]`.
- Milestone 11: Automated daily sync pipeline (`backend/cli.py daily-sync`, `scripts/daily_sync.sh`, and `backend/cli.py setup-schedule` with macOS `launchd` plist generator).
- Test suite: 100% passing tests in `tests/`.

## Current process state

- **FastAPI Backend:** Running on `http://localhost:8000` (`.venv/bin/uvicorn backend.main:app --reload --port 8000`).
  - Curation Dashboard: `http://localhost:8000`
  - Knowledge Base: `http://localhost:8000/knowledge`
  - Visualizer: `http://localhost:8000/graph`
  - API: `http://localhost:8000/api/knowledge`
- **Next.js Q&A Portal:** Running on `http://localhost:3001` (`portal/`, Next.js 16.3.4, pinned to port 3001).
- **SQLite Database:** `database/mindweave.db` (381+ raw messages, 30+ canonical items, 21+ relationships).

## Important files

| File | Purpose |
| --- | --- |
| `backend/main.py` | FastAPI routes, CORS, REST API endpoints, and dashboard flow. |
| `backend/whatsapp_local.py` | Direct macOS native WhatsApp Desktop `ChatStorage.sqlite` reader. |
| `backend/parser.py` | WhatsApp & Telegram text/export parsing. |
| `backend/db.py` | SQLite schema, graph relationships, and approval transaction—sole canonical-write path. |
| `backend/llm.py` | `LLMProvider` abstraction, HeuristicProvider, and Agy/Gemini structured proposals. |
| `backend/cli.py` | Shared CLI: direct sync, analysis, daily-sync, link-concepts, schedule setup. |
| `backend/obsidian.py` | Obsidian vault synchronization engine. |
| `backend/templates/dashboard.html` | Curation Suite with direct sync and proposal review. |
| `backend/templates/graph.html` | Interactive Vis.js Knowledge Graph visualizer. |
| `portal/src/app/page.tsx` | Next.js Q&A Portal displaying live curated knowledge cards & source discussions. |
| `scripts/daily_sync.sh` | Daily cron/launchd execution script. |
| `tests/` | Comprehensive test suite (all passing). |

## Validation commands

```bash
cd /Users/josephvijayakumarj/Projects2026/MindWeave
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/uvicorn backend.main:app --reload --port 8000
cd portal && npm run dev
```

## Non-negotiable acceptance criteria

- Raw content and source references remain intact.
- A model can create proposals only; it must not write `knowledge_items`, `knowledge_versions`, or `relationships` directly.
- Approval remains explicit and human-initiated.
- No API key, chat export, media, database, or other private information is committed.
</handoff>

