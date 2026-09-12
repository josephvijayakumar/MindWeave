from __future__ import annotations

import json
import os
import zipfile
from io import BytesIO
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime

from .db import Database
from .llm import HeuristicProvider, GeminiProvider, AgyProvider
from .parser import parse_whatsapp_export, parse_telegram_json
from .obsidian import export_to_vault
from .whatsapp_local import get_whatsapp_messages, get_whatsapp_chats
from .models import ParsedMessage

DATA_PATH = os.environ.get("MINDWEAVE_DB", "database/mindweave.db")
db = Database(DATA_PATH)
provider_choice = os.environ.get("LLM_PROVIDER", "agy").lower()
if provider_choice == "gemini":
    provider = GeminiProvider()
elif provider_choice == "heuristic":
    provider = HeuristicProvider()
else:
    provider = AgyProvider()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    yield

app = FastAPI(title="MindWeave", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

@app.get("/")
def dashboard(request: Request):
    proposals = db.pending_proposals()
    summary = {"CREATE": 0, "UPDATE": 0, "CONTRADICTION": 0, "QUESTION": 0}
    proposals_with_sources = []
    for proposal in proposals:
        summary[proposal["kind"]] += 1
        source_ids = json.loads(proposal["source_message_ids"])
        messages = db.get_messages(source_ids)
        proposals_with_sources.append({"proposal": proposal, "messages": messages})
    
    whatsapp_chats = get_whatsapp_chats()
    default_group = os.environ.get("MINDWEAVE_WHATSAPP_GROUP", "Let’s Learn together - GoDB Friends")
    
    with db.connection() as conn:
        total_messages = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "proposals": proposals_with_sources,
            "summary": summary,
            "message": request.query_params.get("message"),
            "whatsapp_chats": whatsapp_chats,
            "default_group": default_group,
            "total_canonical": len(db.all_knowledge()),
            "total_relationships": len(db.relationships()),
            "unanalyzed_count": len(db.unprocessed_messages()),
            "total_messages": total_messages
        }
    )

