from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR
WEB_DIR = BASE_DIR
DATA_DIR = Path(os.getenv("ROADPULSE_DATA_DIR", str(BASE_DIR / "data")))
DB_FILE = DATA_DIR / "roadpulse.db"
ADMIN_FILE = DATA_DIR / "admin.json"
SECRET_FILE = DATA_DIR / "server_secret.txt"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_server_secret() -> bytes:
    env_secret = os.getenv("ROADPULSE_SERVER_SECRET")
    if env_secret:
        return env_secret.encode()
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_FILE.read_text(encoding="utf-8").strip().encode()

SERVER_SECRET = get_server_secret()

def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        location TEXT NOT NULL,
        reported_by TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS cameras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_type TEXT NOT NULL,
        location TEXT NOT NULL,
        speed_limit INTEGER,
        confidence INTEGER NOT NULL DEFAULT 50,
        enabled INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        active INTEGER NOT NULL DEFAULT 1
    );
    """)
    defaults = {
        "app_name": "RoadPulse AI",
        "voice_alerts": True,
        "background_driving_mode": True,
        "community_reports": True,
        "camera_layer": True,
        "traffic_layer": True,
        "hazard_layer": True,
        "admin_2fa_required": False,
        "default_country": "DE",
        "camera_warning_mode": "country_compliance",
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)", (k, json.dumps(v)))

    if cur.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0:
        now = int(time.time())
        cur.executemany(
            "INSERT INTO reports(type,location,reported_by,status,created_at) VALUES (?,?,?,?,?)",
            [
                ("camera","A7 Hamburg","user_1023","pending",now-120),
                ("police","A24 Berlin","user_8841","verified",now-300),
                ("accident","A9 Munich","user_2210","pending",now-420),
                ("hazard","B1 Cologne","user_5522","rejected",now-540),
                ("roadwork","A3 Frankfurt","user_7721","verified",now-720),
            ],
        )
    if cur.execute("SELECT COUNT(*) FROM cameras").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO cameras(camera_type,location,speed_limit,confidence,enabled) VALUES (?,?,?,?,?)",
            [("fixed","A7 Hamburg",100,96,1),("mobile","A24 Berlin",80,82,1)],
        )
    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO users(name,role,active) VALUES (?,?,?)",
            [("Owner","super_admin",1),("Moderator One","moderator",1),("Support One","support",1)],
        )
    con.commit()
    con.close()

init_db()
app = FastAPI(title="RoadPulse AI API")

class PasswordPayload(BaseModel):
    password: str

class SettingPayload(BaseModel):
    value: Any

class StatusPayload(BaseModel):
    status: str

class CameraPayload(BaseModel):
    camera_type: str
    location: str
    speed_limit: int | None = None
    confidence: int = 50
    enabled: bool = True

def verify_admin_password(password: str) -> bool:
    # Hosted deployment: keep the password in the platform's secret environment variables,
    # never in HTML/JS/source control.
    env_password = os.getenv("ROADPULSE_ADMIN_PASSWORD")
    if env_password:
        return hmac.compare_digest(password, env_password)

    # Local/offline deployment fallback: setup_admin.py stores only a salted hash.
    if not ADMIN_FILE.exists():
        return False
    data = json.loads(ADMIN_FILE.read_text(encoding="utf-8"))
    salt = base64.b64decode(data["salt"])
    expected = base64.b64decode(data["hash"])
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, int(data.get("iterations", 600000))
    )
    return hmac.compare_digest(expected, actual)

def make_session(ttl_seconds: int = 28800) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{exp}.{secrets.token_urlsafe(16)}".encode()
    sig = hmac.new(SERVER_SECRET, payload, hashlib.sha256).digest()
    p = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    s = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return p + "." + s

def b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def require_admin(request: Request):
    token = request.cookies.get("roadpulse_admin")
    if not token or "." not in token:
        raise HTTPException(401, "Admin login required")
    try:
        p64, s64 = token.split(".", 1)
        payload = b64d(p64)
        sig = b64d(s64)
        expected = hmac.new(SERVER_SECRET, payload, hashlib.sha256).digest()
        exp = int(payload.decode().split(".", 1)[0])
        if not hmac.compare_digest(sig, expected) or exp < int(time.time()):
            raise ValueError
    except Exception:
        raise HTTPException(401, "Invalid or expired admin session")

@app.get("/api/status")
def public_status():
    return {"ok": True, "app": "RoadPulse AI"}

@app.post("/api/admin/login")
def admin_login(payload: PasswordPayload, response: Response):
    if not verify_admin_password(payload.password):
        raise HTTPException(401, "Invalid credentials")
    response.set_cookie(
        "roadpulse_admin",
        make_session(),
        httponly=True,
        secure=os.getenv("ROADPULSE_SECURE_COOKIE", "1") == "1",
        samesite="strict",
        max_age=28800,
    )
    return {"ok": True, "role": "super_admin"}

@app.post("/api/admin/logout")
def admin_logout(response: Response):
    response.delete_cookie("roadpulse_admin")
    return {"ok": True}

@app.get("/api/admin/dashboard")
def dashboard(request: Request):
    require_admin(request)
    con = db()
    reports = [dict(r) for r in con.execute("SELECT * FROM reports ORDER BY created_at DESC").fetchall()]
    cameras = [dict(r) for r in con.execute("SELECT * FROM cameras ORDER BY id DESC").fetchall()]
    users = [dict(r) for r in con.execute("SELECT * FROM users ORDER BY id").fetchall()]
    settings = {r["key"]: json.loads(r["value"]) for r in con.execute("SELECT key,value FROM settings")}
    counts = {
        "live_incidents": con.execute("SELECT COUNT(*) FROM reports WHERE status IN ('pending','verified')").fetchone()[0],
        "pending_reports": con.execute("SELECT COUNT(*) FROM reports WHERE status='pending'").fetchone()[0],
        "camera_count": con.execute("SELECT COUNT(*) FROM cameras WHERE enabled=1").fetchone()[0],
        "active_users": con.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0],
    }
    con.close()
    return {"counts": counts, "reports": reports, "cameras": cameras, "users": users, "settings": settings}

@app.put("/api/admin/settings/{key}")
def update_setting(key: str, payload: SettingPayload, request: Request):
    require_admin(request)
    allowed = {
        "app_name","voice_alerts","background_driving_mode","community_reports",
        "camera_layer","traffic_layer","hazard_layer","admin_2fa_required",
        "default_country","camera_warning_mode",
    }
    if key not in allowed:
        raise HTTPException(400, "Unknown setting")
    con = db()
    con.execute(
        "INSERT INTO settings(key,value) VALUES (?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, json.dumps(payload.value)),
    )
    con.commit()
    con.close()
    return {"ok": True}

@app.put("/api/admin/reports/{report_id}/status")
def update_report(report_id: int, payload: StatusPayload, request: Request):
    require_admin(request)
    if payload.status not in {"pending","verified","rejected"}:
        raise HTTPException(400, "Invalid status")
    con = db()
    con.execute("UPDATE reports SET status=? WHERE id=?", (payload.status, report_id))
    con.commit()
    con.close()
    return {"ok": True}

@app.post("/api/admin/cameras")
def add_camera(payload: CameraPayload, request: Request):
    require_admin(request)
    con = db()
    cur = con.execute(
        "INSERT INTO cameras(camera_type,location,speed_limit,confidence,enabled) VALUES (?,?,?,?,?)",
        (payload.camera_type,payload.location,payload.speed_limit,max(0,min(100,payload.confidence)),1 if payload.enabled else 0),
    )
    con.commit()
    cid = cur.lastrowid
    con.close()
    return {"ok": True, "id": cid}

@app.delete("/api/admin/cameras/{camera_id}")
def delete_camera(camera_id: int, request: Request):
    require_admin(request)
    con = db()
    con.execute("DELETE FROM cameras WHERE id=?", (camera_id,))
    con.commit()
    con.close()
    return {"ok": True}

app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
