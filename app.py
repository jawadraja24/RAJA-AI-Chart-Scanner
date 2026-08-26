from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR
DATA_DIR = Path(os.getenv("ROADPULSE_DATA_DIR", str(BASE_DIR / "data")))
DB_FILE = DATA_DIR / "roadpulse.db"
ADMIN_FILE = DATA_DIR / "admin.json"
SECRET_FILE = DATA_DIR / "server_secret.txt"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PBKDF2_ITERATIONS = 600_000

def get_server_secret() -> bytes:
    env_secret = os.getenv("ROADPULSE_SERVER_SECRET")
    if env_secret:
        return env_secret.encode()
    if not SECRET_FILE.exists():
        SECRET_FILE.write_text(secrets.token_hex(32), encoding="utf-8")
    return SECRET_FILE.read_text(encoding="utf-8").strip().encode()


SERVER_SECRET = get_server_secret()

TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "").strip()
TRAFFIC_CACHE_TTL = 50
TRAFFIC_CACHE_MAX = 600
TRAFFIC_TILE_CACHE: dict[tuple[str, int, int, int], tuple[float, bytes]] = {}
TRAFFIC_CACHE_LOCK = threading.Lock()

# Transparent 1x1 PNG returned when traffic is disabled/unavailable.
TRANSPARENT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

def db():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    return con