@app.post("/sync-whatsapp")
def sync_whatsapp(group_name: str = Form("Let’s Learn together - GoDB Friends"), auto_analyze: str = Form("yes")):
    try:
        messages = get_whatsapp_messages(group_name, limit=500)
        parsed = [
            ParsedMessage(
                external_id=m["external_id"],
                sent_at=datetime.fromisoformat(m["sent_at"]) if m["sent_at"] else None,
                sender=m["sender"],
                content=m["content"],
                is_system=False
            )
            for m in messages
        ]
        _, saved_count = db.import_messages(f"wa_sync_{group_name}", parsed)
        msg = f"Synced+{saved_count}+new+messages+from+'{group_name}'"
        
        if auto_analyze == "yes" and saved_count > 0:
            unprocessed = db.unprocessed_messages()
            proposals = provider.propose(unprocessed, db.all_knowledge())
            db.add_proposals(proposals)
            db.mark_analyzed([r["id"] for r in unprocessed])
            msg += f"+and+generated+{len(proposals)}+proposals"
        return RedirectResponse(f"/?message={msg}", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/?message=WhatsApp+sync+failed:+{str(e)}", status_code=303)

@app.post("/imports")
async def import_chat(chat: UploadFile = File(...)):
    if not chat.filename:
        return RedirectResponse("/?message=Choose+a+WhatsApp+export+file", status_code=303)
    payload = await chat.read()
    filename = chat.filename
    suffix = Path(filename).suffix.lower()
    if suffix == ".zip":
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                text_files = [entry for entry in archive.infolist() if not entry.is_dir() and Path(entry.filename).suffix.lower() == ".txt"]
                if not text_files:
                    return RedirectResponse("/?message=This+ZIP+does+not+contain+a+chat+.txt+file", status_code=303)
                # WhatsApp exports normally contain one transcript; choose the largest if media metadata adds another text file.
                transcript = max(text_files, key=lambda entry: entry.file_size)
                if transcript.file_size > 25 * 1024 * 1024:
                    return RedirectResponse("/?message=The+chat+transcript+exceeds+the+25+MB+import+limit", status_code=303)
                payload = archive.read(transcript)
                filename = f"{filename} / {Path(transcript.filename).name}"
                parsed = parse_whatsapp_export(payload.decode("utf-8", errors="replace"))
        except zipfile.BadZipFile:
            return RedirectResponse("/?message=The+uploaded+file+is+not+a+valid+ZIP+archive", status_code=303)
    elif suffix == ".json":
        parsed = parse_telegram_json(payload.decode("utf-8", errors="replace"))
        if not parsed:
            return RedirectResponse("/?message=No+Telegram+messages+found.+Export+the+group+as+JSON.", status_code=303)
    elif suffix == ".txt":
        parsed = parse_whatsapp_export(payload.decode("utf-8", errors="replace"))
        if not parsed:
            return RedirectResponse("/?message=No+WhatsApp+messages+were+found.+Please+export+the+chat+as+.txt+or+ZIP+from+WhatsApp.", status_code=303)
    else:
        return RedirectResponse("/?message=Upload+a+WhatsApp+.txt+or+Telegram+.json+export", status_code=303)
    
    if not parsed: return RedirectResponse("/?message=No+messages+found", status_code=303)
    _, count = db.import_messages(filename, parsed)
    return RedirectResponse(f"/?message=Imported+{count}+messages", status_code=303)

@app.post("/analyze")
def analyze():
    messages = db.unprocessed_messages()
    try:
        proposals = provider.propose(messages, db.all_knowledge())
    except Exception as exc:
        return RedirectResponse(f"/?message=Analysis+failed:+{exc}", status_code=303)
    db.add_proposals(proposals)
    db.mark_analyzed([row["id"] for row in messages])
    return RedirectResponse(f"/?message=Analyzed+{len(messages)}+messages+and+created+{len(proposals)}+proposals", status_code=303)

@app.post("/proposals/{proposal_id}/review")
def review(proposal_id: int, decision: str = Form(...), note: str = Form(""), topic: str = Form(None), concept: str = Form(None), explanation: str = Form(None)):
    try: 
        db.review(proposal_id, decision == "approve", note, topic, concept, explanation)
        if decision == "approve": export_to_vault(db)
    except ValueError as exc: raise HTTPException(404, str(exc))
    return RedirectResponse("/?message=Proposal+reviewed", status_code=303)

@app.post("/proposals/approve-all")
def approve_all():
    for proposal in db.pending_proposals(): db.review(proposal["id"], True)
    export_to_vault(db)
    return RedirectResponse("/?message=All+pending+proposals+approved", status_code=303)

@app.get("/knowledge")
def knowledge(request: Request):
    items = db.all_knowledge()
    grouped = {}
    for item in items:
        grouped.setdefault(item["topic"], []).append(item)
    rels = db.relationships()
    rels_by_item = {}
    for r in rels:
        rels_by_item.setdefault(r["from_knowledge_id"], []).append(r)
    return templates.TemplateResponse(
        request,
        "knowledge.html",
        {
            "grouped_items": grouped,
            "relationships": rels,
            "rels_by_item": rels_by_item,
            "all_items": items,
            "json": json,
            "message": request.query_params.get("message", "")
        }
    )

@app.get("/graph")
def graph(request: Request):
    items = db.all_knowledge()
    relationships = db.relationships()
    nodes = [
        {
            "id": item["id"],
            "label": item["concept"],
            "group": item["topic"],
            "topic": item["topic"],
            "concept": item["concept"],
            "explanation": item["explanation"],
            "confidence": round(float(item["confidence"]) * 100),
            "version": item["version"],
        }
        for item in items
    ]
    edges = [
        {
            "id": rel["id"],
            "from": rel["from_knowledge_id"],
            "to": rel["to_knowledge_id"],
            "label": rel["relation_type"].replace("_", " "),
            "relation_type": rel["relation_type"],
            "from_concept": rel["from_concept"],
            "to_concept": rel["to_concept"],
        }
        for rel in relationships
    ]
    topics = sorted(list({item["topic"] for item in items}))
    return templates.TemplateResponse(
        request,
        "graph.html",
        {
            "nodes": json.dumps(nodes),
            "edges": json.dumps(edges),
            "all_items": items,
            "topics": topics,
            "relationships": relationships,
            "message": request.query_params.get("message", "")
        }
    )

@app.post("/relationships")
def create_relationship(from_knowledge_id: int = Form(...), to_knowledge_id: int = Form(...), relation_type: str = Form("related_to")):
    added = db.add_relationship(from_knowledge_id, to_knowledge_id, relation_type)
    if added:
        export_to_vault(db)
        msg = "Relationship+created+successfully"
    else:
        msg = "Relationship+already+exists+or+invalid"
    return RedirectResponse(f"/graph?message={msg}", status_code=303)

@app.post("/relationships/{rel_id}/delete")
def delete_relationship(rel_id: int):
    db.delete_relationship(rel_id)
    export_to_vault(db)
    return RedirectResponse("/graph?message=Relationship+deleted", status_code=303)

@app.post("/relationships/discover")
def discover_relationships():
    discovered = db.infer_relationships()
    export_to_vault(db)
    msg = f"Discovered+{len(discovered)}+new+semantic+relationships" if discovered else "No+new+relationships+found"
    return RedirectResponse(f"/graph?message={msg}", status_code=303)

@app.get("/api/knowledge")
def api_knowledge():
    items = db.all_knowledge()
    relationships = db.relationships()
    
    # Map relationships by from_knowledge_id
    rels_by_id = {}
    for r in relationships:
        rels_by_id.setdefault(r["from_knowledge_id"], []).append({
            "id": r["id"],
            "relation_type": r["relation_type"],
            "to_id": r["to_knowledge_id"],
            "to_concept": r["to_concept"]
        })

    # Fetch source message provenance for each knowledge item
    provenance_map = {}
    try:
        with db.connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT k.id, p.source_message_ids
                FROM knowledge_items k
                JOIN knowledge_versions kv ON kv.knowledge_item_id = k.id
                LEFT JOIN proposals p ON p.id = kv.proposal_id
            """)
            for row in cur.fetchall():
                if row["source_message_ids"]:
                    try:
                        sids = json.loads(row["source_message_ids"])
                        provenance_map[row["id"]] = sids
                    except Exception:
                        pass
    except Exception:
        pass

    enriched_items = []
    for item in items:
        sids = provenance_map.get(item["id"], [])
        source_messages = []
        if sids:
            try:
                with db.connection() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        f"SELECT id, sender, content, sent_at FROM messages WHERE id IN ({','.join('?'*len(sids))}) ORDER BY id ASC",
                        sids
                    )
                    source_messages = [
                        {
                            "id": m["id"],
                            "sender": m["sender"],
                            "content": m["content"],
                            "sent_at": m["sent_at"]
                        }
                        for m in cur.fetchall()
                    ]
            except Exception:
                pass
        
        # Formulate intuitive StackOverflow-style Question and Answer
        concept_title = item["concept"]
        topic = item["topic"]
        question = f"What is {concept_title} in {topic} and how does it work?"
        if topic.lower() == "technology":
            question = f"How is {concept_title} implemented and what are its engineering trade-offs?"
        elif topic.lower() == "finance":
            question = f"What is {concept_title} and how does it impact policy or financial strategy?"
        elif topic.lower() == "ai":
            question = f"What does {concept_title} mean in the context of LLMs and Modern AI systems?"

        # Confidence percentage (e.g. 95)
        conf_pct = round(float(item["confidence"]) * 100)
        upvotes = int(conf_pct / 5) + (item["version"] * 4) + len(source_messages) * 2

        enriched_items.append({
            "id": item["id"],
            "topic": item["topic"],
            "concept": item["concept"],
            "question": question,
            "answer": item["explanation"],
            "explanation": item["explanation"],
            "confidence": conf_pct,
            "version": item["version"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
            "relationships": rels_by_id.get(item["id"], []),
            "source_messages": source_messages,
            "upvotes": upvotes,
            "answers_count": item["version"]
        })

    topics = sorted(list({item["topic"] for item in items}))
    
    with db.connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages")
        total_messages = cur.fetchone()[0]

    return {
        "items": enriched_items,
        "topics": topics,
        "total_items": len(items),
        "total_relationships": len(relationships),
        "total_messages": total_messages
    }
