# MindWeave - Project Specification

## Vision
MindWeave is an AI-powered collective learning system that converts conversations from a private learning group into a continuously evolving, connected knowledge base.

**Tagline:** Where conversations become collective knowledge.

## Core Use Case
A group of friends uses a WhatsApp group to learn and discuss different topics. The system ingests these conversations, ignores the noise, extracts concepts and insights, and outputs proposed changes to a permanent knowledge base. A human reviews these proposals before they become canonical.

## MVP Development Goals
1. ✅ **Import a WhatsApp/Telegram exported chat file.** (Now natively integrated with local macOS WhatsApp DB!)
2. ✅ **Parse the messages.**
3. ✅ **Store them in a Database.** (SQLite)
4. ✅ **Send relevant batches to an LLM.** (via AgyProvider / Gemini)
5. ✅ **Generate structured proposed knowledge updates.** (Atomic concepts extracted)
6. ✅ **Compare them with existing knowledge.**
7. ✅ **Display the proposed changes in a simple web UI.** (FastAPI Dashboard)
8. ✅ **Allow human approval/rejection.**
9. ✅ **Store approved knowledge.** (Synced to Obsidian Vault and SQLite)
10. ✅ **Show relationships between knowledge items.** (Interactive Graph UI at `/graph`, slide-out node inspector, domain filters, live search, semantic link discovery, manual relationship creation, and Obsidian wikilink sync)
11. ✅ **Automated Daily Ingestion.** (Automated `daily-sync` CLI command, `scripts/daily_sync.sh` runner, macOS `launchd` service installer via `setup-schedule`, and crontab scheduling)

## Important Design Principle
**The AI must NOT directly modify the permanent knowledge base.** 
All changes must go through the human approval queue.

---

## Future Vision & Roadmap

### 1. ✅ StackOverflow-Style Q&A Knowledge Portal (Completed)
The system has successfully evolved into a **StackOverflow-style knowledge base** in `portal/`:
* The WhatsApp-sourced information automatically generates and updates curated Q&A pairs directly from the canonical SQLite database.
* Users can browse questions, inspect AI-synthesized canonical answers, and view the original WhatsApp verbatim messages as discussion provenance (with sender names, dates, and quotes).
* Provides a real-time searchable, domain-filtered, interconnected collective learning "brain" running on port 3001.
