"""
Time Travel Debugger MCP Server v1.2.0
AI Agent Time-Travel Debugger, SQLite Shadow Snapshot & Instant Rollback Engine MCP Server.
"""

import argparse
import difflib
import json
import os
import sqlite3
import sys
import time
from typing import Dict, List, Any, Optional

VERSION = "1.2.0"
DB_PATH = os.path.expanduser("~/.time_travel_debugger.db")

def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                description TEXT
            )
        """)
    return conn

def create_shadow_checkpoint(file_path: str, description: str = "", db_path: str = DB_PATH) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    conn = init_db(db_path)
    now = time.time()
    with conn:
        cursor = conn.execute(
            "INSERT INTO checkpoints (file_path, content, timestamp, description) VALUES (?, ?, ?, ?)",
            (os.path.abspath(file_path), content, now, description)
        )
        checkpoint_id = cursor.lastrowid
    return {
        "status": "success",
        "checkpoint_id": checkpoint_id,
        "file_path": os.path.abspath(file_path),
        "timestamp": now,
        "description": description
    }

def list_timeline_checkpoints(file_path: Optional[str] = None, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = init_db(db_path)
    if file_path:
        abs_path = os.path.abspath(file_path)
        cursor = conn.execute("SELECT id, file_path, timestamp, description FROM checkpoints WHERE file_path = ? ORDER BY id DESC", (abs_path,))
    else:
        cursor = conn.execute("SELECT id, file_path, timestamp, description FROM checkpoints ORDER BY id DESC")
    rows = cursor.fetchall()
    return [{"id": r[0], "file_path": r[1], "timestamp": r[2], "description": r[3]} for r in rows]

def diff_against_checkpoint(checkpoint_id: int, file_path: Optional[str] = None, db_path: str = DB_PATH) -> Dict[str, Any]:
    conn = init_db(db_path)
    cursor = conn.execute("SELECT file_path, content FROM checkpoints WHERE id = ?", (checkpoint_id,))
    row = cursor.fetchone()
    if not row:
        return {"status": "error", "message": f"Checkpoint ID {checkpoint_id} not found."}
    cp_file_path, cp_content = row
    target_path = file_path if file_path else cp_file_path
    if not os.path.exists(target_path):
        return {"status": "error", "message": f"Current file not found: {target_path}"}
    with open(target_path, "r", encoding="utf-8", errors="replace") as f:
        current_content = f.read()
    diff = list(difflib.unified_diff(
        cp_content.splitlines(keepends=True),
        current_content.splitlines(keepends=True),
        fromfile=f"checkpoint_{checkpoint_id}",
        tofile=target_path
    ))
    return {
        "status": "success",
        "checkpoint_id": checkpoint_id,
        "diff": "".join(diff)
    }

def rollback_to_checkpoint(checkpoint_id: int, db_path: str = DB_PATH) -> Dict[str, Any]:
    conn = init_db(db_path)
    cursor = conn.execute("SELECT file_path, content FROM checkpoints WHERE id = ?", (checkpoint_id,))
    row = cursor.fetchone()
    if not row:
        return {"status": "error", "message": f"Checkpoint ID {checkpoint_id} not found."}
    file_path, content = row
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "success", "checkpoint_id": checkpoint_id, "file_path": file_path, "message": f"Rolled back {file_path} to checkpoint {checkpoint_id}."}

def run_self_test() -> bool:
    print(f"Running Time-Travel Debugger MCP v{VERSION} Self-Test...")
    test_db = "/tmp/time_travel_test.db"
    test_file = "/tmp/test_code.py"
    if os.path.exists(test_db):
        os.remove(test_db)
    with open(test_file, "w") as f:
        f.write("print('Hello World')\n")
    cp = create_shadow_checkpoint(test_file, "Initial commit", db_path=test_db)
    assert cp["status"] == "success", "Checkpoint creation failed"
    cp_id = cp["checkpoint_id"]
    with open(test_file, "w") as f:
        f.write("print('Modified World')\n")
    diff_res = diff_against_checkpoint(cp_id, db_path=test_db)
    assert diff_res["status"] == "success", "Diff failed"
    rb_res = rollback_to_checkpoint(cp_id, db_path=test_db)
    assert rb_res["status"] == "success", "Rollback failed"
    with open(test_file, "r") as f:
        restored = f.read()
    assert restored == "print('Hello World')\n", "Content mismatch after rollback"
    print("✅ All self-tests passed successfully!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Time Travel Debugger MCP Server")
    parser.add_argument("--self-test", action="store_true", help="Run self tests")
    args = parser.parse_args()
    if args.self_test:
        run_self_test()
    else:
        print(f"Time Travel Debugger MCP Server v{VERSION} running...")
