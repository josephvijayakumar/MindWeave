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
from datetime import datetime
import subprocess

from .google_docs import publish_review_document, sync_review_decisions
import os
from .llm import LLMProvider, HeuristicProvider, GeminiProvider, AgyProvider
from .parser import parse_whatsapp_export, parse_telegram_json
from .obsidian import export_to_vault
from .db import Database
from .models import ProposalKind, ProposedChange, ParsedMessage
from .whatsapp_local import get_whatsapp_messages


def _get_llm_provider() -> LLMProvider:
    choice = os.environ.get("LLM_PROVIDER", "agy").lower()
    if choice == "gemini":
        return GeminiProvider()
    elif choice == "heuristic":
        return HeuristicProvider()
    return AgyProvider()


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
    parser.add_argument("--db", default=os.environ.get("MINDWEAVE_DB", "database/mindweave.db"), help="SQLite database path (default: database/mindweave.db)")
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
    export_obsidian_cmd = commands.add_parser("export-obsidian", help="Export the knowledge base as an Obsidian Markdown vault")
    export_obsidian_cmd.add_argument("--output", type=Path, help="Output directory path (default: MindWeave_Vault)")
    sync_local_cmd = commands.add_parser("sync-local", help="Sync messages from local WhatsApp database")
    sync_local_cmd.add_argument("group_name", help="WhatsApp group name", nargs="?")
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
    commands.add_parser("link-concepts", help="Automatically infer semantic relationships between approved concepts")
    
    daily_sync_cmd = commands.add_parser("daily-sync", help="Automated daily ingestion: syncs WhatsApp, runs AI analysis, and enqueues proposals")
    daily_sync_cmd.add_argument("--group", help="WhatsApp group name (default: env MINDWEAVE_WHATSAPP_GROUP or 'Let’s Learn together - GoDB Friends')")
    daily_sync_cmd.add_argument("--limit", type=int, default=500, help="Maximum messages to inspect (default: 500)")
    daily_sync_cmd.add_argument("--dry-run", action="store_true", help="Inspect messages without persisting or creating proposals")
    daily_sync_cmd.add_argument("--discover-links", action="store_true", help="Also run semantic relationship discovery on canonical knowledge")

    schedule_cmd = commands.add_parser("setup-schedule", help="Generate or install a daily macOS launchd schedule or cron entry")
    schedule_cmd.add_argument("--install", action="store_true", help="Install LaunchAgent to ~/Library/LaunchAgents/")
    schedule_cmd.add_argument("--uninstall", action="store_true", help="Uninstall LaunchAgent from ~/Library/LaunchAgents/")
    schedule_cmd.add_argument("--time", default="02:00", help="Daily time in 24h format (default: 02:00)")
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
        elif args.command == "export-obsidian":
            export_dir = args.output if args.output else Path("MindWeave_Vault")
            export_to_vault(database, str(export_dir))
            print(f"Exported items to Obsidian vault at '{Path(export_dir).absolute()}'.")
        elif args.command == "sync-local":
            if len(sys.argv) < 3 and not args.group_name:
                print("Usage: python -m backend.cli sync-local \"Group Name\"")
                sys.exit(1)
            group_name = args.group_name if hasattr(args, "group_name") and args.group_name else sys.argv[2]
            print(f"Connecting to local WhatsApp database to sync '{group_name}'...")
            try:
                messages = get_whatsapp_messages(group_name, limit=500)
                print(f"Found {len(messages)} recent messages.")
                
                db = Database(args.db)
                parsed_messages = [
                    ParsedMessage(
                        external_id=msg["external_id"],
                        sent_at=datetime.fromisoformat(msg["sent_at"]) if msg["sent_at"] else None,
                        sender=msg["sender"],
                        content=msg["content"],
                        is_system=False
                    )
                    for msg in messages
                ]
                
                _, saved_count = db.import_messages("local_sync", parsed_messages)
                print(f"Imported {saved_count} new messages (skipped {len(messages) - saved_count} duplicates).")
                
                # Automatically analyze the new messages
                if saved_count > 0:
                    print("Analyzing new messages...")
                    un_analyzed = db.unprocessed_messages()
                    llm = _get_llm_provider()
                    un_analyzed_dicts = [dict(row) for row in un_analyzed]
                    existing_knowledge = [dict(row) for row in db.all_knowledge()]
                    
                    proposals = llm.propose(un_analyzed_dicts, existing_knowledge)
                    db.add_proposals(proposals)
                    db.mark_analyzed([m["id"] for m in un_analyzed])
                    print(f"Created {len(proposals)} new proposals.")
            except Exception as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif args.command == "daily-sync":
            group_name = args.group or os.environ.get("MINDWEAVE_WHATSAPP_GROUP") or "Let’s Learn together - GoDB Friends"
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Starting automated daily sync for WhatsApp group: '{group_name}'...")
            
            if args.dry_run:
                print("[DRY-RUN] Checking local WhatsApp database connection...")
                messages = get_whatsapp_messages(group_name, limit=min(args.limit, 10))
                print(f"[DRY-RUN] Found {len(messages)} sample messages. WhatsApp database connection verified.")
                return 0

            messages = get_whatsapp_messages(group_name, limit=args.limit)
            print(f"Retrieved {len(messages)} messages from local WhatsApp database.")
            
            parsed_messages = [
                ParsedMessage(
                    external_id=msg["external_id"],
                    sent_at=datetime.fromisoformat(msg["sent_at"]) if msg["sent_at"] else None,
                    sender=msg["sender"],
                    content=msg["content"],
                    is_system=False
                )
                for msg in messages
            ]
            
            import_tag = f"daily_sync_{datetime.now().strftime('%Y%m%d')}"
            _, saved_count = database.import_messages(import_tag, parsed_messages)
            print(f"Imported {saved_count} new messages ({len(messages) - saved_count} duplicates skipped).")
            
            if saved_count > 0:
                print("Analyzing newly imported messages with AI provider...")
                un_analyzed = database.unprocessed_messages()
                llm = _get_llm_provider()
                un_analyzed_dicts = [dict(row) for row in un_analyzed]
                existing_knowledge = [dict(row) for row in database.all_knowledge()]
                
                proposals = llm.propose(un_analyzed_dicts, existing_knowledge)
                database.add_proposals(proposals)
                database.mark_analyzed([m["id"] for m in un_analyzed])
                print(f"Created {len(proposals)} new knowledge proposals awaiting human review.")
            else:
                print("No new unanalyzed messages.")
                
            if args.discover_links:
                print("Running semantic relationship discovery...")
                discovered = database.infer_relationships()
                export_to_vault(database)
                print(f"Discovered {len(discovered)} new relationships.")
                
            pending_count = len(database.pending_proposals())
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Daily sync completed. Total pending proposals in approval queue: {pending_count}")
        elif args.command == "setup-schedule":
            plist_name = "com.mindweave.dailysync.plist"
            user_home = Path.home()
            launch_agents_dir = user_home / "Library" / "LaunchAgents"
            target_plist = launch_agents_dir / plist_name
            project_dir = Path(__file__).resolve().parent.parent
            script_path = project_dir / "scripts" / "daily_sync.sh"
            
            time_parts = args.time.split(":")
            hour = int(time_parts[0]) if len(time_parts) > 0 else 2
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            if args.uninstall:
                if target_plist.exists():
                    subprocess.run(["launchctl", "unload", str(target_plist)], check=False)
                    target_plist.unlink()
                    print(f"Uninstalled LaunchAgent from {target_plist}")
                else:
                    print("LaunchAgent not currently installed.")
                return 0
                
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mindweave.dailysync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>{script_path}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{project_dir}/logs/daily_sync.log</string>
    <key>StandardErrorPath</key>
    <string>{project_dir}/logs/daily_sync.err</string>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
