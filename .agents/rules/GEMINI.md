# Gemini continuation guide

Start by reading `AGENTS.md`, then `docs/HANDOFF_GEMINI.md`. Follow the shared instructions in `AGENTS.md`; this file only adds Gemini-specific operational context.

## Assignment

Continue the MindWeave local MVP without replacing its human-approval architecture. The most valuable next implementation is a real Gemini-backed `LLMProvider` that produces validated structured proposals, selected through configuration while retaining the offline heuristic provider for tests and demos.

## Gemini provider requirements

1. Add a `GeminiProvider` alongside `HeuristicProvider` in `app/llm.py` or a focused provider module.
2. Read the API key only from an environment variable such as `GEMINI_API_KEY`; do not add secrets or `.env` files to source control.
3. Ask Gemini for JSON matching the existing `ProposedChange` fields: topic, kind, concept, explanation, reason, source-message IDs, confidence, related concepts.
4. Validate and normalize model output before storing proposals. Invalid output must fail safely, produce no canonical writes, and give the user a clear message.
5. Keep the existing heuristic provider as the default unless an explicit environment setting opts into Gemini; this keeps offline tests and demos reproducible.
6. Add mocked provider tests—tests must not make live API calls.

## Do not do without user direction

- Do not send historical chats to an external API by default without a clear UI/configuration indication.
- Do not add autonomous approval, an always-on scheduler, authentication, a separate frontend, PostgreSQL, or a graph database yet.
- Do not delete the SQLite database or imported source messages.
