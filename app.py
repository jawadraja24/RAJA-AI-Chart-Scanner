from __future__ import annotations

import io
import json
import math
import os
import secrets
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from flask import Flask, Response, jsonify, redirect, request, send_from_directory
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

try:
    import psycopg
except Exception:
    psycopg = None

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
DATA_DIR = Path(os.environ.get("RAJA_SCANNER_DATA_DIR", str(APP_DIR / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
STORE_FILE = DATA_DIR / "scanner_store.json"
SHARED_DIR = DATA_DIR / "shared_charts"
SHARED_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = (os.environ.get("DATABASE_URL") or os.environ.get("RAJA_DATABASE_URL") or "").strip()
ADMIN_PASSWORD = (os.environ.get("RAJA_SCANNER_ADMIN_PASSWORD") or "3250").strip()
QUOTEX_URL = (os.environ.get("RAJA_SCANNER_QUOTEX_URL") or "https://broker-qx.pro/sign-up/?lid=2209395").strip()
POCKET_URL = (os.environ.get("RAJA_SCANNER_POCKET_URL") or "https://u3.shortink.io/smart/txvQPFrBEgdZmL").strip()
MONTHLY_PRICE_EUR = float(os.environ.get("RAJA_SCANNER_MONTHLY_PRICE_EUR", "19.99"))
SUPPORT_URL = (os.environ.get("RAJA_SCANNER_SUPPORT_URL") or "https://t.me/RAJASIGNALAIPREMIUM").strip()
MAX_UPLOAD_BYTES = max(2, min(16, int(os.environ.get("RAJA_SCANNER_MAX_UPLOAD_MB", "8")))) * 1024 * 1024

BROKER_DATA = {'Quotex': {'CryptoLive': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'LTC-USD', 'XRP-USD', 'ADA-USD', 'DOGE-USD'], 'CryptoOTC': ['Zcash (OTC)', 'Chainlink (OTC)', 'Bitcoin (OTC)', 'Binance Coin (OTC)', 'Ethereum (OTC)', 'Bitcoin Cash (OTC)', 'Cosmos (OTC)', 'Ethereum Classic (OTC)', 'Axie Infinity (OTC)', 'Trump (OTC)', 'Dash (OTC)', 'Solana (OTC)', 'Toncoin (OTC)', 'Litecoin (OTC)', 'Avalanche (OTC)', 'Polkadot (OTC)', 'Ripple (OTC)'], 'ForexLive': ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'NZD/USD', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'EUR/AUD', 'GBP/AUD', 'CAD/JPY', 'EUR/CAD', 'GBP/CAD', 'NZD/JPY', 'AUD/NZD', 'EUR/CHF', 'GBP/CHF', 'XAUUSD'], 'ForexOTC': ['USD/BRL (OTC)', 'NZD/CHF (OTC)', 'NZD/JPY (OTC)', 'USD/COP (OTC)', 'USD/MXN (OTC)', 'AUD/NZD (OTC)', 'USD/BDT (OTC)', 'USD/DZD (OTC)', 'USD/NGN (OTC)', 'USD/PHP (OTC)', 'USD/PKR (OTC)', 'USD/ZAR (OTC)', 'USD/INR (OTC)', 'USD/EGP (OTC)', 'USD/IDR (OTC)', 'USD/ARS (OTC)', 'GBP/NZD (OTC)', 'EUR/NZD (OTC)', 'NZD/USD (OTC)', 'NZD/CAD (OTC)', 'CAD/CHF (OTC)']}, 'PocketOption': {'CryptoLive': ['BTC-USD', 'ETH-USD', 'SOL-USD', 'LTC-USD', 'XRP-USD', 'ADA-USD', 'DOGE-USD'], 'ForexLive': ['EUR/USD', 'GBP/USD', 'USD/JPY', 'AUD/USD', 'USD/CAD', 'USD/CHF', 'NZD/USD', 'EUR/GBP', 'EUR/JPY', 'GBP/JPY', 'AUD/JPY', 'EUR/AUD', 'GBP/AUD', 'CAD/JPY', 'EUR/CAD', 'GBP/CAD', 'NZD/JPY', 'AUD/NZD', 'EUR/CHF', 'GBP/CHF', 'XAUUSD'], 'ForexOTC': ['EUR/USD (OTC)', 'GBP/USD (OTC)', 'USD/JPY (OTC)', 'AUD/USD (OTC)', 'USD/CAD (OTC)', 'USD/CHF (OTC)', 'EUR/JPY (OTC)', 'GBP/JPY (OTC)', 'AUD/JPY (OTC)', 'CAD/JPY (OTC)', 'EUR/CHF (OTC)', 'EUR/GBP (OTC)', 'AUD/CAD (OTC)', 'AUD/CHF (OTC)', 'CAD/CHF (OTC)', 'NZD/JPY (OTC)', 'AUD/NZD (OTC)', 'EUR/NZD (OTC)', 'GBP/AUD (OTC)', 'CHF/JPY (OTC)', 'USD/MXN (OTC)', 'USD/BRL (OTC)', 'USD/INR (OTC)', 'USD/SGD (OTC)', 'USD/CNH (OTC)', 'USD/IDR (OTC)', 'USD/PHP (OTC)', 'USD/MYR (OTC)', 'USD/COP (OTC)', 'EUR/TRY (OTC)'], 'CryptoOTC': ['BNB (OTC)', 'Polkadot (OTC)', 'Ethereum (OTC)', 'Toncoin (OTC)', 'Cardano (OTC)', 'Polygon (OTC)', 'TRON (OTC)', 'Avalanche (OTC)', 'Bitcoin (OTC)', 'Bitcoin ETF (OTC)', 'Solana (OTC)', 'Chainlink (OTC)', 'Litecoin (OTC)', 'Dogecoin (OTC)'], 'StocksOTC': ['Apple (OTC)', 'American Express (OTC)', 'Boeing Company (OTC)', 'Cisco (OTC)', 'Facebook Inc (OTC)', 'Intel (OTC)', 'Johnson & Johnson (OTC)', "McDonald's (OTC)", 'Microsoft (OTC)', 'Pfizer Inc (OTC)', 'Tesla (OTC)', 'ExxonMobil (OTC)', 'Advanced Micro Devices (OTC)']}}

Image.MAX_IMAGE_PIXELS = 25_000_000

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

_store_lock = threading.RLock()


def _now() -> int:
    return int(time.time())


def _norm_user(value: Any) -> str:
    return str(value or "").strip().lower()[:160]


def _norm_device(value: Any) -> str:
    return str(value or "").strip()[:180]


def _db_connect():
    if not DATABASE_URL or psycopg is None:
        return None
    return psycopg.connect(DATABASE_URL, connect_timeout=10)


def _empty_store() -> dict[str, Any]:
    return {
        "licenses": {},
        "trial_claims": {},
        "requests": [],
        "scans": [],
        "next_request_id": 1,
        "next_scan_id": 1,
    }


def _load_file_store() -> dict[str, Any]:
    with _store_lock:
        if not STORE_FILE.exists():
            data = _empty_store()
            STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return data
        try:
            data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("bad store")
            base = _empty_store()
            base.update(data)
            return base
        except Exception:
            backup = STORE_FILE.with_name(f"scanner_store.corrupt.{_now()}.json")
            try:
                STORE_FILE.replace(backup)
            except Exception:
                pass
            data = _empty_store()
            STORE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            return data


def _save_file_store(data: dict[str, Any]) -> None:
    with _store_lock:
        tmp = STORE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(STORE_FILE)


def init_store() -> None:
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raja_scanner_licenses (
                        license_key TEXT PRIMARY KEY,
                        active BOOLEAN NOT NULL DEFAULT TRUE,
                        user_id TEXT,
                        device_id TEXT,
                        device_label TEXT,
                        session_token TEXT,
                        plan TEXT,
                        created_at BIGINT,
                        expires_at BIGINT,
                        last_verified_at BIGINT,
                        last_login_at BIGINT
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raja_scanner_trial_claims (
                        claim_type TEXT NOT NULL,
                        claim_value TEXT NOT NULL,
                        license_key TEXT,
                        created_at BIGINT,
                        PRIMARY KEY (claim_type, claim_value)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raja_scanner_access_requests (
                        request_id BIGSERIAL PRIMARY KEY,
                        request_type TEXT,
                        broker TEXT,
                        user_id TEXT,
                        deposit_amount DOUBLE PRECISION,
                        contact TEXT,
                        payment_ref TEXT,
                        status TEXT,
                        license_key TEXT,
                        created_at BIGINT,
                        updated_at BIGINT
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raja_scanner_scans (
                        scan_id BIGSERIAL PRIMARY KEY,
                        user_id TEXT,
                        created_at BIGINT,
                        broker TEXT,
                        pair TEXT,
                        timeframe TEXT,
                        bias TEXT,
                        confidence DOUBLE PRECISION,
                        quality DOUBLE PRECISION,
                        payload TEXT
                    )
                """)
        return
    _load_file_store()


def get_license(key: str) -> dict[str, Any] | None:
    key = str(key or "").strip()
    if not key:
        return None
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT active,user_id,device_id,device_label,session_token,plan,created_at,expires_at,last_verified_at,last_login_at
                    FROM raja_scanner_licenses WHERE license_key=%s LIMIT 1
                """, (key,))
                row = cur.fetchone()
        if not row:
            return None
        fields = ["active","user_id","device_id","device_label","session_token","plan","created_at","expires_at","last_verified_at","last_login_at"]
        return dict(zip(fields, row))
    return _load_file_store()["licenses"].get(key)


def save_license(key: str, record: dict[str, Any]) -> None:
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO raja_scanner_licenses
                    (license_key,active,user_id,device_id,device_label,session_token,plan,created_at,expires_at,last_verified_at,last_login_at)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT(license_key) DO UPDATE SET
                      active=EXCLUDED.active,user_id=EXCLUDED.user_id,device_id=EXCLUDED.device_id,
                      device_label=EXCLUDED.device_label,session_token=EXCLUDED.session_token,plan=EXCLUDED.plan,
                      created_at=EXCLUDED.created_at,expires_at=EXCLUDED.expires_at,
                      last_verified_at=EXCLUDED.last_verified_at,last_login_at=EXCLUDED.last_login_at
                """, (
                    key, bool(record.get("active", True)), record.get("user_id"), record.get("device_id"),
                    record.get("device_label"), record.get("session_token"), record.get("plan"),
                    record.get("created_at"), record.get("expires_at"), record.get("last_verified_at"), record.get("last_login_at")
                ))
        return
    data = _load_file_store()
    data["licenses"][key] = record
    _save_file_store(data)


def delete_license(key: str) -> None:
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM raja_scanner_licenses WHERE license_key=%s", (key,))
        return
    data = _load_file_store()
    data["licenses"].pop(key, None)
    _save_file_store(data)


def list_licenses() -> list[dict[str, Any]]:
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT license_key,active,user_id,device_id,device_label,plan,created_at,expires_at,last_verified_at,last_login_at
                    FROM raja_scanner_licenses ORDER BY created_at DESC NULLS LAST
                """)
                rows = cur.fetchall()
        return [dict(zip(["key","active","user_id","device_id","device_label","plan","created_at","expires_at","last_verified_at","last_login_at"], r)) for r in rows]
    data = _load_file_store()
    out = []
    for key, rec in data["licenses"].items():
        x = dict(rec)
        x["key"] = key
        out.append(x)
    return sorted(out, key=lambda x: int(x.get("created_at") or 0), reverse=True)


def get_trial_claim(claim_type: str, claim_value: str) -> dict[str, Any] | None:
    claim_type = str(claim_type or "").strip().lower()
    claim_value = _norm_user(claim_value) if claim_type == "user" else _norm_device(claim_value)
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT license_key,created_at FROM raja_scanner_trial_claims WHERE claim_type=%s AND claim_value=%s", (claim_type, claim_value))
                row = cur.fetchone()
        return {"license_key": row[0], "created_at": row[1]} if row else None
    return _load_file_store()["trial_claims"].get(f"{claim_type}:{claim_value}")


def set_trial_claim(claim_type: str, claim_value: str, key: str) -> None:
    claim_type = str(claim_type or "").strip().lower()
    claim_value = _norm_user(claim_value) if claim_type == "user" else _norm_device(claim_value)
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO raja_scanner_trial_claims(claim_type,claim_value,license_key,created_at)
                    VALUES(%s,%s,%s,%s) ON CONFLICT(claim_type,claim_value) DO NOTHING
                """, (claim_type, claim_value, key, _now()))
        return
    data = _load_file_store()
    data["trial_claims"].setdefault(f"{claim_type}:{claim_value}", {"license_key": key, "created_at": _now()})
    _save_file_store(data)


def create_license(user_id: str, plan: str, duration_days: float | None = None) -> tuple[str, dict[str, Any]]:
    user_id = _norm_user(user_id)
    plan = str(plan or "VIP").strip().upper()[:50]
    now = _now()
    key = "RAJA-SCAN-" + secrets.token_hex(5).upper()
    while get_license(key):
        key = "RAJA-SCAN-" + secrets.token_hex(5).upper()
    expires = None
    if duration_days and duration_days > 0:
        expires = now + int(float(duration_days) * 86400)
    rec = {
        "active": True,
        "user_id": user_id,
        "device_id": None,
        "device_label": None,
        "session_token": None,
        "plan": plan,
        "created_at": now,
        "expires_at": expires,
        "last_verified_at": None,
        "last_login_at": None,
    }
    save_license(key, rec)
    return key, rec


def add_access_request(payload: dict[str, Any]) -> dict[str, Any]:
    now = _now()
    req_type = str(payload.get("request_type") or "affiliate").strip().lower()
    broker = str(payload.get("broker") or "").strip()[:40]
    user_id = _norm_user(payload.get("user_id"))
    contact = str(payload.get("contact") or "").strip()[:180]
    payment_ref = str(payload.get("payment_ref") or "").strip()[:180]
    try:
        deposit_amount = float(payload.get("deposit_amount") or 0)
    except Exception:
        deposit_amount = 0.0
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO raja_scanner_access_requests
                    (request_type,broker,user_id,deposit_amount,contact,payment_ref,status,license_key,created_at,updated_at)
                    VALUES(%s,%s,%s,%s,%s,%s,'PENDING',NULL,%s,%s)
                    RETURNING request_id
                """, (req_type, broker, user_id, deposit_amount, contact, payment_ref, now, now))
                rid = cur.fetchone()[0]
        return {"request_id": rid, "status": "PENDING"}
    data = _load_file_store()
    rid = int(data.get("next_request_id") or 1)
    data["next_request_id"] = rid + 1
    row = {
        "request_id": rid, "request_type": req_type, "broker": broker, "user_id": user_id,
        "deposit_amount": deposit_amount, "contact": contact, "payment_ref": payment_ref,
        "status": "PENDING", "license_key": None, "created_at": now, "updated_at": now,
    }
    data["requests"].append(row)
    _save_file_store(data)
    return row


def list_requests() -> list[dict[str, Any]]:
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT request_id,request_type,broker,user_id,deposit_amount,contact,payment_ref,status,license_key,created_at,updated_at
                    FROM raja_scanner_access_requests ORDER BY created_at DESC
                """)
                rows = cur.fetchall()
        keys = ["request_id","request_type","broker","user_id","deposit_amount","contact","payment_ref","status","license_key","created_at","updated_at"]
        return [dict(zip(keys, r)) for r in rows]
    return sorted(_load_file_store()["requests"], key=lambda x: int(x.get("created_at") or 0), reverse=True)


def get_request(request_id: int) -> dict[str, Any] | None:
    for row in list_requests():
        if int(row.get("request_id") or 0) == int(request_id):
            return row
    return None


def update_request(request_id: int, status: str, license_key: str | None = None) -> None:
    now = _now()
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE raja_scanner_access_requests SET status=%s,license_key=%s,updated_at=%s WHERE request_id=%s", (status, license_key, now, request_id))
        return
    data = _load_file_store()
    for row in data["requests"]:
        if int(row.get("request_id") or 0) == int(request_id):
            row["status"] = status
            row["license_key"] = license_key
            row["updated_at"] = now
            break
    _save_file_store(data)


def add_scan(user_id: str, broker: str, pair: str, timeframe: str, result: dict[str, Any]) -> None:
    now = _now()
    payload = json.dumps(result, ensure_ascii=False)
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO raja_scanner_scans(user_id,created_at,broker,pair,timeframe,bias,confidence,quality,payload)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (user_id, now, broker, pair, timeframe, result.get("bias"), result.get("confidence"), result.get("image_quality_score"), payload))
        return
    data = _load_file_store()
    sid = int(data.get("next_scan_id") or 1)
    data["next_scan_id"] = sid + 1
    data["scans"].append({
        "scan_id": sid, "user_id": user_id, "created_at": now, "broker": broker, "pair": pair,
        "timeframe": timeframe, "bias": result.get("bias"), "confidence": result.get("confidence"),
        "quality": result.get("image_quality_score"), "payload": result,
    })
    data["scans"] = data["scans"][-2000:]
    _save_file_store(data)


def list_scans(user_id: str, limit: int = 30) -> list[dict[str, Any]]:
    user_id = _norm_user(user_id)
    if DATABASE_URL and psycopg is not None:
        with _db_connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT scan_id,created_at,broker,pair,timeframe,bias,confidence,quality,payload
                    FROM raja_scanner_scans WHERE lower(user_id)=%s ORDER BY created_at DESC LIMIT %s
                """, (user_id, max(1, min(100, limit))))
                rows = cur.fetchall()
        out = []
        for r in rows:
            try:
                payload = json.loads(r[8])
            except Exception:
                payload = {}
            out.append({"scan_id": r[0], "created_at": r[1], "broker": r[2], "pair": r[3], "timeframe": r[4], "bias": r[5], "confidence": r[6], "quality": r[7], "payload": payload})
        return out
    rows = [x for x in _load_file_store()["scans"] if _norm_user(x.get("user_id")) == user_id]
    rows.sort(key=lambda x: int(x.get("created_at") or 0), reverse=True)
    return rows[:max(1, min(100, limit))]


