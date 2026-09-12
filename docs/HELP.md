# MindWeave - Help & Quick Start Guide

This document contains all the necessary commands to run, test, and manage the MindWeave project locally from your terminal or IDE (like Antigravity).

Make sure you run all commands from the root of the project folder:
`/Users/josephvijayakumarj/Projects2026/MindWeave`

---

## 1. Start the Web Dashboard
To start the FastAPI web dashboard, run the following command. The server will run at `http://localhost:8000` and automatically reload if you make code changes.

```bash
.venv/bin/uvicorn backend.main:app --reload
```

## 2. Sync Local WhatsApp Messages
To automatically pull the newest messages from your local WhatsApp Desktop application and analyze them using the AI, run:

```bash
.venv/bin/python -m backend.cli sync-local "Let’s Learn together - GoDB Friends"
```
*(Replace the group name in quotes with any exact WhatsApp group or contact name as it appears in your app).*

## 3. Run the Automated Tests
If you modify the codebase, you can run the test suite to ensure everything is working correctly:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

## 4. Export to Obsidian
If you want to manually force an export of all approved knowledge directly into your local Obsidian vault (`MindWeave_Vault/`), run:

```bash
.venv/bin/python -m backend.cli export-obsidian
```

---

## Troubleshooting
**"Port 8000 is already in use" Error:**
If you try to run the web server and it fails because port 8000 is occupied, it means the server is already running in the background. You will need to stop the existing process before starting it again in your IDE.
