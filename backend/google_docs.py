"""Optional Google Docs publishing adapter.

This module deliberately has no import-time Google dependency, so the local MVP
and its tests remain usable without an external account.
"""
from __future__ import annotations

from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/documents"]


def publish_review_document(title: str, content: str, client_secrets: str, token_path: str) -> str:
    """Create a Google Doc and return its URL; OAuth consent opens on first run."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Install optional Google dependencies: .venv/bin/pip install -r requirements-google.txt") from exc

    token_file = Path(token_path)
    credentials = Credentials.from_authorized_user_file(token_file, SCOPES) if token_file.exists() else None
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            credentials = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES).run_local_server(port=0)
        token_file.write_text(credentials.to_json(), encoding="utf-8")

    service = build("docs", "v1", credentials=credentials)
    document = service.documents().create(body={"title": title}).execute()
    service.documents().batchUpdate(
        documentId=document["documentId"],
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
    ).execute()
    return f"https://docs.google.com/document/d/{document['documentId']}/edit"

def sync_review_decisions(document_id: str, client_secrets: str, token_path: str) -> dict[int, str]:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Install optional Google dependencies: .venv/bin/pip install -r requirements-google.txt") from exc

    token_file = Path(token_path)
    credentials = Credentials.from_authorized_user_file(token_file, SCOPES) if token_file.exists() else None
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            credentials = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES).run_local_server(port=0)
        token_file.write_text(credentials.to_json(), encoding="utf-8")

    service = build("docs", "v1", credentials=credentials)
    document = service.documents().get(documentId=document_id).execute()
    
    decisions = {}
    current_proposal = None
    
    content = document.get('body', {}).get('content', [])
    for element in content:
        if 'paragraph' in element:
            for text_run in element.get('paragraph').get('elements', []):
                text = text_run.get('textRun', {}).get('content', '').strip()
                if text.startswith("## Proposal "):
                    try:
                        current_proposal = int(text.split(":")[0].split(" ")[2])
                    except (IndexError, ValueError):
                        pass
                elif text.startswith("Reviewer decision:"):
                    decision = text.split("Reviewer decision:")[1].strip().upper()
                    if current_proposal and decision in ("APPROVED", "REJECTED"):
                        decisions[current_proposal] = decision
                        current_proposal = None
                        
    return decisions