def _license_expired(rec: dict[str, Any]) -> bool:
    exp = int(rec.get("expires_at") or 0)
    return bool(exp and exp <= _now())


def _session_from_request() -> tuple[str, str, str, str]:
    return (
        str(request.headers.get("X-RAJA-Key") or request.form.get("key") or "").strip(),
        _norm_user(request.headers.get("X-RAJA-User") or request.form.get("user") or ""),
        _norm_device(request.headers.get("X-RAJA-Device") or request.form.get("device") or ""),
        str(request.headers.get("X-RAJA-Token") or request.form.get("session_token") or "").strip(),
    )


def validate_session() -> tuple[dict[str, Any] | None, tuple[dict[str, Any], int] | None]:
    key, user, device, token = _session_from_request()
    if not key or not user or not device or not token:
        return None, ({"status": "error", "message": "Active RAJA Scanner session required."}, 401)
    rec = get_license(key)
    if not rec or not rec.get("active") or _license_expired(rec):
        return None, ({"status": "error", "message": "License invalid, revoked or expired."}, 401)
    if _norm_user(rec.get("user_id")) != user:
        return None, ({"status": "error", "message": "License belongs to another user/UID."}, 403)
    if str(rec.get("device_id") or "") != device or str(rec.get("session_token") or "") != token:
        return None, ({"status": "error", "message": "This session was replaced by a newer device login."}, 409)
    rec["last_verified_at"] = _now()
    save_license(key, rec)
    return rec, None


def _quality_score(rgb: np.ndarray) -> tuple[float, list[str]]:
    """Estimate screenshot readability without punishing large dark chart backgrounds.

    Broker charts contain broad, intentionally smooth/dark regions. A plain mean-gradient
    metric marks those clean screenshots as "blurred", so this version measures contrast,
    edge density and the stronger part of the gradient distribution instead.
    """
    h, w, _ = rgb.shape
    gray = rgb.astype(np.float32).mean(axis=2)
    contrast = float(np.std(gray))

    gx = np.abs(np.diff(gray, axis=1)) if w > 1 else np.zeros((h, 1), dtype=np.float32)
    gy = np.abs(np.diff(gray, axis=0)) if h > 1 else np.zeros((1, w), dtype=np.float32)
    gradients = np.concatenate([gx.ravel(), gy.ravel()]) if gx.size and gy.size else np.array([0.0], dtype=np.float32)

    # Strong-edge percentile is much better for candlestick screenshots than the mean.
    p85 = float(np.percentile(gradients, 85))
    p95 = float(np.percentile(gradients, 95))
    edge_density = float(np.mean(gradients > 10.0))

    size_score = min(1.0, min(w / 700.0, h / 420.0))
    contrast_score = min(1.0, contrast / 25.0)
    edge_score = min(1.0, (0.45 * p85 + 0.55 * p95) / 12.0)
    density_score = min(1.0, edge_density / 0.05)

    score = 100.0 * (
        0.28 * size_score
        + 0.28 * contrast_score
        + 0.30 * edge_score
        + 0.14 * density_score
    )

    notes: list[str] = []
    if size_score < 0.60:
        notes.append("Image resolution is low; use a clearer full chart screenshot.")
    if contrast_score < 0.35:
        notes.append("Chart contrast is weak; candles may be hard to separate.")
    # Only warn for blur when both edge strength and edge density are genuinely poor.
    if edge_score < 0.20 and density_score < 0.24:
        notes.append("Image looks soft/blurred; hold the camera steady or upload a screenshot.")

    return round(max(0.0, min(100.0, score)), 1), notes


def _group_columns(active: np.ndarray) -> list[tuple[int, int]]:
    groups = []
    start = None
    for i, on in enumerate(active.tolist()):
        if on and start is None:
            start = i
        elif not on and start is not None:
            groups.append((start, i - 1))
            start = None
    if start is not None:
        groups.append((start, len(active) - 1))
    return groups



def _connected_color_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    """Return 8-connected component boxes as (left,right,top,bottom,pixels).

    The old V9 counter projected every coloured pixel onto the X axis. On Pocket
    Option mobile screenshots, wide BUY/SELL/sentiment UI bands could make many
    separate candles look like one huge X component. This run-length component
    labeller keeps candles separate in 2D without adding OpenCV/scipy dependencies.
    """
    h, w = mask.shape
    parent: list[int] = []
    runs: list[tuple[int, int, int, int]] = []
    prev: list[tuple[int, int, int]] = []

    def make_label() -> int:
        parent.append(len(parent))
        return len(parent) - 1

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for y in range(h):
        xs = np.flatnonzero(mask[y])
        curr: list[tuple[int, int, int]] = []
        if xs.size:
            run_start = run_last = int(xs[0])
            for xv in xs[1:]:
                x = int(xv)
                if x == run_last + 1:
                    run_last = x
                else:
                    curr.append((run_start, run_last, make_label()))
                    run_start = run_last = x
            curr.append((run_start, run_last, make_label()))

        # Runs are X-sorted. Connect current row to overlapping/adjacent previous runs.
        pi = 0
        for left, right, label in curr:
            while pi < len(prev) and prev[pi][1] < left - 1:
                pi += 1
            pj = pi
            while pj < len(prev) and prev[pj][0] <= right + 1:
                p_left, p_right, p_label = prev[pj]
                if left <= p_right + 1 and right >= p_left - 1:
                    union(label, p_label)
                pj += 1
            runs.append((y, left, right, label))
        prev = curr

    boxes: dict[int, list[int]] = {}
    for y, left, right, label in runs:
        root = find(label)
        box = boxes.setdefault(root, [w, -1, h, -1, 0])
        box[0] = min(box[0], left)
        box[1] = max(box[1], right)
        box[2] = min(box[2], y)
        box[3] = max(box[3], y)
        box[4] += right - left + 1
    return [tuple(v) for v in boxes.values()]


