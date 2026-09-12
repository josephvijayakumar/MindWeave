---
name: mindweave-stack
description: >-
  Use this skill when developing, debugging, or modifying the core architecture of MindWeave. 
  It explains the explicit separation of concerns between the Python Backend Engine and the Node.js Next.js Portal.
---

# MindWeave Architecture & Stack Guidelines

MindWeave is strictly divided into two decoupled parts. As an AI Agent working on this codebase, you must respect this boundary and never mix their responsibilities.

## Part 1: The Python Engine (Data Ingestion & Curation)
**Location:** Root directory (`app/`, `mindweave.db`)
**Tech Stack:** Python 3.9+, FastAPI, SQLite, LLM APIs (Gemini/AgyProvider).

**Responsibilities:**
1. **Data Ingestion:** Connecting to local WhatsApp SQLite databases (`app/whatsapp_local.py`) or parsing exported ZIP files.
2. **AI Processing:** Batching messages and sending them to LLMs to extract granular, atomic "knowledge concepts".
3. **Curation Dashboard:** A simple FastAPI + Jinja HTML dashboard (`app/templates/`) used strictly by the admin to Approve/Reject AI proposals.
4. **Data Storage:** Writing approved knowledge to `mindweave.db`.

**Rules for Part 1:**
- Do not add complex frontend logic (React/JS) here.
- The Python engine runs locally on the user's machine to safely handle private WhatsApp data.

## Part 2: The Node.js Portal (StackOverflow-style Q&A)
**Location:** `portal/` directory
**Tech Stack:** Node.js, Next.js (React), Vanilla CSS (No Tailwind unless explicitly requested).

**Responsibilities:**
1. **Public/UAT Display:** This is the rich, modern UI that end-users will interact with.
2. **Read-Only:** It reads the approved, curated knowledge from `mindweave.db` (or a REST API exposed by Part 1).
3. **Visualizations:** Renders Knowledge Graphs, relationships, and Q&A feeds.

**Rules for Part 2:**
- Use Vanilla CSS in `globals.css` for styling. Focus on glassmorphic, premium, modern dark-mode designs.
- Never write data directly to the canonical knowledge base from the Next.js app. All knowledge generation must pass through the Python Engine's human-approval queue.
- If migrating to production, `mindweave.db` can be shipped with this Next.js app, or the data can be migrated to Firebase NoSQL.

## Handoff & Synchronization
If you make architectural decisions, you must update `docs/ProjectSourceKnowledgeHub.md`, which acts as the ultimate product specification for MindWeave.