"""
            (project_dir / "scripts").mkdir(parents=True, exist_ok=True)
            (project_dir / "logs").mkdir(parents=True, exist_ok=True)
            
            if args.install:
                launch_agents_dir.mkdir(parents=True, exist_ok=True)
                target_plist.write_text(plist_content, encoding="utf-8")
                subprocess.run(["launchctl", "unload", str(target_plist)], check=False)
                subprocess.run(["launchctl", "load", str(target_plist)], check=False)
                print(f"Successfully installed and loaded macOS LaunchAgent at {target_plist}")
                print(f"Scheduled to run daily at {hour:02d}:{minute:02d}.")
            else:
                print(f"Generated LaunchAgent specification (Daily at {hour:02d}:{minute:02d}):\n")
                print(plist_content)
                print(f"To install as active background job on macOS, run:\n.venv/bin/python -m backend.cli setup-schedule --install --time {args.time}\n")
                print(f"Or to use standard crontab, add the following line:\n{minute} {hour} * * * /bin/bash {script_path} >> {project_dir}/logs/daily_sync.log 2>&1\n")
        elif args.command == "link-concepts":
            discovered = database.infer_relationships()
            export_to_vault(database)
            print(f"Discovered and recorded {len(discovered)} relationships:")
            for d in discovered:
                print(f"  - {d['from_concept']} --[{d['relation_type']}]--> {d['to_concept']}")
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
