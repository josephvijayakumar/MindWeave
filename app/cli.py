"""Command-line workflow for MindWeave.

The CLI shares the SQLite database with the web UI. It can import/analyze and
publish review material, but canonical knowledge changes still require an
explicit `approve` or `approve-all --confirm` command (or UI approval).
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from io import BytesIO
from pathlib import Path

from .db import Database
from .google_docs import publish_review_document, sync_review_decisions
import os
from .llm import HeuristicProvider, GeminiProvider, AgyProvider
from .parser import parse_whatsapp_export, parse_telegram_json


def _load_export(path: Path):
    payload = path.read_bytes()
    filename = path.name
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            transcripts = [entry for entry in archive.infolist() if not entry.is_dir() and Path(entry.filename).suffix.lower() == ".txt"]
            if not transcripts:
                raise ValueError("ZIP does not contain a .txt chat transcript")
            transcript = max(transcripts, key=lambda entry: entry.file_size)
            if transcript.file_size > 25 * 1024 * 1024:
                raise ValueError("Chat transcript exceeds the 25 MB import limit")
            payload = archive.read(transcript)
            filename = f"{filename} / {Path(transcript.filename).name}"
    elif path.suffix.lower() == ".json":
        messages = parse_telegram_json(payload.decode("utf-8", errors="replace"))
        if not messages: raise ValueError("No Telegram messages found")
        return filename, messages
    elif path.suffix.lower() == ".txt":
        messages = parse_whatsapp_export(payload.decode("utf-8", errors="replace"))
        if not messages: raise ValueError("No WhatsApp messages found")
        return filename, messages
    else:
        raise ValueError("Use a WhatsApp .txt export, Telegram .json, or a media .zip export")
    
    if path.suffix.lower() == ".zip":
        messages = parse_whatsapp_export(payload.decode("utf-8", errors="replace"))
    
    return filename, messages


def render_review_document(database: Database) -> str:
    proposals = database.pending_proposals()
    lines = ["# MindWeave review", "", "These are AI proposals. Approval in this document is informational; use the MindWeave UI or explicit CLI approval to update canonical knowledge.", ""]
    if not proposals:
        return "\n".join(lines + ["No pending proposals.", ""])
    for proposal in proposals:
        source_ids = json.loads(proposal["source_message_ids"])
        messages = database.get_messages(source_ids)
        rel_data = json.loads(proposal["related_concepts"])
        related_strs = []
        for rel in rel_data:
            if isinstance(rel, str): related_strs.append(rel)
            else: related_strs.append(f"{rel.get('concept')} ({rel.get('type')})")
        related = ", ".join(related_strs) or "None"
        lines.extend([
            f"## Proposal {proposal['id']}: {proposal['concept']}",
            f"- Type: {proposal['kind']}",
            f"- Topic: {proposal['topic']}",
            f"- Confidence: {proposal['confidence']:.0%}",
            f"- Related concepts: {related}",
            "", 
            "**Source Messages:**"
        ])
        for m in messages:
            lines.append(f"> **{m['sender']}**: {m['content']}")
        
        lines.extend([
            "", proposal["explanation"], "", f"Reason: {proposal['reason']}",
            "", "Reviewer decision: PENDING", "",
        ])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mindweave", description="MindWeave local CLI")
    parser.add_argument("--db", default="mindweave.db", help="SQLite database path (default: mindweave.db)")
    commands = parser.add_subparsers(dest="command", required=True)
    import_cmd = commands.add_parser("import", help="Import a WhatsApp .txt or media ZIP export")
    import_cmd.add_argument("path", type=Path)
    analyze_cmd = commands.add_parser("analyze", help="Create proposals from unprocessed messages")
    analyze_cmd.add_argument("--since", help="Process messages sent since date (YYYY-MM-DD)")
    analyze_cmd.add_argument("--until", help="Process messages sent until date (YYYY-MM-DD)")
    analyze_cmd.add_argument("--limit", type=int, help="Limit number of messages processed in this batch")
    export_cmd = commands.add_parser("export-review", help="Write pending proposals to a Markdown review document")
    export_cmd.add_argument("--output", type=Path, required=True)
    export_knowledge_cmd = commands.add_parser("export-knowledge", help="Export canonical knowledge base to Markdown")
    export_knowledge_cmd.add_argument("--output", type=Path, required=True)
    publish_cmd = commands.add_parser("publish-google-doc", help="Create a Google Doc containing pending proposals")
    publish_cmd.add_argument("--client-secrets", required=True, help="OAuth desktop-client JSON file")
    publish_cmd.add_argument("--token", default=".mindweave-google-token.json", help="Local OAuth token path")
    publish_cmd.add_argument("--title", default="MindWeave review", help="Google Doc title")
    sync_cmd = commands.add_parser("sync-google-doc", help="Sync review decisions from a Google Doc")
    sync_cmd.add_argument("document_id", help="The Google Doc ID")
    sync_cmd.add_argument("--client-secrets", required=True, help="OAuth desktop-client JSON file")
    sync_cmd.add_argument("--token", default=".mindweave-google-token.json", help="Local OAuth token path")
    approve_cmd = commands.add_parser("approve", help="Explicitly approve one pending proposal")
    approve_cmd.add_argument("proposal_id", type=int)
    approve_cmd.add_argument("--note", default="")
    approve_all = commands.add_parser("approve-all", help="Explicitly approve every pending proposal")
    approve_all.add_argument("--confirm", action="store_true", help="Required guard against accidental bulk approval")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    database = Database(args.db)
    database.initialize()
    try:
        if args.command == "import":
            filename, messages = _load_export(args.path)
            _, count = database.import_messages(filename, messages)
            print(f"Imported {count} messages from {filename}")
        elif args.command == "analyze":
            messages = database.unprocessed_messages(since=args.since, until=args.until, limit=args.limit)
            provider_choice = os.environ.get("LLM_PROVIDER", "agy").lower()
            if provider_choice == "gemini":
                provider = GeminiProvider()
            elif provider_choice == "heuristic":
                provider = HeuristicProvider()
            else:
                provider = AgyProvider()
            proposals = provider.propose(messages, database.all_knowledge())
            database.add_proposals(proposals)
            database.mark_analyzed([message["id"] for message in messages])
            print(f"Analyzed {len(messages)} messages and created {len(proposals)} proposals")
        elif args.command == "export-review":
            args.output.write_text(render_review_document(database), encoding="utf-8")
            print(f"Review document written to {args.output}")
        elif args.command == "export-knowledge":
            lines = ["# MindWeave Knowledge Base", ""]
            knowledge = database.all_knowledge()
            relationships = database.relationships()
            rels_by_id = {}
            for r in relationships:
                rels_by_id.setdefault(r["from_knowledge_id"], []).append(r)
            for item in knowledge:
                lines.extend([
                    f"## {item['topic']}: {item['concept']}",
                    f"- Confidence: {item['confidence']:.0%}",
                    f"- Version: {item['version']}",
                    "",
                    item["explanation"],
                    ""
                ])
                if item["id"] in rels_by_id:
                    lines.append("**Relationships:**")
                    for r in rels_by_id[item["id"]]:
                        lines.append(f"- {r['relation_type']}: {r['to_concept']}")
                    lines.append("")
            args.output.write_text("\n".join(lines), encoding="utf-8")
            print(f"Knowledge document written to {args.output}")
        elif args.command == "publish-google-doc":
            url = publish_review_document(args.title, render_review_document(database), args.client_secrets, args.token)
            print(f"Google review document created: {url}")
        elif args.command == "sync-google-doc":
            decisions = sync_review_decisions(args.document_id, args.client_secrets, args.token)
            if not decisions:
                print("No APPROVED or REJECTED decisions found.")
            else:
                for prop_id, decision in decisions.items():
                    try:
                        database.review(prop_id, approved=(decision == "APPROVED"), note=f"Synced from Google Doc {args.document_id}")
                        print(f"Synced proposal {prop_id} as {decision}")
                    except ValueError as e:
                        print(f"Skipping proposal {prop_id}: {e}")
        elif args.command == "approve":
            database.review(args.proposal_id, True, args.note)
            print(f"Approved proposal {args.proposal_id}")
        elif args.command == "approve-all":
            if not args.confirm:
                raise ValueError("Refusing bulk approval: rerun with --confirm")
            pending = database.pending_proposals()
            for proposal in pending:
                database.review(proposal["id"], True)
            print(f"Approved {len(pending)} proposals")
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
