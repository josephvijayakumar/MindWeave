import sqlite3
import os
import shutil
from datetime import datetime
from typing import List, Dict

DB_PATH = os.path.expanduser("~/Library/Group Containers/group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite")
TMP_DB_PATH = "/tmp/ChatStorage_MindWeave.sqlite"

def get_whatsapp_messages(group_name: str, limit: int = 500) -> List[Dict]:
    """Reads messages directly from the macOS local WhatsApp database."""
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"WhatsApp database not found at {DB_PATH}. Are you sure WhatsApp Desktop is installed from the Mac App Store?")
        
    # Copy DB because WhatsApp might be locking it
    shutil.copy2(DB_PATH, TMP_DB_PATH)
    
    conn = sqlite3.connect(TMP_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Apple timestamp is offset from Jan 1 2001 (978307200 seconds from Unix Epoch)
    
    cursor.execute("SELECT Z_PK FROM ZWACHATSESSION WHERE ZPARTNERNAME = ?", (group_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Chat or Group '{group_name}' not found in your WhatsApp database.")
        
    chat_id = row['Z_PK']
    
    cursor.execute('''
        SELECT Z_PK, ZTEXT, ZMESSAGEDATE, ZISFROMME, ZPUSHNAME 
        FROM ZWAMESSAGE 
        WHERE ZCHATSESSION = ? AND ZTEXT IS NOT NULL
        ORDER BY ZMESSAGEDATE DESC 
        LIMIT ?
    ''', (chat_id, limit))
    
    results = []
    # Reverse to get chronological order
    for row in reversed(cursor.fetchall()):
        timestamp = row['ZMESSAGEDATE'] + 978307200
        dt = datetime.fromtimestamp(timestamp)
        sender = row['ZPUSHNAME'] if row['ZPUSHNAME'] else ("Me" if row['ZISFROMME'] else "Unknown")
        
        # In WhatsApp's DB, Z_PK is a unique incrementing primary key for every message
        msg_id = f"wa_mac_{row['Z_PK']}"
        
        results.append({
            "sender": sender,
            "content": row['ZTEXT'],
            "sent_at": dt.isoformat(),
            "external_id": msg_id
        })
        
    conn.close()
    
    # Clean up temp db
    if os.path.exists(TMP_DB_PATH):
        os.remove(TMP_DB_PATH)
        
    return results


def get_whatsapp_chats(limit: int = 25) -> List[str]:
    """Returns the names of recent active chats and groups from local WhatsApp database."""
    if not os.path.exists(DB_PATH):
        return []
    try:
        shutil.copy2(DB_PATH, TMP_DB_PATH)
        conn = sqlite3.connect(TMP_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ZPARTNERNAME FROM ZWACHATSESSION WHERE ZPARTNERNAME IS NOT NULL AND ZPARTNERNAME != '' ORDER BY ZLASTMESSAGEDATE DESC LIMIT ?",
            (limit,)
        )
        chats = [row["ZPARTNERNAME"] for row in cursor.fetchall() if not row["ZPARTNERNAME"].startswith("‎")]
        conn.close()
        if os.path.exists(TMP_DB_PATH):
            os.remove(TMP_DB_PATH)
        return chats
    except Exception:
        return []
