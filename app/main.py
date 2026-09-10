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

from .db import Database
from .llm import HeuristicProvider, GeminiProvider
from .parser import parse_whatsapp_export

DATA_PATH = os.environ.get("MINDWEAVE_DB", "mindweave.db")
db = Database(DATA_PATH)
if os.environ.get("LLM_PROVIDER", "heuristic").lower() == "gemini":
    provider = GeminiProvider()
else:
    provider = HeuristicProvider()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.initialize()
    yield

app = FastAPI(title="MindWeave", lifespan=lifespan)
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
    return templates.TemplateResponse(request, "dashboard.html", {"proposals": proposals_with_sources, "summary": summary, "message": request.query_params.get("message")})

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
        except zipfile.BadZipFile:
            return RedirectResponse("/?message=The+uploaded+file+is+not+a+valid+ZIP+archive", status_code=303)
    elif suffix != ".txt":
        return RedirectResponse("/?message=Upload+a+WhatsApp+.txt+export+or+media+ZIP", status_code=303)
    parsed = parse_whatsapp_export(payload.decode("utf-8", errors="replace"))
    if not parsed:
        return RedirectResponse("/?message=No+WhatsApp+messages+were+found.+Please+export+the+chat+as+.txt+or+ZIP+from+WhatsApp.", status_code=303)
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
    try: db.review(proposal_id, decision == "approve", note, topic, concept, explanation)
    except ValueError as exc: raise HTTPException(404, str(exc))
    return RedirectResponse("/?message=Proposal+reviewed", status_code=303)

@app.post("/proposals/approve-all")
def approve_all():
    for proposal in db.pending_proposals(): db.review(proposal["id"], True)
    return RedirectResponse("/?message=All+pending+proposals+approved", status_code=303)

@app.get("/knowledge")
def knowledge(request: Request):
    return templates.TemplateResponse(request, "knowledge.html", {"items": db.all_knowledge(), "relationships": db.relationships(), "json": json})

@app.get("/graph")
def graph(request: Request):
    items = db.all_knowledge()
    relationships = db.relationships()
    nodes = [{"id": item["id"], "label": item["concept"], "group": item["topic"]} for item in items]
    edges = [{"from": rel["from_knowledge_id"], "to": rel["to_knowledge_id"], "label": rel["relation_type"]} for rel in relationships]
    return templates.TemplateResponse(request, "graph.html", {"nodes": json.dumps(nodes), "edges": json.dumps(edges)})