def _regular_candle_run(candles: list[dict[str, Any]], cw: int) -> list[dict[str, Any]]:
    """Keep the densest regularly-spaced candle sequence and discard UI glyphs.

    Broker candles are almost equally spaced horizontally. Price text/icons can also
    be red/green, but they normally appear as tiny duplicate components or as an
    isolated group beyond a large gap. This filter removes those without inventing
    missing candles.
    """
    if len(candles) < 6:
        return candles

    candles = sorted(candles, key=lambda c: float(c["x"]))
    xs = np.array([float(c["x"]) for c in candles], dtype=float)
    gaps = np.diff(xs)
    useful = gaps[(gaps >= max(3.0, cw * 0.008)) & (gaps <= cw * 0.14)]
    if useful.size < 3:
        return candles

    spacing = float(np.median(useful))

    # If two candidates are much closer than the normal candle spacing, they are
    # usually split wick/body fragments or coloured UI text. Keep the stronger one.
    min_gap = max(3.0, spacing * 0.72)
    de_duped: list[dict[str, Any]] = []
    for c in candles:
        if de_duped and float(c["x"]) - float(de_duped[-1]["x"]) < min_gap:
            if float(c.get("pixels") or 0) > float(de_duped[-1].get("pixels") or 0):
                de_duped[-1] = c
        else:
            de_duped.append(c)

    if len(de_duped) < 6:
        return de_duped

    xs = np.array([float(c["x"]) for c in de_duped], dtype=float)
    gaps = np.diff(xs)
    useful = gaps[(gaps >= max(3.0, cw * 0.008)) & (gaps <= cw * 0.14)]
    spacing = float(np.median(useful)) if useful.size else spacing
    split_gap = max(18.0, cw * 0.078, spacing * 1.60)

    runs: list[list[dict[str, Any]]] = []
    run_start = 0
    for i, gap in enumerate(gaps):
        if gap > split_gap:
            runs.append(de_duped[run_start:i + 1])
            run_start = i + 1
    runs.append(de_duped[run_start:])
    runs.sort(
        key=lambda seq: (len(seq), sum(float(c.get("pixels") or 0) for c in seq)),
        reverse=True,
    )
    best = runs[0]
    return best if len(best) >= 4 else de_duped