def has_column(con: sqlite3.Connection, table: str, column: str) -> bool:
    cols = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in cols)

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

    CREATE TABLE IF NOT EXISTS user_accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_salt TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        active INTEGER NOT NULL DEFAULT 1
    );
    """)

    # Safe migrations for deployments that already have an older SQLite DB.
    for table in ("reports", "cameras"):
        if not has_column(con, table, "lat"):
            con.execute(f"ALTER TABLE {table} ADD COLUMN lat REAL")
        if not has_column(con, table, "lng"):
            con.execute(f"ALTER TABLE {table} ADD COLUMN lng REAL")

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
        cur.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
            (k, json.dumps(v)),
        )

    if cur.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0:
        now = int(time.time())
        cur.executemany(
            """INSERT INTO reports(type,location,reported_by,status,created_at,lat,lng)
               VALUES (?,?,?,?,?,?,?)""",
            [
                ("camera", "A7 Hamburg", "demo_user", "verified", now-120, 53.6027, 9.9281),
                ("police", "A24 Hamburg", "demo_user", "verified", now-300, 53.5798, 10.0747),
                ("accident", "Hamburg Zentrum", "demo_user", "verified", now-420, 53.5511, 9.9937),
                ("hazard", "B5 Hamburg", "demo_user", "verified", now-540, 53.5394, 10.0674),
                ("roadwork", "A1 Hamburg", "demo_user", "verified", now-720, 53.4934, 10.0896),
            ],
        )

    if cur.execute("SELECT COUNT(*) FROM cameras").fetchone()[0] == 0:
        cur.executemany(
            """INSERT INTO cameras(camera_type,location,speed_limit,confidence,enabled,lat,lng)
               VALUES (?,?,?,?,?,?,?)""",
            [
                ("fixed", "A7 Hamburg", 100, 96, 1, 53.6027, 9.9281),
                ("mobile", "A24 Hamburg", 80, 82, 1, 53.5798, 10.0747),
            ],
        )

    if cur.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO users(name,role,active) VALUES (?,?,?)",
            [
                ("Owner", "super_admin", 1),
                ("Moderator One", "moderator", 1),
                ("Support One", "support", 1),
            ],
        )

    # Backfill coordinates into older demo rows where possible.
    backfill = {
        "A7 Hamburg": (53.6027, 9.9281),
        "A24 Berlin": (52.5200, 13.4050),
        "A24 Hamburg": (53.5798, 10.0747),
        "A9 Munich": (48.1351, 11.5820),
        "B1 Cologne": (50.9375, 6.9603),
        "A3 Frankfurt": (50.1109, 8.6821),
    }
    for location, (lat, lng) in backfill.items():
        con.execute(
            "UPDATE reports SET lat=COALESCE(lat,?), lng=COALESCE(lng,?) WHERE location=?",
            (lat, lng, location),
        )
        con.execute(
            "UPDATE cameras SET lat=COALESCE(lat,?), lng=COALESCE(lng,?) WHERE location=?",
            (lat, lng, location),
        )

    con.commit()
    con.close()

init_db()

app = FastAPI(title="RoadPulse AI API")

class PasswordPayload(BaseModel):
    password: str

class UserRegisterPayload(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLoginPayload(BaseModel):
    email: EmailStr
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
    lat: float | None = None
    lng: float | None = None

class ReportPayload(BaseModel):
    type: str
    lat: float
    lng: float
    location: str | None = None

def hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return base64.b64encode(digest).decode("ascii")

def verify_password(password: str, salt_b64: str, expected_b64: str) -> bool:
    salt = base64.b64decode(salt_b64)
    actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_b64)

def verify_admin_password(password: str) -> bool:
    env_password = os.getenv("ROADPULSE_ADMIN_PASSWORD")
    if env_password:
        return hmac.compare_digest(password, env_password)

    if not ADMIN_FILE.exists():
        return False
    data = json.loads(ADMIN_FILE.read_text(encoding="utf-8"))
    salt = base64.b64decode(data["salt"])
    expected = base64.b64decode(data["hash"])
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        int(data.get("iterations", PBKDF2_ITERATIONS)),
    )
    return hmac.compare_digest(expected, actual)

def make_session(kind: str, subject: str, ttl_seconds: int) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{kind}|{subject}|{exp}|{secrets.token_urlsafe(16)}".encode()
    sig = hmac.new(SERVER_SECRET, payload, hashlib.sha256).digest()
    p = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    s = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return p + "." + s

def b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def parse_session(token: str, expected_kind: str) -> str:
    if not token or "." not in token:
        raise HTTPException(401, "Login required")
    try:
        p64, s64 = token.split(".", 1)
        payload = b64d(p64)
        sig = b64d(s64)
        expected = hmac.new(SERVER_SECRET, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError
        kind, subject, exp, _nonce = payload.decode().split("|", 3)
        if kind != expected_kind or int(exp) < int(time.time()):
            raise ValueError
        return subject
    except Exception:
        raise HTTPException(401, "Invalid or expired session")

def require_admin(request: Request):
    return parse_session(request.cookies.get("roadpulse_admin", ""), "admin")

def require_user(request: Request) -> int:
    subject = parse_session(request.cookies.get("roadpulse_user", ""), "user")
    return int(subject)

def get_setting(key: str, default: Any = None) -> Any:
    con = db()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return json.loads(row["value"]) if row else default

@app.get("/api/status")
def public_status():
    return {"ok": True, "app": "RoadPulse AI"}

# --------------------------
# User authentication
# --------------------------

@app.post("/api/auth/register")
def register(payload: UserRegisterPayload, response: Response):
    name = payload.name.strip()
    email = payload.email.lower().strip()
    if len(name) < 2:
        raise HTTPException(400, "Name is too short")
    if len(payload.password) < 6:
        raise HTTPException(400, "Use at least 6 characters")

    salt = os.urandom(16)
    con = db()
    try:
        cur = con.execute(
            """INSERT INTO user_accounts(name,email,password_salt,password_hash,created_at,active)
               VALUES (?,?,?,?,?,1)""",
            (
                name,
                email,
                base64.b64encode(salt).decode("ascii"),
                hash_password(payload.password, salt),
                int(time.time()),
            ),
        )
        con.commit()
    except sqlite3.IntegrityError:
        con.close()
        raise HTTPException(409, "Email already registered")

    user_id = cur.lastrowid
    con.close()
    token = make_session("user", str(user_id), 30 * 24 * 60 * 60)
    response.set_cookie(
        "roadpulse_user",
        token,
        httponly=True,
        secure=os.getenv("ROADPULSE_SECURE_COOKIE", "1") == "1",
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )
    return {"ok": True, "user": {"id": user_id, "name": name, "email": email}}

@app.post("/api/auth/login")
def user_login(payload: UserLoginPayload, response: Response):
    email = payload.email.lower().strip()
    con = db()
    row = con.execute(
        "SELECT * FROM user_accounts WHERE email=? AND active=1", (email,)
    ).fetchone()
    con.close()

    if not row or not verify_password(
        payload.password, row["password_salt"], row["password_hash"]
    ):
        raise HTTPException(401, "Invalid email or password")

    token = make_session("user", str(row["id"]), 30 * 24 * 60 * 60)
    response.set_cookie(
        "roadpulse_user",
        token,
        httponly=True,
        secure=os.getenv("ROADPULSE_SECURE_COOKIE", "1") == "1",
        samesite="lax",
        max_age=30 * 24 * 60 * 60,
    )
    return {
        "ok": True,
        "user": {"id": row["id"], "name": row["name"], "email": row["email"]},
    }

@app.post("/api/auth/logout")
def user_logout(response: Response):
    response.delete_cookie("roadpulse_user")
    return {"ok": True}

@app.get("/api/auth/me")
def user_me(request: Request):
    user_id = require_user(request)
    con = db()
    row = con.execute(
        "SELECT id,name,email FROM user_accounts WHERE id=? AND active=1",
        (user_id,),
    ).fetchone()
    con.close()
    if not row:
        raise HTTPException(401, "User not found")
    return {"user": dict(row)}

# --------------------------
# Public/live app data
# --------------------------

@app.get("/api/map-data")
def map_data(request: Request):
    require_user(request)

    con = db()
    reports = [
        dict(r)
        for r in con.execute(
            """SELECT id,type,location,status,created_at,lat,lng
               FROM reports
               WHERE status='verified' AND lat IS NOT NULL AND lng IS NOT NULL
               ORDER BY created_at DESC
               LIMIT 300"""
        ).fetchall()
    ]

    cameras = []
    if get_setting("camera_layer", True):
        cameras = [
            dict(r)
            for r in con.execute(
                """SELECT id,camera_type,location,speed_limit,confidence,lat,lng
                   FROM cameras
                   WHERE enabled=1 AND lat IS NOT NULL AND lng IS NOT NULL
                   ORDER BY id DESC
                   LIMIT 300"""
            ).fetchall()
        ]

    con.close()
    return {
        "reports": reports,
        "cameras": cameras,
        "settings": {
            "community_reports": get_setting("community_reports", True),
            "camera_layer": get_setting("camera_layer", True),
            "traffic_layer": get_setting("traffic_layer", True),
            "hazard_layer": get_setting("hazard_layer", True),
            "camera_warning_mode": get_setting("camera_warning_mode", "country_compliance"),
            "traffic_available": bool(TOMTOM_API_KEY),
        },
    }

@app.post("/api/reports")
def create_report(payload: ReportPayload, request: Request):
    user_id = require_user(request)
    allowed_types = {"camera", "police", "accident", "hazard", "roadwork", "traffic"}
    report_type = payload.type.lower().strip()
    if report_type not in allowed_types:
        raise HTTPException(400, "Unsupported report type")

    if not get_setting("community_reports", True):
        raise HTTPException(403, "Community reports are disabled")

    if not (-90 <= payload.lat <= 90 and -180 <= payload.lng <= 180):
        raise HTTPException(400, "Invalid coordinates")

    location = (payload.location or "Current GPS location").strip()[:160]
    con = db()
    user = con.execute(
        "SELECT email FROM user_accounts WHERE id=?", (user_id,)
    ).fetchone()
    reporter = user["email"] if user else f"user_{user_id}"

    cur = con.execute(
        """INSERT INTO reports(type,location,reported_by,status,created_at,lat,lng)
           VALUES (?,?,?,?,?,?,?)""",
        (
            report_type,
            location,
            reporter,
            "pending",
            int(time.time()),
            payload.lat,
            payload.lng,
        ),
    )
    con.commit()
    report_id = cur.lastrowid
    con.close()
    return {"ok": True, "id": report_id, "status": "pending"}


# --------------------------
# Real-time traffic tiles
# --------------------------

def _validate_tile(z: int, x: int, y: int) -> None:
    if not (0 <= z <= 22):
        raise HTTPException(400, "Invalid zoom")
    max_index = (1 << z) - 1
    if not (0 <= x <= max_index and 0 <= y <= max_index):
        raise HTTPException(400, "Invalid tile coordinates")

def _traffic_upstream_url(kind: str, z: int, x: int, y: int) -> str:
    if kind == "flow":
        return (
            f"https://api.tomtom.com/maps/orbis/traffic/flow/raster/tile/"
            f"{z}/{x}/{y}?apiVersion=2&style=light&tileSize=256"
        )
    if kind == "incidents":
        return (
            f"https://api.tomtom.com/maps/orbis/traffic/incidents/raster/tile/"
            f"{z}/{x}/{y}?apiVersion=2&style=light&tileSize=256"
        )
    raise HTTPException(400, "Unknown traffic layer")

def _get_cached_traffic_tile(kind: str, z: int, x: int, y: int) -> bytes | None:
    cache_key = (kind, z, x, y)
    now = time.time()
    with TRAFFIC_CACHE_LOCK:
        item = TRAFFIC_TILE_CACHE.get(cache_key)
        if item and item[0] > now:
            return item[1]
        if item:
            TRAFFIC_TILE_CACHE.pop(cache_key, None)
    return None

def _put_cached_traffic_tile(kind: str, z: int, x: int, y: int, data: bytes) -> None:
    cache_key = (kind, z, x, y)
    with TRAFFIC_CACHE_LOCK:
        if len(TRAFFIC_TILE_CACHE) >= TRAFFIC_CACHE_MAX:
            # Remove the oldest-expiring entries first.
            oldest = sorted(
                TRAFFIC_TILE_CACHE.items(),
                key=lambda item: item[1][0]
            )[: max(1, TRAFFIC_CACHE_MAX // 10)]
            for key, _value in oldest:
                TRAFFIC_TILE_CACHE.pop(key, None)
        TRAFFIC_TILE_CACHE[cache_key] = (time.time() + TRAFFIC_CACHE_TTL, data)

def _fetch_traffic_tile(kind: str, z: int, x: int, y: int) -> bytes:
    cached = _get_cached_traffic_tile(kind, z, x, y)
    if cached is not None:
        return cached

    url = _traffic_upstream_url(kind, z, x, y)
    req = urllib.request.Request(
        url,
        headers={
            "TomTom-Api-Key": TOMTOM_API_KEY,
            "TomTom-Api-Version": "2",
            "Accept": "image/png",
            "User-Agent": "RoadPulseAI/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as upstream:
            data = upstream.read()
            content_type = upstream.headers.get("Content-Type", "")
            if upstream.status != 200 or "image/png" not in content_type:
                return TRANSPARENT_PNG
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
        return TRANSPARENT_PNG

    _put_cached_traffic_tile(kind, z, x, y, data)
    return data

def _traffic_tile_response(kind: str, z: int, x: int, y: int, request: Request) -> Response:
    require_user(request)
    _validate_tile(z, x, y)

    if not get_setting("traffic_layer", True) or not TOMTOM_API_KEY:
        return Response(
            content=TRANSPARENT_PNG,
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=30"},
        )

    data = _fetch_traffic_tile(kind, z, x, y)
    return Response(
        content=data,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=45",
            "X-RoadPulse-Traffic": "tomtom-orbis-v2",
        },
    )

@app.get("/api/traffic/flow/{z}/{x}/{y}")
def traffic_flow_tile(z: int, x: int, y: int, request: Request):
    return _traffic_tile_response("flow", z, x, y, request)

@app.get("/api/traffic/incidents/{z}/{x}/{y}")
def traffic_incident_tile(z: int, x: int, y: int, request: Request):
    return _traffic_tile_response("incidents", z, x, y, request)

@app.get("/api/traffic/status")
def traffic_status(request: Request):
    require_user(request)
    return {
        "configured": bool(TOMTOM_API_KEY),
        "enabled": bool(get_setting("traffic_layer", True)),
        "provider": "TomTom Orbis Traffic v2" if TOMTOM_API_KEY else None,
        "refresh_seconds": 60,
    }

# --------------------------
# Hidden Admin
# --------------------------

@app.post("/api/admin/login")
def admin_login(payload: PasswordPayload, response: Response):
    if not verify_admin_password(payload.password):
        raise HTTPException(401, "Invalid credentials")
    response.set_cookie(
        "roadpulse_admin",
        make_session("admin", "owner", 8 * 60 * 60),
        httponly=True,
        secure=os.getenv("ROADPULSE_SECURE_COOKIE", "1") == "1",
        samesite="strict",
        max_age=8 * 60 * 60,
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
    reports = [dict(r) for r in con.execute(
        "SELECT * FROM reports ORDER BY created_at DESC LIMIT 100"
    ).fetchall()]
    cameras = [dict(r) for r in con.execute(
        "SELECT * FROM cameras ORDER BY id DESC LIMIT 100"
    ).fetchall()]
    users = [dict(r) for r in con.execute(
        "SELECT * FROM users ORDER BY id"
    ).fetchall()]
    app_users = [dict(r) for r in con.execute(
        "SELECT id,name,email,active,created_at FROM user_accounts ORDER BY id DESC LIMIT 100"
    ).fetchall()]
    settings = {
        r["key"]: json.loads(r["value"])
        for r in con.execute("SELECT key,value FROM settings")
    }
    counts = {
        "live_incidents": con.execute(
            "SELECT COUNT(*) FROM reports WHERE status IN ('pending','verified')"
        ).fetchone()[0],
        "pending_reports": con.execute(
            "SELECT COUNT(*) FROM reports WHERE status='pending'"
        ).fetchone()[0],
        "camera_count": con.execute(
            "SELECT COUNT(*) FROM cameras WHERE enabled=1"
        ).fetchone()[0],
        "active_users": con.execute(
            "SELECT COUNT(*) FROM user_accounts WHERE active=1"
        ).fetchone()[0],
    }
    con.close()
    return {
        "counts": counts,
        "reports": reports,
        "cameras": cameras,
        "users": users,
        "app_users": app_users,
        "settings": settings,
    }

@app.put("/api/admin/settings/{key}")
def update_setting(key: str, payload: SettingPayload, request: Request):
    require_admin(request)
    allowed = {
        "app_name", "voice_alerts", "background_driving_mode", "community_reports",
        "camera_layer", "traffic_layer", "hazard_layer", "admin_2fa_required",
        "default_country", "camera_warning_mode",
    }
    if key not in allowed:
        raise HTTPException(400, "Unknown setting")

    con = db()
    con.execute(
        """INSERT INTO settings(key,value) VALUES (?,?)
           ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
        (key, json.dumps(payload.value)),
    )
    con.commit()
    con.close()
    return {"ok": True}

@app.put("/api/admin/reports/{report_id}/status")
def update_report(report_id: int, payload: StatusPayload, request: Request):
    require_admin(request)
    if payload.status not in {"pending", "verified", "rejected"}:
        raise HTTPException(400, "Invalid status")
    con = db()
    con.execute(
        "UPDATE reports SET status=? WHERE id=?",
        (payload.status, report_id),
    )
    con.commit()
    con.close()
    return {"ok": True}

@app.post("/api/admin/cameras")
def add_camera(payload: CameraPayload, request: Request):
    require_admin(request)
    con = db()
    cur = con.execute(
        """INSERT INTO cameras(camera_type,location,speed_limit,confidence,enabled,lat,lng)
           VALUES (?,?,?,?,?,?,?)""",
        (
            payload.camera_type,
            payload.location,
            payload.speed_limit,
            max(0, min(100, payload.confidence)),
            1 if payload.enabled else 0,
            payload.lat,
            payload.lng,
        ),
    )
    con.commit()
    camera_id = cur.lastrowid
    con.close()
    return {"ok": True, "id": camera_id}

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