def _adaptive_candle_color_masks(chart: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Return bearish/bullish candle masks with phone/theme adaptive colour thresholds.

    This is deterministic computer vision (not an external ML model): it adapts saturation
    and brightness floors to each frame, then combines hue-like channel dominance with
    the older fixed masks. It is intentionally lightweight for Render and older phones.
    """
    rgb = chart.astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    chroma = mx - mn
    sat = chroma / np.maximum(mx, 1.0)
    value = mx / 255.0

    bright = value > 0.16
    sat_sample = sat[bright]
    if sat_sample.size:
        sat_floor = float(np.clip(np.percentile(sat_sample, 42), 0.12, 0.24))
    else:
        sat_floor = 0.16

    # Theme/phone adaptive dominance floors. Purple/blue backgrounds are rejected by
    # requiring a clear red or green/cyan dominance plus meaningful saturation.
    red_dom = r - np.maximum(g, b * 0.84)
    green_dom = g - r
    cyan_dom = ((g + b) * 0.5) - r
    red_pos = red_dom[(red_dom > 0) & bright & (sat >= sat_floor)]
    green_pos = green_dom[(green_dom > 0) & bright & (sat >= sat_floor * 0.75)]
    red_floor = float(np.clip(np.percentile(red_pos, 35), 8, 18)) if red_pos.size else 11.0
    green_floor = float(np.clip(np.percentile(green_pos, 30), 5, 14)) if green_pos.size else 7.0

    adaptive_red = (value >= 0.22) & (sat >= sat_floor) & (red_dom >= red_floor) & (r >= g + 5)
    adaptive_green = (value >= 0.19) & (sat >= sat_floor * 0.72) & (green_dom >= green_floor) & (g >= b - 58)
    adaptive_cyan = (value >= 0.22) & (sat >= sat_floor * 0.65) & (cyan_dom >= 10) & (g >= r + 6) & (b >= r - 8)

    # Preserve proven V9/V10 masks as a fallback for clean screenshots.
    fixed_red = (r > 84) & ((r - g) > 16) & ((r - b) > 3)
    fixed_green = (g > 64) & ((g - r) > 10) & ((g - b) > -42)
    fixed_cyan = (g > 88) & (b > 88) & (r < 185) & (((g + b) - 2 * r) > 24)

    red = adaptive_red | fixed_red
    bull = adaptive_green | adaptive_cyan | fixed_green | fixed_cyan
    # Pixels that accidentally satisfy both are ambiguous and are discarded.
    overlap = red & bull
    if overlap.any():
        red = red & ~overlap
        bull = bull & ~overlap

    meta = {
        "sat_floor": round(sat_floor, 3),
        "red_floor": round(red_floor, 1),
        "green_floor": round(green_floor, 1),
        "red_density": round(float(red.mean()), 6),
        "bull_density": round(float(bull.mean()), 6),
    }
    return red, bull, meta


def _detect_candles_in_chart(chart: np.ndarray) -> tuple[list[dict[str, Any]], float, list[str], float, float]:
    """Detect red/green candles with mobile-safe 2D component clustering.

    V9.1 fixes the V9 mobile under-count where 14+ visible Pocket Option candles
    could be reported as 7 because the old X-axis grouping was contaminated by
    wide coloured interface bars. No indicator values are used; geometry remains
    visual-only body/wick estimation.
    """
    ch, cw, _ = chart.shape
    quality, quality_notes = _quality_score(chart)

    # V11 Adaptive Vision Lens: per-frame red/green/cyan calibration.
    red, bull, color_meta = _adaptive_candle_color_masks(chart)
    colored = red | bull

    # Suppress only near-full-width coloured UI bands. 2D components already make
    # normal BUY/SELL buttons harmless because their width is rejected below.
    row_counts = colored.sum(axis=1)
    broad_rows = row_counts > max(80, int(cw * 0.52))
    clean_red = red.copy()
    clean_bull = bull.copy()
    clean_colored = colored.copy()
    if broad_rows.any():
        clean_red[broad_rows, :] = False
        clean_bull[broad_rows, :] = False
        clean_colored[broad_rows, :] = False

    min_pixels = max(14, min(70, int(ch * cw * 0.00020)))
    max_width = max(32, int(cw * 0.080))
    max_height = max(55, int(ch * 0.50))
    seeds: list[dict[str, Any]] = []

    # Label bullish and bearish colours separately so adjacent opposite candles do
    # not merge into one component when their anti-aliased edges touch.
    for direction, mask in ((-1, clean_red), (1, clean_bull)):
        for left, right, top, bottom, pixels in _connected_color_components(mask):
            width = right - left + 1
            height = bottom - top + 1
            if pixels < min_pixels or width > max_width or height < 4 or height > max_height:
                continue
            # Reject flat coloured labels; doji/small bodies are still allowed.
            if width > max(12, int(cw * 0.040)) and height < max(5, int(width * 0.20)):
                continue
            density = float(pixels / max(1, width * height))
            if density < 0.045:
                continue
            seeds.append({
                "left": int(left), "right": int(right), "top": int(top), "bottom": int(bottom),
                "pixels": int(pixels), "dir": int(direction),
            })

    seeds.sort(key=lambda s: (s["left"] + s["right"]) / 2.0)

    # Merge/replace only components centered at effectively the same X position.
    same_x = max(3, int(cw * 0.009))
    de_duped_seeds: list[dict[str, Any]] = []
    for seed in seeds:
        cx = (seed["left"] + seed["right"]) / 2.0
        if de_duped_seeds:
            prev = de_duped_seeds[-1]
            pcx = (prev["left"] + prev["right"]) / 2.0
            if abs(cx - pcx) <= same_x:
                if seed["pixels"] > prev["pixels"]:
                    de_duped_seeds[-1] = seed
                continue
        de_duped_seeds.append(seed)

    candles: list[dict[str, Any]] = []
    for seed in de_duped_seeds:
        left, right = seed["left"], seed["right"]
        top, bottom = seed["top"], seed["bottom"]
        direction = int(seed["dir"])
        width = right - left + 1
        height = bottom - top + 1

        # Expand only locally to recover a wick that may be a thin/disconnected
        # anti-aliased line. Never search the whole column, which could capture UI.
        xpad = max(1, min(3, width // 4))
        ypad = max(5, min(int(ch * 0.07), int(height * 0.65)))
        xl, xr = max(0, left - xpad), min(cw - 1, right + xpad)
        yt, yb = max(0, top - ypad), min(ch - 1, bottom + ypad)
        local = clean_colored[yt:yb + 1, xl:xr + 1]
        ys, _ = np.where(local)
        if ys.size:
            full_top = yt + int(ys.min())
            full_bottom = yt + int(ys.max())
        else:
            full_top, full_bottom = top, bottom

        full_height = max(1, full_bottom - full_top + 1)
        own_mask = clean_bull if direction > 0 else clean_red
        body_block = own_mask[full_top:full_bottom + 1, left:right + 1]
        row_counts_body = body_block.sum(axis=1).astype(np.int32)
        max_row = int(row_counts_body.max()) if row_counts_body.size else 0
        if max_row >= 2:
            body_thr = max(2, int(math.ceil(max_row * 0.50)))
            body_rows = np.where(row_counts_body >= body_thr)[0]
        else:
            body_rows = np.array([], dtype=int)

        if body_rows.size:
            body_top = full_top + int(body_rows.min())
            body_bottom = full_top + int(body_rows.max())
        else:
            body_top, body_bottom = top, bottom

        body_height = max(1, body_bottom - body_top + 1)
        upper_wick = max(0, body_top - full_top)
        lower_wick = max(0, full_bottom - body_bottom)
        range_px = float(max(1, full_height))
        body_ratio = float(body_height / range_px)
        open_y = float(body_bottom if direction > 0 else body_top)
        close_y = float(body_top if direction > 0 else body_bottom)

        candles.append({
            "x": float((left + right) / 2.0),
            "y": float((body_top + body_bottom) / 2.0),
            "top": int(full_top), "bottom": int(full_bottom),
            "body_top": int(body_top), "body_bottom": int(body_bottom),
            "body_height": float(body_height),
            "upper_wick": float(upper_wick), "lower_wick": float(lower_wick),
            "body_ratio": body_ratio, "open_y": open_y, "close_y": close_y,
            "dir": direction, "pixels": int(seed["pixels"]), "range": range_px,
        })

    candles = _regular_candle_run(candles, cw)[-80:]
    if len(candles) >= 2:
        span = float((candles[-1]["x"] - candles[0]["x"]) / max(cw, 1))
    else:
        span = 0.0
    density = float(colored.mean())
    return candles, quality, quality_notes, max(0.0, span), density

def _candidate_chart_regions(arr: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """Return desktop + mobile chart crops; the engine scores and chooses the best one."""
    h, w, _ = arr.shape
    portrait = h > w * 1.12
    specs: list[tuple[str, float, float, float, float]]
    if portrait:
        specs = [
            ("mobile-chart-tight", 0.01, 0.99, 0.12, 0.64),
            ("mobile-chart-mid", 0.01, 0.99, 0.10, 0.68),
            ("mobile-chart-core", 0.03, 0.97, 0.14, 0.70),
            ("mobile-upper", 0.01, 0.99, 0.10, 0.72),
            ("mobile-middle", 0.01, 0.99, 0.18, 0.84),
            ("mobile-lower", 0.01, 0.99, 0.28, 0.96),
            ("mobile-wide", 0.01, 0.99, 0.08, 0.94),
            ("mobile-center", 0.05, 0.95, 0.14, 0.90),
        ]
    else:
        specs = [
            ("desktop-main", 0.035, 0.86, 0.24, 0.94),
            ("desktop-wide", 0.02, 0.94, 0.18, 0.94),
            ("desktop-center", 0.05, 0.90, 0.12, 0.90),
            ("desktop-fullchart", 0.01, 0.99, 0.16, 0.96),
        ]

    out: list[tuple[str, np.ndarray]] = []
    for name, xa, xb, ya, yb in specs:
        x1, x2 = int(w * xa), int(w * xb)
        y1, y2 = int(h * ya), int(h * yb)
        if x2 - x1 >= 180 and y2 - y1 >= 140:
            out.append((name, arr[y1:y2, x1:x2]))
    return out

def analyze_chart_image(raw: bytes, timeframe: str = "1m", market: str = "", last_outcome: str = "", *, captured_at_close: bool = False) -> dict[str, Any]:
    """V11: strict SK Trading Club Pattern Type 1-25 scanner.

    The older V9 candlestick/chart-pattern library is intentionally removed from
    signal decisions. This engine only evaluates the 25 user-supplied setup
    types, visible candle body/wick geometry and the level/trend context required
    by those setups. No RSI/EMA/MACD/Stochastic/Bollinger values are calculated.
    """
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Image could not be opened. Upload a PNG/JPG chart screenshot.") from exc

    w0, h0 = image.size
    if w0 < 240 or h0 < 180:
        raise ValueError("Image is too small. Use a clearer chart screenshot.")

    tf = str(timeframe or "1m").strip().lower()
    market_name = str(market or "").strip()
    previous_outcome = str(last_outcome or "").strip().upper()

    max_dim = 1800.0 if h0 > w0 * 1.12 else 1600.0
    scale = min(1.0, max_dim / max(w0, h0))
    if scale < 1.0:
        image = image.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))), Image.Resampling.LANCZOS)

    # Keep the V9.4 AI Lens server fallback: original + one gentle colour recovery.
    image_variants: list[tuple[str, Image.Image]] = [("raw", image)]
    try:
        enhanced = ImageOps.autocontrast(image, cutoff=1)
        enhanced = ImageEnhance.Color(enhanced).enhance(1.18)
        enhanced = ImageEnhance.Contrast(enhanced).enhance(1.07)
        enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.08)
        image_variants.append(("ai-lens", enhanced))
    except Exception:
        pass

    best_region = None
    best_region_score = -1e9
    fallback_arr = np.asarray(image, dtype=np.uint8)
    for variant_name, variant_image in image_variants:
        variant_arr = np.asarray(variant_image, dtype=np.uint8)
        for crop_name, candidate in _candidate_chart_regions(variant_arr):
            cands, q, qnotes, span, density = _detect_candles_in_chart(candidate)
            score = min(len(cands), 60) * 3.2 + min(1.0, span / 0.55) * 34.0 + min(18.0, density * 900.0) + q * 0.16
            if len(cands) < 6:
                score -= 22.0
            if variant_name == "raw":
                score += 0.6
            if score > best_region_score:
                best_region_score = score
                best_region = (f"{variant_name}:{crop_name}", candidate, cands, q, qnotes)

    if best_region is None:
        crop_name, chart = "raw:full-image", fallback_arr
        candles, quality, quality_notes, _, _ = _detect_candles_in_chart(chart)
    else:
        crop_name, chart, candles, quality, quality_notes = best_region

    ch, cw, _ = chart.shape
    detected_count = len(candles)
    warnings = list(quality_notes)
    reasons: list[str] = []
    library = "SK Trading Club Pattern Type 1-25"

    # V11 Closed Candle Lock. A normal screenshot/live-now frame can contain a
    # still-forming rightmost candle, so it is excluded from setup matching. A
    # frame captured exactly at a candle boundary may include a newborn next candle;
    # a tiny-range heuristic removes that newborn while preserving the just-closed one.
    forming_candle_excluded = False
    newborn_candle_excluded = False
    observed_latest_direction = "UNKNOWN"
    if candles:
        observed_latest_direction = "GREEN" if candles[-1]["dir"] > 0 else "RED"
    if len(candles) >= 2:
        if not captured_at_close:
            candles = candles[:-1]
            forming_candle_excluded = True
        elif len(candles) >= 4:
            prior_ranges = np.array([float(c["range"]) for c in candles[-8:-1]], dtype=float)
            prior_bodies = np.array([float(c["body_height"]) for c in candles[-8:-1]], dtype=float)
            if prior_ranges.size and prior_bodies.size:
                last = candles[-1]
                tiny_newborn = (float(last["range"]) <= float(np.median(prior_ranges)) * 0.34
                                and float(last["body_height"]) <= max(2.0, float(np.median(prior_bodies)) * 0.48))
                if tiny_newborn:
                    candles = candles[:-1]
                    newborn_candle_excluded = True

    count = len(candles)

    def legacy_aliases(pattern: str, direction: str, score: float, signals: list[dict[str, Any]], size: int = 25) -> dict[str, Any]:
        return {
            "selected_strategy": pattern,
            "strategy_direction": direction,
            "strategy_score": score,
            "strategy_signals": signals,
            "strategy_library": library,
            "strategy_library_size": size,
        }

    if count < 6:
        warnings.append("Not enough candle structure was detected. Move closer to the chart and keep candles sharp.")
        return {
            "bias": "NO TRADE", "confidence": 0.0, "image_quality_score": quality,
            "detected_candles": detected_count, "closed_candles_analyzed": count, "visual_trend": "UNREADABLE", "momentum": "PATTERN TYPE 1-25", "volatility": "NOT USED",
            "selected_pattern": "NO TYPE 1-25 SETUP", "pattern_direction": "NONE", "pattern_score": 0.0,
            "pattern_signals": [], "pattern_library": library, "pattern_library_size": 25,
            "confluence_count": 0, "setup_quality": "LOW", "next_candle_color": "NONE",
            "entry_instruction": "WAIT FOR A COMPLETE SETUP", "recovery_trade": False,
            "latest_candle_direction": "UNKNOWN",
            "reasons": ["Insufficient readable candle structure for Pattern Type 1-25 recognition."], "warnings": warnings,
            "pattern_status": {"Candle geometry": "Unreadable", "Pattern library": "Type 1-25 only"},
            "engine": "RAJA V11 · Strict SK25 + Adaptive Vision + Closed Candle Lock", "analysis_crop_mode": crop_name,
            "timing_verified": bool(captured_at_close), "forming_candle_excluded": forming_candle_excluded, "newborn_candle_excluded": newborn_candle_excluded,
            **legacy_aliases("NO TYPE 1-25 SETUP", "NONE", 0.0, []),
        }

    ranges = np.array([float(c["range"]) for c in candles], dtype=float)
    bodies = np.array([float(c["body_height"]) for c in candles], dtype=float)
    med_range = float(np.median(ranges[-min(count, 24):])) if count else 8.0
    med_body = float(np.median(bodies[-min(count, 24):])) if count else 5.0
    tol = max(2.0, med_range * 0.18)

    def trend_before(end_idx: int, lookback: int = 7) -> float:
        start = max(0, end_idx - lookback)
        seq0 = candles[start:end_idx]
        if len(seq0) < 3:
            return 0.0
        yv = np.array([c["y"] for c in seq0], dtype=float) / max(ch, 1)
        xv = np.arange(len(seq0), dtype=float)
        slope = float(np.polyfit(xv, yv, 1)[0]) if len(seq0) > 1 else 0.0
        return float(np.clip(-slope * 18.0, -1.0, 1.0))

    def seq_is(seq0: list[dict[str, Any]], dirs0: list[int]) -> bool:
        return len(seq0) == len(dirs0) and all(int(c["dir"]) == d for c, d in zip(seq0, dirs0))

    def is_normal(c: dict[str, Any]) -> bool:
        # "Normal body" in the source is visual, not a fixed percentage. Keep
        # this tolerant because phone anti-aliasing can make a thin wick merge
        # into the detected body. Sequence/level rules still provide the guard.
        bh = float(c["body_height"])
        return float(c["body_ratio"]) >= 0.28 and bh >= max(2.0, med_body * 0.45) and bh <= med_body * 2.20

    def is_small(c: dict[str, Any]) -> bool:
        return float(c["body_ratio"]) <= 0.30 or float(c["body_height"]) <= max(2.0, med_body * 0.52)

    def is_long(c: dict[str, Any]) -> bool:
        return float(c["body_ratio"]) >= 0.66 and float(c["body_height"]) >= max(4.0, med_body * 1.28)

    def is_marubozu(c: dict[str, Any]) -> bool:
        return is_long(c) and (float(c["upper_wick"]) + float(c["lower_wick"])) <= max(3.0, float(c["body_height"]) * 0.42)

    def long_lower(c: dict[str, Any]) -> bool:
        return float(c["lower_wick"]) >= max(3.0, float(c["body_height"]) * 0.68, med_range * 0.20)

    def long_upper(c: dict[str, Any]) -> bool:
        return float(c["upper_wick"]) >= max(3.0, float(c["body_height"]) * 0.68, med_range * 0.20)

    def close_breaks_above(c: dict[str, Any], level_y: float, margin: float = 0.22) -> bool:
        return float(c["close_y"]) < float(level_y) - tol * margin

    def close_breaks_below(c: dict[str, Any], level_y: float, margin: float = 0.22) -> bool:
        return float(c["close_y"]) > float(level_y) + tol * margin

    def body_inside(inner: dict[str, Any], outer: dict[str, Any], extra: float = 0.0) -> bool:
        return float(inner["body_top"]) >= float(outer["body_top"]) - extra and float(inner["body_bottom"]) <= float(outer["body_bottom"]) + extra

    def strongest_level_cluster(values: list[float], cluster_tol: float, prefer: str) -> tuple[float | None, int]:
        """Cluster nearby visual highs/lows so S/R rules use repeated levels, not one pixel."""
        if not values:
            return None, 0
        vals = sorted(float(v) for v in values)
        clusters: list[list[float]] = []
        for v in vals:
            placed = False
            for cl in clusters:
                center = float(sum(cl) / len(cl))
                if abs(v - center) <= cluster_tol:
                    cl.append(v); placed = True; break
            if not placed:
                clusters.append([v])
        clusters.sort(key=lambda cl: (len(cl), -abs(sum(cl) / len(cl))), reverse=True)
        max_n = max(len(cl) for cl in clusters)
        strongest = [cl for cl in clusters if len(cl) == max_n]
        if prefer == "resistance":
            chosen = min(strongest, key=lambda cl: sum(cl) / len(cl))  # smaller y = higher price
        else:
            chosen = max(strongest, key=lambda cl: sum(cl) / len(cl))  # larger y = lower price
        return float(sum(chosen) / len(chosen)), len(chosen)

    is_otc = "OTC" in market_name.upper()
    is_live = "LIVE" in market_name.upper()
    global_trend = trend_before(len(candles), min(10, count))
    context_label = "UPTREND" if global_trend > 0.13 else "DOWNTREND" if global_trend < -0.13 else "SIDEWAYS/MIXED"

    exact: list[dict[str, Any]] = []
    near: list[dict[str, Any]] = []

    def add_setup(type_no: int, direction: int, rules: list[tuple[str, bool]], setup: str, why: str,
                  *, family: str = "Candle Sequence", recovery: bool = False, timeframe_rule: str = "ANY") -> None:
        matched = sum(1 for _, ok in rules if ok)
        total = max(1, len(rules))
        pct = round(100.0 * matched / total, 1)
        priority_map = {1:120, 2:105, 3:120, 4:115, 5:125, 6:170, 7:80, 8:80, 9:145, 10:145, 11:160, 12:165, 13:175, 14:150, 15:170, 16:75, 17:75, 18:155, 19:155, 20:145, 21:145, 22:155, 23:155, 24:180, 25:175}
        item = {
            "name": f"Pattern Type {type_no}",
            "priority": priority_map.get(type_no, 100),
            "pattern_type": type_no,
            "direction": "UP" if direction > 0 else "DOWN",
            "next_candle": "GREEN" if direction > 0 else "RED",
            "score": pct,
            "why": why,
            "setup": setup,
            "family": family,
            "rules_matched": matched,
            "rules_total": total,
            "rules": [{"name": name, "ok": bool(ok)} for name, ok in rules],
            "recovery_trade": bool(recovery),
            "timeframe_rule": timeframe_rule,
        }
        if matched == total:
            exact.append(item)
        elif pct >= 50.0:
            near.append(item)

    # TYPE 1 - OTC 9-candle sequence: 8 same-colour setup candles -> next same colour.
    if count >= 8:
        last8 = candles[-8:]
        add_setup(1, 1, [("OTC market", is_otc), ("8 back-to-back GREEN candles", all(c["dir"] > 0 for c in last8))],
                  "8 GREEN candles in OTC", "After 8 consecutive green setup candles, the strategy targets the next candle GREEN.", timeframe_rule="OTC ONLY")
        add_setup(1, -1, [("OTC market", is_otc), ("8 back-to-back RED candles", all(c["dir"] < 0 for c in last8))],
                  "8 RED candles in OTC", "After 8 consecutive red setup candles, the strategy targets the next candle RED.", timeframe_rule="OTC ONLY")

    # TYPE 2 - 2 green + first red at respected resistance -> next red.
    if count >= 3:
        a, b, c = candles[-3:]
        resistance_touch = abs(float(a["top"]) - float(b["top"])) <= tol * 1.55
        reversal = c["dir"] < 0 and float(c["close_y"]) > float(b["open_y"]) - tol * 0.25
        add_setup(2, -1, [("GREEN, GREEN, RED setup", seq_is([a,b,c],[1,1,-1])), ("Recent highs respect one resistance area", resistance_touch), ("First RED shows reversal", reversal)],
                  "2 GREEN + first RED at resistance", "Resistance is respected and the first red reversal candle is present; the strategy targets the following candle RED.", family="Resistance")

    # TYPE 3 - sideways G-R-G; 3rd green lower wick breaks down -> next red.
    if count >= 3:
        a, b, c = candles[-3:]
        wick_break_down = c["dir"] > 0 and float(c["bottom"]) > max(float(a["bottom"]), float(b["bottom"])) + tol * 0.20 and long_lower(c)
        add_setup(3, -1, [("GREEN, RED, GREEN setup", seq_is([a,b,c],[1,-1,1])), ("3rd GREEN wick breaks below prior lows", wick_break_down), ("Sideways/mixed context", abs(global_trend) < 0.60)],
                  "GREEN - RED - GREEN with downside wick break", "The third green candle sweeps below the prior lows; the strategy targets the next candle RED.", family="Sideways")

    # TYPE 4 - RED long tail then GREEN; next green.
    if count >= 2:
        a, b = candles[-2:]
        tail_vs_head = float(a["lower_wick"]) > max(float(b["upper_wick"]) * 1.12, med_range * 0.18)
        add_setup(4, 1, [("RED then GREEN", seq_is([a,b],[-1,1])), ("1st RED tail is long", long_lower(a)), ("RED tail longer than GREEN head", tail_vs_head)],
                  "RED long-tail + GREEN", "The first red candle has the required long tail relative to the green candle head; the strategy targets the next candle GREEN.")

    # TYPE 5 - R,R with long tails; 2nd red head does not break 1st; then G -> next R.
    if count >= 3:
        a, b, c = candles[-3:]
        no_head_break = float(b["top"]) >= float(a["top"]) - tol * 0.35
        add_setup(5, -1, [("RED, RED, GREEN setup", seq_is([a,b,c],[-1,-1,1])), ("First two RED tails are long", long_lower(a) and long_lower(b)), ("2nd RED head does not break 1st RED", no_head_break), ("Sideways/mixed context", abs(global_trend) < 0.68)],
                  "2 long-tail RED + GREEN", "The two red candles keep the required wick/level structure and a green setup candle follows; the strategy targets the next candle RED.", family="Sideways")

    # TYPE 6 - recovery sequence only after a recorded loss.
    if count >= 3:
        a, b, c = candles[-3:]
        add_setup(6, -1, [("Previous trade marked LOSS", previous_outcome == "LOSS"), ("RED, GREEN, RED setup", seq_is([a,b,c],[-1,1,-1]))],
                  "Recovery: RED - GREEN - RED", "This setup is enabled only after the previous trade is recorded as a loss; the strategy targets the next candle RED.", family="Recovery", recovery=True, timeframe_rule="AFTER LOSS ONLY")

    # TYPE 7 - R,G,G normal -> next red.
    if count >= 3:
        a, b, c = candles[-3:]
        add_setup(7, -1, [("RED, GREEN, GREEN setup", seq_is([a,b,c],[-1,1,1])), ("Two GREEN candles have normal bodies", is_normal(b) and is_normal(c))],
                  "RED + 2 normal GREEN", "After one red and two back-to-back normal-body green candles, the strategy targets the next candle RED.")

    # TYPE 8 - G,R,R normal -> next green.
    if count >= 3:
        a, b, c = candles[-3:]
        add_setup(8, 1, [("GREEN, RED, RED setup", seq_is([a,b,c],[1,-1,-1])), ("Two RED candles have normal bodies", is_normal(b) and is_normal(c))],
                  "GREEN + 2 normal RED", "After one green and two back-to-back normal-body red candles, the strategy targets the next candle GREEN.")

    # TYPE 9 - 3 green + opposite red with long tail -> next green.
    if count >= 4:
        a,b,c,d = candles[-4:]
        add_setup(9, 1, [("3 GREEN + 1 RED setup", seq_is([a,b,c,d],[1,1,1,-1])), ("Opposite RED has long tail", long_lower(d))],
                  "GREEN, GREEN, GREEN + long-tail RED", "Three green candles are followed by the required opposite red long-tail setup candle; the strategy targets the NEXT candle GREEN.")

    # TYPE 10 - 3 red + opposite green with long head -> next red.
    if count >= 4:
        a,b,c,d = candles[-4:]
        add_setup(10, -1, [("3 RED + 1 GREEN setup", seq_is([a,b,c,d],[-1,-1,-1,1])), ("Opposite GREEN has long head", long_upper(d))],
                  "RED, RED, RED + long-head GREEN", "Three red candles are followed by the required opposite green long-head setup candle; the strategy targets the NEXT candle RED.")

    # TYPE 11 - 30s only: 3 normal red + green that does not break prior 3 -> next green.
    if count >= 4:
        a,b,c,d = candles[-4:]
        prior_high = min(float(x["top"]) for x in (a,b,c))
        no_break = float(d["top"]) >= prior_high - tol * 0.35
        add_setup(11, 1, [("30-second timeframe", tf == "30s"), ("RED, RED, RED, GREEN setup", seq_is([a,b,c,d],[-1,-1,-1,1])), ("First 3 RED candles have normal bodies", all(is_normal(x) for x in (a,b,c))), ("GREEN does not break previous 3 RED highs", no_break)],
                  "3 normal RED + contained GREEN", "On a 30-second chart, the green setup candle stays within the previous red structure; the strategy targets the next 30-second candle GREEN.", timeframe_rule="30S ONLY")

    # TYPE 12 - 2m only: RR + GG contained under horizontal resistance -> next red.
    if count >= 4:
        a,b,c,d = candles[-4:]
        resistance = min(float(a["top"]), float(b["top"]))
        greens_contained = max(float(c["top"]), float(d["top"])) >= resistance - tol * 0.45 and float(c["top"]) >= resistance - tol * 0.45 and float(d["top"]) >= resistance - tol * 0.45
        close_near = abs(float(d["close_y"]) - resistance) <= max(tol * 2.8, med_range * 0.65)
        add_setup(12, -1, [("2-minute timeframe", tf == "2m"), ("RED, RED, GREEN, GREEN setup", seq_is([a,b,c,d],[-1,-1,1,1])), ("Normal body candles", all(is_normal(x) for x in (a,b,c,d))), ("GREEN candles do not break first RED resistance", greens_contained), ("Last GREEN stays near horizontal level", close_near)],
                  "2 RED + 2 GREEN below horizontal resistance", "The 2-minute setup stays below the first red resistance area; the strategy targets the next 2-minute candle RED.", family="Horizontal Level", timeframe_rule="2M ONLY")

    # TYPE 13 - 2m only: several resistance/support retests, breakout -> next opposite reversal.
    if count >= 7:
        prior = candles[-10:-1] if count >= 10 else candles[:-1]
        last = candles[-1]
        resistance, res_touches = strongest_level_cluster([float(x["top"]) for x in prior], tol * 1.25, "resistance")
        support, sup_touches = strongest_level_cluster([float(x["bottom"]) for x in prior], tol * 1.25, "support")
        resistance = float(resistance if resistance is not None else min(x["top"] for x in prior))
        support = float(support if support is not None else max(x["bottom"] for x in prior))
        up_break = last["dir"] > 0 and close_breaks_above(last, resistance, 0.28)
        dn_break = last["dir"] < 0 and close_breaks_below(last, support, 0.28)
        add_setup(13, -1, [("2-minute timeframe", tf == "2m"), ("Resistance retested several times", res_touches >= 2), ("Latest GREEN breaks resistance", up_break)],
                  "Repeated resistance retest + upside breakout", "After several resistance retests, the breakout candle completes the setup; the strategy targets the next 2-minute candle RED.", family="Breakout Reversal", timeframe_rule="2M ONLY")
        add_setup(13, 1, [("2-minute timeframe", tf == "2m"), ("Support retested several times", sup_touches >= 2), ("Latest RED breaks support", dn_break)],
                  "Repeated support retest + downside breakout", "After several support retests, the breakdown candle completes the setup; the strategy targets the next 2-minute candle GREEN.", family="Breakout Reversal", timeframe_rule="2M ONLY")

    # TYPE 14 - horizontal S/R break -> same direction next candle.
    if count >= 5:
        prior = candles[-9:-1] if count >= 9 else candles[:-1]
        last = candles[-1]
        greens = [x for x in prior if x["dir"] > 0]
        reds = [x for x in prior if x["dir"] < 0]
        support, support_touches = strongest_level_cluster([float(x["bottom"]) for x in greens], tol * 1.25, "support")
        resistance, resistance_touches = strongest_level_cluster([float(x["top"]) for x in reds], tol * 1.25, "resistance")
        if support is not None and support_touches >= 2:
            add_setup(14, -1, [("2+ GREEN candles define one support cluster", True), ("Latest candle is RED", last["dir"] < 0), ("RED closes below clustered support", close_breaks_below(last, support, 0.25))],
                      "Clustered horizontal support breakdown", "A red candle breaks support confirmed by repeated green-candle lows; the strategy targets the next candle RED.", family="Horizontal Break")
        if resistance is not None and resistance_touches >= 2:
            add_setup(14, 1, [("2+ RED candles define one resistance cluster", True), ("Latest candle is GREEN", last["dir"] > 0), ("GREEN closes above clustered resistance", close_breaks_above(last, resistance, 0.25))],
                      "Clustered horizontal resistance breakout", "A green candle breaks resistance confirmed by repeated red-candle highs; the strategy targets the next candle GREEN.", family="Horizontal Break")

    # TYPE 15 - V / inverted-V breakout, then opposite-direction target.
    if count >= 7:
        shape = candles[-7:-1]
        last = candles[-1]
        yv = np.array([float(x["y"]) for x in shape], dtype=float)
        low_i = int(np.argmax(yv))
        high_i = int(np.argmin(yv))
        v_shape = 1 <= low_i <= len(shape)-2 and (yv[low_i]-yv[0]) >= med_range * 0.80 and (yv[low_i]-yv[-1]) >= med_range * 0.70
        iv_shape = 1 <= high_i <= len(shape)-2 and (yv[0]-yv[high_i]) >= med_range * 0.80 and (yv[-1]-yv[high_i]) >= med_range * 0.70
        v_level = min(float(shape[0]["top"]), float(shape[1]["top"]))
        iv_level = max(float(shape[0]["bottom"]), float(shape[1]["bottom"]))
        add_setup(15, -1, [("V shape formed", v_shape), ("Latest GREEN breaks horizontal top", last["dir"] > 0 and close_breaks_above(last, v_level, 0.18))],
                  "V pattern + upside horizontal breakout", "The V completes and breaks the horizontal line; the strategy targets the next candle in the opposite direction: RED.", family="V Reversal")
        add_setup(15, 1, [("Inverted-V shape formed", iv_shape), ("Latest RED breaks horizontal bottom", last["dir"] < 0 and close_breaks_below(last, iv_level, 0.18))],
                  "Inverted V + downside horizontal breakout", "The inverted V completes and breaks the horizontal line; the strategy targets the next candle in the opposite direction: GREEN.", family="V Reversal")

    # TYPE 16 - 3/4 green normal + 1 red -> next green.
    if count >= 4 and candles[-1]["dir"] < 0:
        run = 0
        i = count - 2
        while i >= 0 and candles[i]["dir"] > 0 and run < 5:
            run += 1; i -= 1
        setup_c = candles[count-run-1:count-1] if run else []
        add_setup(16, 1, [("3 to 4 back-to-back GREEN candles", 3 <= run <= 4), ("GREEN bodies are normal", bool(setup_c) and all(is_normal(x) for x in setup_c)), ("One opposite RED setup candle", candles[-1]["dir"] < 0)],
                  "3-4 normal GREEN + 1 RED", "The continuation setup is complete; the strategy targets the next candle GREEN.")

    # TYPE 17 - 3/4 red normal + 1 green -> next red.
    if count >= 4 and candles[-1]["dir"] > 0:
        run = 0
        i = count - 2
        while i >= 0 and candles[i]["dir"] < 0 and run < 5:
            run += 1; i -= 1
        setup_c = candles[count-run-1:count-1] if run else []
        add_setup(17, -1, [("3 to 4 back-to-back RED candles", 3 <= run <= 4), ("RED bodies are normal", bool(setup_c) and all(is_normal(x) for x in setup_c)), ("One opposite GREEN setup candle", candles[-1]["dir"] > 0)],
                  "3-4 normal RED + 1 GREEN", "The continuation setup is complete; the strategy targets the next candle RED.")

    # TYPE 18 - long red marubozu + GGG + R, no resistance break -> next red.
    if count >= 5:
        a,b,c,d,e = candles[-5:]
        no_res_break = all(float(x["top"]) >= float(a["top"]) - tol * 0.30 for x in (b,c,d,e))
        add_setup(18, -1, [("Long RED marubozu first candle", a["dir"] < 0 and is_marubozu(a)), ("Then GREEN, GREEN, GREEN, RED", seq_is([b,c,d,e],[1,1,1,-1])), ("Three GREEN candles have normal bodies", all(is_normal(x) for x in (b,c,d))), ("No wick/body breaks first RED resistance", no_res_break), ("Sideways/mixed context", abs(global_trend) < 0.72)],
                  "Long RED + 3 GREEN + RED below resistance", "The entire four-candle response stays below the first long red resistance; the strategy targets the next candle RED.", family="Sideways Level")

    # TYPE 19 - long green marubozu + RRR + G, no support break -> next green.
    if count >= 5:
        a,b,c,d,e = candles[-5:]
        no_sup_break = all(float(x["bottom"]) <= float(a["bottom"]) + tol * 0.30 for x in (b,c,d,e))
        add_setup(19, 1, [("Long GREEN marubozu first candle", a["dir"] > 0 and is_marubozu(a)), ("Then RED, RED, RED, GREEN", seq_is([b,c,d,e],[-1,-1,-1,1])), ("Three RED candles have normal bodies", all(is_normal(x) for x in (b,c,d))), ("No wick/body breaks first GREEN support", no_sup_break), ("Sideways/mixed context", abs(global_trend) < 0.72)],
                  "Long GREEN + 3 RED + GREEN above support", "The entire four-candle response stays above the first long green support; the strategy targets the next candle GREEN.", family="Sideways Level")

    # TYPE 20 - downtrend: R,R,G,R where 4th red does not break previous green -> next red.
    if count >= 4:
        a,b,c,d = candles[-4:]
        no_green_breakdown = float(d["bottom"]) <= float(c["bottom"]) + tol * 0.35
        add_setup(20, -1, [("Downtrend context", global_trend < -0.10), ("RED, RED, GREEN, RED setup", seq_is([a,b,c,d],[-1,-1,1,-1])), ("First two RED candles normal", is_normal(a) and is_normal(b)), ("4th RED does not break previous GREEN low", no_green_breakdown)],
                  "Downtrend R-R-G-R hold", "The fourth red candle holds above the prior green low; the strategy targets the next candle RED.", family="Downtrend")

    # TYPE 21 - uptrend: G,G,R,G where 4th green does not break previous red -> next green.
    if count >= 4:
        a,b,c,d = candles[-4:]
        no_red_breakout = float(d["top"]) >= float(c["top"]) - tol * 0.35
        add_setup(21, 1, [("Uptrend context", global_trend > 0.10), ("GREEN, GREEN, RED, GREEN setup", seq_is([a,b,c,d],[1,1,-1,1])), ("First two GREEN candles normal", is_normal(a) and is_normal(b)), ("4th GREEN does not break previous RED high", no_red_breakout)],
                  "Uptrend G-G-R-G hold", "The fourth green candle stays below the prior red high; the strategy targets the next candle GREEN.", family="Uptrend")

    # TYPE 22 - uptrend 3-5 green + small red contained in prior green body -> next green.
    if count >= 4 and candles[-1]["dir"] < 0:
        last = candles[-1]
        run = 0; i = count - 2
        while i >= 0 and candles[i]["dir"] > 0 and run < 6:
            run += 1; i -= 1
        greens = candles[count-run-1:count-1] if run else []
        prev = candles[-2]
        add_setup(22, 1, [("Uptrend context", global_trend > 0.08), ("3 to 5 back-to-back GREEN candles", 3 <= run <= 5), ("GREEN candles normal", bool(greens) and all(is_normal(x) for x in greens)), ("Opposite RED body smaller than previous GREEN", float(last["body_height"]) < float(prev["body_height"])), ("RED body does not break previous GREEN body", float(last["body_bottom"]) <= float(prev["body_bottom"]) + tol * 0.28)],
                  "3-5 GREEN + smaller contained RED", "The small red pullback stays within the prior green body; the strategy targets the next candle GREEN.", family="Uptrend")

    # TYPE 23 - downtrend 3-5 red + small green contained in prior red body -> next red.
    if count >= 4 and candles[-1]["dir"] > 0:
        last = candles[-1]
        run = 0; i = count - 2
        while i >= 0 and candles[i]["dir"] < 0 and run < 6:
            run += 1; i -= 1
        reds = candles[count-run-1:count-1] if run else []
        prev = candles[-2]
        add_setup(23, -1, [("Downtrend context", global_trend < -0.08), ("3 to 5 back-to-back RED candles", 3 <= run <= 5), ("RED candles normal", bool(reds) and all(is_normal(x) for x in reds)), ("Opposite GREEN body smaller than previous RED", float(last["body_height"]) < float(prev["body_height"])), ("GREEN body does not break previous RED body", float(last["body_top"]) >= float(prev["body_top"]) - tol * 0.28)],
                  "3-5 RED + smaller contained GREEN", "The small green pullback stays within the prior red body; the strategy targets the next candle RED.", family="Downtrend")

    # TYPE 24 - live market sideways: G,R,R(small),G,R(smaller) -> next green, SNR respected.
    if count >= 5:
        a,b,c,d,e = candles[-5:]
        snr = (float(a["top"]) + float(b["top"])) / 2.0
        snr_respected = all(float(x["top"]) >= snr - tol * 0.40 for x in (a,b,c,d,e))
        add_setup(24, 1, [("LIVE market", is_live), ("GREEN, RED, RED, GREEN, RED setup", seq_is([a,b,c,d,e],[1,-1,-1,1,-1])), ("First GREEN and second RED maintain SNR", abs(float(a["top"])-float(b["top"])) <= tol * 1.45), ("3rd RED is Doji/small body", is_small(c)), ("4th GREEN does not break SNR", float(d["top"]) >= snr - tol * 0.40), ("5th RED body smaller than previous GREEN", float(e["body_height"]) < float(d["body_height"])), ("No setup candle breaks SNR", snr_respected), ("Sideways/mixed context", abs(global_trend) < 0.72)],
                  "LIVE sideways G-R-smallR-G-smallR at SNR", "All five live-market SNR conditions are present; the strategy targets the next candle GREEN.", family="Live SNR", timeframe_rule="LIVE MARKET ONLY")

    # TYPE 25 - small red, normal red, long green breaks first red SNR -> next green.
    if count >= 3:
        a,b,c = candles[-3:]
        snr = float(a["top"])
        add_setup(25, 1, [("RED, RED, GREEN setup", seq_is([a,b,c],[-1,-1,1])), ("1st RED is small/Doji", is_small(a)), ("2nd RED has normal body", is_normal(b)), ("3rd GREEN is long", is_long(c)), ("Long GREEN breaks 1st RED SNR", close_breaks_above(c, snr, 0.20))],
                  "Small RED + normal RED + long GREEN SNR breakout", "The long green candle breaks the SNR level created by the first small red candle; the strategy targets the next candle GREEN.", family="SNR Breakout")

    # V11 conflict gate: an opposite exact setup is never overridden by a numeric
    # priority. Same-direction exact setups reinforce one another; opposite exact
    # setups produce NO TRADE until the chart resolves.
    exact.sort(key=lambda s: (int(s.get("priority") or 0), int(s["rules_total"]), int(s["pattern_type"])), reverse=True)
    near.sort(key=lambda s: (float(s["score"]), int(s["rules_total"])), reverse=True)
    exact_directions = {str(x.get("direction") or "") for x in exact}
    conflict_gate = len({x for x in exact_directions if x in {"UP", "DOWN"}}) > 1
    best = None if conflict_gate else (exact[0] if exact else None)
    best_near = near[0] if near else None

    if conflict_gate:
        bias = "NO TRADE"
        next_color = "NONE"
        selected_dir = "NONE"
        setup_quality = "LOW"
        selected = "CONFLICTING TYPE SETUPS"
        match_score = 100.0
        confidence = 0.0
        signals_out = exact[:8]
        conflict_names = ", ".join(f"{x['name']} {x['direction']}" for x in exact[:6])
        reasons.append(f"Conflict Gate blocked the entry because opposite exact setups are present: {conflict_names}.")
        reasons.append("Wait for a fresh closed candle and re-scan; V11 never chooses UP/DOWN by priority when exact setups disagree.")
    elif best:
        direction = str(best["direction"])
        next_color = str(best["next_candle"])
        bias = "UP SIGNAL" if direction == "UP" else "DOWN SIGNAL"
        # 100% means every coded source rule for this setup matched; it is not a profit probability.
        match_score = 100.0
        setup_quality = "HIGH" if quality >= 72 else "MEDIUM"
        selected = str(best["name"])
        reasons.extend([
            f"{selected} exact setup matched: {best['rules_matched']}/{best['rules_total']} coded rules.",
            f"Strategy target: NEXT candle {next_color} ({direction}). Entry alert is for the next candle open after setup confirmation.",
        ])
        if best.get("recovery_trade"):
            reasons.append("RECOVERY TRADE: Pattern Type 6 is active because the previous trade is recorded as LOSS.")
        confidence = match_score
        selected_dir = direction
        signals_out = exact[:8]
        if not captured_at_close:
            # Pattern can be inspected, but a static/mid-candle frame cannot prove
            # that the setup completed exactly at the boundary. Do not arm an entry.
            bias = "NO TRADE"
            next_color = "NONE"
            confidence = 0.0
            selected_dir = "NONE"
            selected = f"WAIT CLOSE: {best['name']}"
            reasons.append("Closed Candle Lock: exact setup geometry was seen, but timing was not captured at candle close. Use ONE-TAP CAMERA AUTO SCAN for the next boundary.")
    else:
        bias = "NO TRADE"
        next_color = "NONE"
        selected_dir = "NONE"
        setup_quality = "LOW"
        if best_near:
            selected = f"WATCH: {best_near['name']}"
            match_score = float(best_near["score"])
            reasons.append(f"No exact Type 1-25 setup yet. Closest is {best_near['name']} with {best_near['rules_matched']}/{best_near['rules_total']} rules currently visible.")
        else:
            selected = "NO TYPE 1-25 SETUP"
            match_score = 0.0
            reasons.append("No exact Pattern Type 1-25 setup is complete on the newest readable candles.")
        reasons.append("No directional entry is armed until every required rule for one strategy setup is present.")
        confidence = match_score
        signals_out = near[:8]

    latest_dir = "GREEN" if candles and candles[-1]["dir"] > 0 else "RED" if candles else "UNKNOWN"

    # Strategy Proof: normalized candle geometry for the newest closed candles.
    candle_debug: list[dict[str, Any]] = []
    debug_seq = candles[-10:]
    for i, c in enumerate(debug_seq, start=max(1, count - len(debug_seq) + 1)):
        rng = max(1.0, float(c.get("range") or 1.0))
        body_pct = round(float(c.get("body_height") or 0.0) / rng * 100.0, 1)
        upper_pct = round(float(c.get("upper_wick") or 0.0) / rng * 100.0, 1)
        lower_pct = round(float(c.get("lower_wick") or 0.0) / rng * 100.0, 1)
        body_class = "SMALL" if is_small(c) else "LONG" if is_long(c) else "NORMAL" if is_normal(c) else "OTHER"
        candle_debug.append({
            "n": i, "color": "GREEN" if c["dir"] > 0 else "RED",
            "body_pct": body_pct, "upper_wick_pct": upper_pct, "lower_wick_pct": lower_pct,
            "body_class": body_class,
        })

    if quality < 65:
        warnings.append("Image is usable, but a sharper screenshot/photo will improve wick/body and SNR-level measurement.")
    warnings.append("Setup Match measures coded rule agreement only; it is not a guaranteed win probability.")

    result = {
        "bias": bias,
        "confidence": round(float(confidence), 1),
        "setup_match": round(float(match_score), 1),
        "image_quality_score": quality,
        "detected_candles": detected_count,
        "closed_candles_analyzed": count,
        "visual_trend": context_label,
        "momentum": "PATTERN TYPE 1-25 ONLY",
        "volatility": "NOT USED",
        "selected_pattern": selected,
        "pattern_type": int(best.get("pattern_type") or 0) if best else 0,
        "pattern_direction": selected_dir,
        "pattern_score": round(float(match_score), 1),
        "setup_rules": list(best.get("rules") or []) if best else list((best_near or {}).get("rules") or []),
        "pattern_signals": signals_out,
        "pattern_library": library,
        "pattern_library_size": 25,
        "confluence_count": len(exact) if (best and not conflict_gate) else 0,
        "setup_quality": setup_quality,
        "conflict_gate": bool(conflict_gate),
        "timing_verified": bool(captured_at_close),
        "forming_candle_excluded": bool(forming_candle_excluded),
        "newborn_candle_excluded": bool(newborn_candle_excluded),
        "observed_latest_candle_direction": observed_latest_direction,
        "candle_debug": candle_debug,
        "next_candle_color": next_color,
        "entry_instruction": "NEXT CANDLE OPEN" if (best and captured_at_close and not conflict_gate) else "WAIT FOR VERIFIED CANDLE CLOSE" if best else "WAIT FOR EXACT SETUP",
        "recovery_trade": bool(best and best.get("recovery_trade")),
        "recovery_candidate": bool(any(int(x.get("pattern_type") or 0) == 6 for x in near)),
        "latest_candle_direction": latest_dir,
        "last_outcome_used": previous_outcome or "NONE",
        "reasons": reasons[:10],
        "warnings": warnings[:7],
        "pattern_status": {
            "Mode": "Pattern Type 1-25 only",
            "Indicators": "OFF - signal engine uses only the supplied Pattern Type 1-25 rules",
            "Context": f"Visual candle context: {context_label}",
            "Candle geometry": f"{count} closed candles analysed / {detected_count} visible structures",
            "Closed Candle Lock": "VERIFIED AT CLOSE" if captured_at_close else "FORMING CANDLE EXCLUDED - ENTRY NOT ARMED",
            "Conflict Gate": "BLOCK" if conflict_gate else "PASS",
            "Timeframe rules": "Type 11=30s; Type 12/13=2m; Type 1=OTC; Type 24=Live market",
        },
        "engine": "RAJA V11 · Strict SK25 + Adaptive Vision + Closed Candle Lock + Conflict Gate",
        "analysis_crop_mode": crop_name,
    }
    result.update(legacy_aliases(selected, selected_dir, round(float(match_score), 1), signals_out, 25))
    return result


@app.get("/")
def home():
    resp = send_from_directory(APP_DIR, "index.html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


def _cleanup_shared_charts(max_age_seconds: int = 900) -> None:
    cutoff = time.time() - max_age_seconds
    try:
        for path in SHARED_DIR.iterdir():
            if path.is_file() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
    except Exception:
        pass


@app.post("/share-target")
def share_target():
    """PWA share target: receive an image from Android/desktop share sheet.

    The image is stored under an unguessable short-lived token and is deleted the
    first time the scanner loads it. No broker password/session information is used.
    """
    _cleanup_shared_charts()
    f = request.files.get("chart")
    if not f or not f.filename:
        return redirect("/?share_error=no-image", code=303)
    raw = f.read(MAX_UPLOAD_BYTES + 1)
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        return redirect("/?share_error=image-too-large", code=303)
    mime = str(f.mimetype or "").lower()
    suffix = ".png" if "png" in mime else ".webp" if "webp" in mime else ".jpg"
    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()
    except Exception:
        return redirect("/?share_error=invalid-image", code=303)
    token = secrets.token_urlsafe(18)
    (SHARED_DIR / f"{token}{suffix}").write_bytes(raw)
    return redirect(f"/?shared={token}", code=303)


@app.get("/api/shared-image/<token>")
def shared_image(token: str):
    _cleanup_shared_charts()
    if not token or len(token) > 80 or any(not (c.isalnum() or c in "-_") for c in token):
        return jsonify({"status": "error", "message": "Invalid share token."}), 400
    path = next((p for p in SHARED_DIR.glob(f"{token}.*") if p.is_file()), None)
    if path is None:
        return jsonify({"status": "error", "message": "Shared chart expired or not found."}), 404
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    path.unlink(missing_ok=True)
    mime = "image/png" if suffix == ".png" else "image/webp" if suffix == ".webp" else "image/jpeg"
    return Response(raw, mimetype=mime, headers={"Cache-Control": "no-store"})


@app.get("/manifest.json")
def manifest():
    resp = send_from_directory(APP_DIR, "manifest.json")
    resp.headers["Cache-Control"] = "no-cache, max-age=0"
    return resp


@app.get("/sw.js")
def sw():
    resp = send_from_directory(APP_DIR, "sw.js", mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "app": "RAJA AI Chart Scanner",
        "version": "11.0.0",
        "storage": "postgres" if DATABASE_URL and psycopg is not None else "file",
        "monthly_price_eur": MONTHLY_PRICE_EUR,
    })


@app.get("/api/config")
def public_config():
    return jsonify({
        "status": "success",
        "quotex_url": QUOTEX_URL,
        "pocket_url": POCKET_URL,
        "monthly_price_eur": MONTHLY_PRICE_EUR,
        "support_url": SUPPORT_URL,
        "min_affiliate_deposit_usd": 50,
        "broker_data": BROKER_DATA,
    })


@app.post("/api/free-trial")
def free_trial():
    data = request.get_json(silent=True) or {}
    user = _norm_user(data.get("user"))
    device = _norm_device(data.get("device"))
    label = str(data.get("device_label") or "Mobile Device")[:160]
    if not user or not device:
        return jsonify({"status": "error", "message": "User/UID and device are required."}), 400
    if get_trial_claim("user", user):
        return jsonify({"status": "error", "message": "This user/UID has already used the free trial."}), 409
    if get_trial_claim("device", device):
        return jsonify({"status": "error", "message": "This device has already used the free trial."}), 409
    key, rec = create_license(user, "FREE TRIAL", 0.5)
    token = secrets.token_urlsafe(32)
    rec.update({"device_id": device, "device_label": label, "session_token": token, "last_verified_at": _now(), "last_login_at": _now()})
    save_license(key, rec)
    set_trial_claim("user", user, key)
    set_trial_claim("device", device, key)
    return jsonify({"status": "success", "key": key, "user": user, "session_token": token, "plan": rec["plan"], "expires_at": rec["expires_at"]})


@app.post("/api/verify-license")
def verify_license():
    data = request.get_json(silent=True) or {}
    key = str(data.get("key") or "").strip()
    user = _norm_user(data.get("user"))
    device = _norm_device(data.get("device"))
    label = str(data.get("device_label") or device)[:160]
    token = str(data.get("session_token") or "").strip()
    heartbeat = bool(data.get("heartbeat"))
    if not key or not device:
        return jsonify({"status": "error", "message": "License key and device are required."}), 400
    rec = get_license(key)
    if not rec or not rec.get("active"):
        return jsonify({"status": "error", "message": "Invalid or revoked license key."}), 401
    if _license_expired(rec):
        return jsonify({"status": "error", "message": "License expired. Renew access to continue."}), 401
    assigned_user = _norm_user(rec.get("user_id"))
    if heartbeat and not user:
        return jsonify({"status": "error", "message": "Active session user is missing."}), 400
    if not user:
        user = assigned_user
    if not user:
        return jsonify({"status": "error", "message": "This license has no assigned user/UID."}), 400
    if assigned_user and assigned_user != user:
        return jsonify({"status": "error", "message": "This key is assigned to another user/UID."}), 403
    if heartbeat:
        if str(rec.get("device_id") or "") != device or str(rec.get("session_token") or "") != token:
            return jsonify({"status": "error", "message": "This session was replaced by a newer device login."}), 409
        rec["last_verified_at"] = _now()
        save_license(key, rec)
        return jsonify({"status": "success", "user": user, "plan": rec.get("plan"), "expires_at": rec.get("expires_at"), "session_token": rec.get("session_token")})

    previous_device = str(rec.get("device_id") or "")
    previous_label = str(rec.get("device_label") or "")
    new_token = secrets.token_urlsafe(32)
    rec.update({
        "device_id": device,
        "device_label": label,
        "session_token": new_token,
        "last_verified_at": _now(),
        "last_login_at": _now(),
    })
    save_license(key, rec)
    return jsonify({
        "status": "success", "user": user, "plan": rec.get("plan"), "expires_at": rec.get("expires_at"),
        "session_token": new_token,
        "replaced_previous_device": bool(previous_device and previous_device != device),
        "previous_device_label": previous_label if previous_device and previous_device != device else None,
    })


@app.post("/api/access-request")
def access_request():
    data = request.get_json(silent=True) or {}
    req_type = str(data.get("request_type") or "affiliate").lower().strip()
    user = _norm_user(data.get("user_id"))
    if not user:
        return jsonify({"status": "error", "message": "User/UID is required."}), 400
    if req_type not in {"affiliate", "monthly"}:
        return jsonify({"status": "error", "message": "Unknown request type."}), 400
    if req_type == "affiliate":
        broker = str(data.get("broker") or "").strip()
        if broker not in {"Quotex", "Pocket Option"}:
            return jsonify({"status": "error", "message": "Select Quotex or Pocket Option."}), 400
        try:
            deposit = float(data.get("deposit_amount") or 0)
        except Exception:
            deposit = 0
        if deposit < 50:
            return jsonify({"status": "error", "message": "Affiliate Pro verification requires minimum $50 deposit."}), 400
    row = add_access_request(data)
    return jsonify({"status": "success", "message": "Request submitted for admin verification.", "request": row})


@app.post("/api/access-status")
def access_status():
    data = request.get_json(silent=True) or {}
    user = _norm_user(data.get("user_id"))
    if not user:
        return jsonify({"status": "error", "message": "User/UID is required."}), 400
    rows = [r for r in list_requests() if _norm_user(r.get("user_id")) == user]
    if not rows:
        return jsonify({"status": "success", "found": False})
    row = rows[0]
    return jsonify({
        "status": "success", "found": True,
        "request": {
            "request_id": row.get("request_id"), "request_type": row.get("request_type"), "broker": row.get("broker"),
            "status": row.get("status"), "license_key": row.get("license_key"), "updated_at": row.get("updated_at"),
        }
    })




MIN_SIGNAL_CANDLES = max(10, min(30, int(os.environ.get("RAJA_SCANNER_MIN_SIGNAL_CANDLES", "14"))))
MIN_SIGNAL_IMAGE_QUALITY = max(45.0, min(90.0, float(os.environ.get("RAJA_SCANNER_MIN_IMAGE_QUALITY", "65"))))


def _rotate_image_bytes(raw: bytes, angle: int) -> bytes:
    """Rotate the uploaded visual frame for mobile/sideways-photo rescue."""
    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image).convert("RGB")
    rotated = image.rotate(angle, expand=True)
    out = io.BytesIO()
    rotated.save(out, format="JPEG", quality=94, optimize=True)
    return out.getvalue()


def _analysis_candidate_score(result: dict[str, Any]) -> float:
    candles = float(result.get("detected_candles") or 0)
    quality = float(result.get("image_quality_score") or 0)
    strategy = float(result.get("pattern_score") or result.get("strategy_score") or 0)
    readable = 0.0 if str(result.get("visual_trend") or "").upper() == "UNREADABLE" else 40.0
    # Candle count dominates because a sharp photo of the wrong/rotated region can still have a high quality score.
    return candles * 12.0 + quality * 0.6 + strategy * 0.25 + readable


def analyze_chart_image_mobile_safe(raw: bytes, timeframe: str = "1m", market: str = "", last_outcome: str = "", *, captured_at_close: bool = False) -> dict[str, Any]:
    """Analyze the frame, rescue sideways mobile photos, then apply a strict signal-quality gate."""
    candidates: list[tuple[int, dict[str, Any]]] = []
    base = analyze_chart_image(raw, timeframe=timeframe, market=market, last_outcome=last_outcome, captured_at_close=captured_at_close)
    candidates.append((0, base))

    base_candles = int(base.get("detected_candles") or 0)
    base_trend = str(base.get("visual_trend") or "").upper()
    # Only spend extra CPU when the original frame is suspicious/too sparse.
    if base_candles < max(MIN_SIGNAL_CANDLES + 4, 18) or base_trend == "UNREADABLE":
        for angle in (90, 270):
            try:
                candidates.append((angle, analyze_chart_image(_rotate_image_bytes(raw, angle), timeframe=timeframe, market=market, last_outcome=last_outcome, captured_at_close=captured_at_close)))
            except Exception:
                pass
        # 180° is less common, so try it only for a very poor original read.
        if base_candles < 8:
            try:
                candidates.append((180, analyze_chart_image(_rotate_image_bytes(raw, 180), timeframe=timeframe, market=market, last_outcome=last_outcome, captured_at_close=captured_at_close)))
            except Exception:
                pass

    angle, best = max(candidates, key=lambda item: _analysis_candidate_score(item[1]))
    best = dict(best)
    best["auto_rotation_degrees"] = int(angle)

    candles = int(best.get("detected_candles") or 0)
    quality = float(best.get("image_quality_score") or 0)
    trend = str(best.get("visual_trend") or "").upper()
    reasons: list[str] = []
    if candles < MIN_SIGNAL_CANDLES:
        reasons.append(f"Only {candles} candles were read; at least {MIN_SIGNAL_CANDLES} clear candles are required for an UP/DOWN signal.")
    if quality < MIN_SIGNAL_IMAGE_QUALITY:
        reasons.append(f"Image quality {quality:.0f}/100 is below the signal threshold {MIN_SIGNAL_IMAGE_QUALITY:.0f}/100.")
    if trend == "UNREADABLE":
        reasons.append("The chart structure is unreadable.")

    rescan_required = bool(reasons)
    best["rescan_required"] = rescan_required
    best["scan_gate"] = "RESCAN" if rescan_required else "PASS"
    best["scan_gate_reason"] = " ".join(reasons) if reasons else "Frame has enough readable candles and image quality."

    if rescan_required:
        # Never emit directional trading guidance from a poor/mobile-misaligned frame.
        best["raw_bias_before_scan_gate"] = best.get("bias")
        best["bias"] = "NO TRADE"
        best["confidence"] = 0.0
        best["selected_strategy"] = "RESCAN REQUIRED"
        best["selected_pattern"] = "RESCAN REQUIRED"
        best["strategy_direction"] = "NONE"
        best["pattern_direction"] = "NONE"
        best["strategy_score"] = 0.0
        best["pattern_score"] = 0.0
        best["setup_match"] = 0.0
        best["next_candle_color"] = "NONE"
        best["entry_instruction"] = "RESCAN FIRST"
        best["recovery_trade"] = False
        best["confluence_count"] = 0
        best["setup_quality"] = "LOW"
        warnings = list(best.get("warnings") or [])
        warnings.insert(0, "Scan Gate blocked UP/DOWN: retake a straight, focused chart photo with more visible candles.")
        best["warnings"] = warnings[:6]
    elif angle:
        notes = list(best.get("warnings") or [])
        notes.append(f"Mobile orientation rescue: chart was auto-rotated {angle}° before analysis.")
        best["warnings"] = notes[:6]

    return best


@app.post("/api/analyze")
def analyze():
    rec, err = validate_session()
    if err:
        payload, code = err
        return jsonify(payload), code
    upload = request.files.get("image")
    if not upload:
        return jsonify({"status": "error", "message": "Camera photo or chart screenshot is required."}), 400
    raw = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        return jsonify({"status": "error", "message": "Image is too large."}), 413
    broker = str(request.form.get("broker") or "").strip()[:60]
    market = str(request.form.get("market") or "").strip()[:40]
    pair = str(request.form.get("pair") or "").strip()[:100]
    timeframe = str(request.form.get("timeframe") or "1m")[:20].lower()
    last_outcome = str(request.form.get("last_outcome") or "").strip().upper()[:16]
    captured_at_close = str(request.form.get("captured_at_close") or "").strip().lower() in {"1", "true", "yes", "on"}
    try:
        capture_boundary_ms = int(float(request.form.get("capture_boundary_ms") or 0))
    except Exception:
        capture_boundary_ms = 0
    broker_key = "PocketOption" if broker == "Pocket Option" else "Quotex" if broker == "Quotex" else ""
    allowed_markets = BROKER_DATA.get(broker_key, {}) if broker_key else {}
    if not broker_key or market not in allowed_markets:
        return jsonify({"status": "error", "message": "Unsupported broker/market selection."}), 400
    if pair not in allowed_markets.get(market, []):
        return jsonify({"status": "error", "message": "Pair is not in the RAJA AI broker pair list."}), 400
    if timeframe not in {"30s", "1m", "2m", "5m", "10m", "15m", "30m"}:
        return jsonify({"status": "error", "message": "Unsupported timeframe."}), 400
    try:
        result = analyze_chart_image_mobile_safe(raw, timeframe=timeframe, market=market, last_outcome=last_outcome, captured_at_close=captured_at_close)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    result.update({"broker": broker, "market": market, "pair": pair, "timeframe": timeframe, "created_at": _now(),
                   "captured_at_close": captured_at_close, "capture_boundary_ms": capture_boundary_ms})
    user = _norm_user(rec.get("user_id"))
    add_scan(user, broker, pair, timeframe, result)
    return jsonify({"status": "success", "result": result})


@app.get("/api/history")
def history():
    rec, err = validate_session()
    if err:
        payload, code = err
        return jsonify(payload), code
    rows = list_scans(_norm_user(rec.get("user_id")), 40)
    return jsonify({"status": "success", "data": rows})


def _admin_ok(data: dict[str, Any]) -> bool:
    supplied = str(data.get("password") or "")
    return bool(ADMIN_PASSWORD and secrets.compare_digest(supplied, ADMIN_PASSWORD))


@app.post("/api/admin/unlock")
def admin_unlock():
    data = request.get_json(silent=True) or {}
    if not _admin_ok(data):
        return jsonify({"status": "error", "message": "Incorrect admin code."}), 403
    return jsonify({"status": "success"})


@app.post("/api/admin/requests")
def admin_requests():
    data = request.get_json(silent=True) or {}
    if not _admin_ok(data):
        return jsonify({"status": "error", "message": "Admin password missing or incorrect."}), 403
    return jsonify({"status": "success", "data": list_requests()})


@app.post("/api/admin/licenses")
def admin_licenses():
    data = request.get_json(silent=True) or {}
    if not _admin_ok(data):
        return jsonify({"status": "error", "message": "Admin password missing or incorrect."}), 403
    now = _now()
    rows = list_licenses()
    for r in rows:
        r["expired"] = bool(r.get("expires_at") and int(r.get("expires_at") or 0) <= now)
        r["online"] = bool(r.get("device_id") and r.get("last_verified_at") and now - int(r.get("last_verified_at") or 0) < 120)
    return jsonify({"status": "success", "data": rows})


@app.post("/api/admin/approve-request")
def approve_request():
    data = request.get_json(silent=True) or {}
    if not _admin_ok(data):
        return jsonify({"status": "error", "message": "Admin password missing or incorrect."}), 403
    rid = int(data.get("request_id") or 0)
    row = get_request(rid)
    if not row:
        return jsonify({"status": "error", "message": "Request not found."}), 404
    if str(row.get("status")) == "APPROVED" and row.get("license_key"):
        return jsonify({"status": "success", "license_key": row.get("license_key"), "already_approved": True})
    req_type = str(row.get("request_type") or "affiliate").lower()
    if req_type == "affiliate":
        # Admin must verify the UID/referral + qualifying deposit in the broker affiliate dashboard first.
        plan = "AFFILIATE PRO"
        duration = None
    else:
        plan = "MONTHLY PRO"
        duration = 30
    key, rec = create_license(_norm_user(row.get("user_id")), plan, duration)
    update_request(rid, "APPROVED", key)
    return jsonify({"status": "success", "license_key": key, "plan": rec.get("plan"), "expires_at": rec.get("expires_at")})


@app.post("/api/admin/reject-request")
def reject_request():
    data = request.get_json(silent=True) or {}
    if not _admin_ok(data):
        return jsonify({"status": "error", "message": "Admin password missing or incorrect."}), 403
    rid = int(data.get("request_id") or 0)
    if not get_request(rid):
        return jsonify({"status": "error", "message": "Request not found."}), 404
    update_request(rid, "REJECTED", None)
    return jsonify({"status": "success"})


@app.post("/api/admin/generate-license")
def admin_generate_license():
    data = request.get_json(silent=True) or {}
    if not _admin_ok(data):
        return jsonify({"status": "error", "message": "Admin password missing or incorrect."}), 403
    user = _norm_user(data.get("user_id"))
    if not user:
        return jsonify({"status": "error", "message": "User/UID is required."}), 400
    plan = str(data.get("plan") or "VIP").strip().upper()[:50]
    try:
        duration = max(0.0, min(3650.0, float(data.get("duration_days") or 0)))
    except Exception:
        duration = 0.0
    if plan == "FREE TRIAL" and get_trial_claim("user", user):
        return jsonify({"status": "error", "message": "This user/UID already used a free trial."}), 409
    key, rec = create_license(user, plan, duration or None)
    if plan == "FREE TRIAL":
        set_trial_claim("user", user, key)
    return jsonify({"status": "success", "license_key": key, "plan": rec.get("plan"), "expires_at": rec.get("expires_at")})


@app.post("/api/admin/license-action")
def admin_license_action():
    data = request.get_json(silent=True) or {}
    if not _admin_ok(data):
        return jsonify({"status": "error", "message": "Admin password missing or incorrect."}), 403
    key = str(data.get("key") or "").strip()
    action = str(data.get("action") or "").strip().lower()
    rec = get_license(key)
    if not rec:
        return jsonify({"status": "error", "message": "License not found."}), 404
    if action == "revoke":
        rec["active"] = False
        rec["session_token"] = None
        save_license(key, rec)
    elif action == "activate":
        rec["active"] = True
        save_license(key, rec)
    elif action == "reset-device":
        rec["device_id"] = None
        rec["device_label"] = None
        rec["session_token"] = None
        save_license(key, rec)
    elif action == "delete":
        delete_license(key)
    else:
        return jsonify({"status": "error", "message": "Unknown action."}), 400
    return jsonify({"status": "success"})


@app.errorhandler(413)
def too_large(_):
    return jsonify({"status": "error", "message": f"Image too large. Max upload is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."}), 413


try:
    init_store()
except Exception as exc:
    print(f"RAJA Scanner store init warning: {exc}")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
