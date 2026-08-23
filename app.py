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
from PIL import Image, ImageOps, UnidentifiedImageError

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


def _detect_candles_in_chart(chart: np.ndarray) -> tuple[list[dict[str, Any]], float, list[str], float, float]:
    """Detect red/green candles with mobile-safe 2D component clustering.

    V9.1 fixes the V9 mobile under-count where 14+ visible Pocket Option candles
    could be reported as 7 because the old X-axis grouping was contaminated by
    wide coloured interface bars. No indicator values are used; geometry remains
    visual-only body/wick estimation.
    """
    ch, cw, _ = chart.shape
    quality, quality_notes = _quality_score(chart)

    r = chart[:, :, 0].astype(np.int16)
    g = chart[:, :, 1].astype(np.int16)
    b = chart[:, :, 2].astype(np.int16)

    # Slightly more tolerant masks for compressed/phone screenshots. Dominance
    # checks still exclude the dark blue/purple broker background.
    red = (r > 84) & ((r - g) > 16) & ((r - b) > 3)
    green = (g > 64) & ((g - r) > 10) & ((g - b) > -42)
    cyan = (g > 88) & (b > 88) & (r < 185) & (((g + b) - 2 * r) > 24)
    bull = green | cyan
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

def analyze_chart_image(raw: bytes) -> dict[str, Any]:
    """V9 pure price-action/pattern scan from a chart image.

    No RSI, EMA, MACD, stochastic, Bollinger or other indicator values are used.
    The engine evaluates visible candle geometry and a small set of chart-pattern
    contexts. A weak/conflicting setup returns NO TRADE.
    """
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Image could not be opened. Upload a PNG/JPG chart screenshot.") from exc

    w0, h0 = image.size
    if w0 < 240 or h0 < 180:
        raise ValueError("Image is too small. Use a clearer chart screenshot.")

    max_dim = 1800.0 if h0 > w0 * 1.12 else 1600.0
    scale = min(1.0, max_dim / max(w0, h0))
    if scale < 1.0:
        image = image.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))), Image.Resampling.LANCZOS)
    arr = np.asarray(image, dtype=np.uint8)

    best_region = None
    best_region_score = -1e9
    for crop_name, candidate in _candidate_chart_regions(arr):
        cands, q, qnotes, span, density = _detect_candles_in_chart(candidate)
        score = min(len(cands), 60) * 3.2 + min(1.0, span / 0.55) * 34.0 + min(18.0, density * 900.0) + q * 0.16
        if len(cands) < 6:
            score -= 22.0
        if score > best_region_score:
            best_region_score = score
            best_region = (crop_name, candidate, cands, q, qnotes)

    if best_region is None:
        crop_name, chart = "full-image", arr
        candles, quality, quality_notes, _, _ = _detect_candles_in_chart(chart)
    else:
        crop_name, chart, candles, quality, quality_notes = best_region

    ch, cw, _ = chart.shape
    count = len(candles)
    warnings = list(quality_notes)
    reasons: list[str] = []

    def legacy_aliases(pattern: str, direction: str, score: float, signals: list[dict[str, Any]], library: str, size: int) -> dict[str, Any]:
        # Keep old field names so the V8 history/timer code continues to work.
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
        library = "Candlestick + Price Action Pattern Library V9"
        return {
            "bias": "NO TRADE", "confidence": 0.0, "image_quality_score": quality,
            "detected_candles": count, "visual_trend": "UNREADABLE", "momentum": "UNREADABLE", "volatility": "UNKNOWN",
            "selected_pattern": "NO CLEAN PATTERN", "pattern_direction": "NONE", "pattern_score": 0.0,
            "pattern_signals": [], "pattern_library": library, "pattern_library_size": 29,
            "confluence_count": 0, "setup_quality": "LOW",
            "reasons": ["Insufficient readable candle structure for pattern recognition."], "warnings": warnings,
            "pattern_status": {"Candle geometry": "Unreadable", "Pattern context": "Unreadable"},
            "engine": "RAJA Pattern-Only Engine V9.1 · Candle Count Fix + V8 Scan Gate", "analysis_crop_mode": crop_name,
            **legacy_aliases("NO CLEAN PATTERN", "NONE", 0.0, [], library, 29),
        }

    ys = np.array([c["y"] for c in candles], dtype=float)
    dirs = np.array([c["dir"] for c in candles], dtype=float)
    ranges = np.array([c["range"] for c in candles], dtype=float)

    def trend_before(end_idx: int, lookback: int = 7) -> float:
        start = max(0, end_idx - lookback)
        seq = candles[start:end_idx]
        if len(seq) < 3:
            return 0.0
        yv = np.array([c["y"] for c in seq], dtype=float) / max(ch, 1)
        xv = np.arange(len(seq), dtype=float)
        slope = float(np.polyfit(xv, yv, 1)[0]) if len(seq) > 1 else 0.0
        # Positive means bullish/uptrend; screen Y falls when price rises.
        return float(np.clip(-slope * 18.0, -1.0, 1.0))

    def body_contains(a: dict[str, Any], b: dict[str, Any], tol: float = 2.0) -> bool:
        return a["body_top"] <= b["body_top"] + tol and a["body_bottom"] >= b["body_bottom"] - tol

    def small_body(c: dict[str, Any]) -> float:
        return float(np.clip((0.38 - c["body_ratio"]) / 0.30, 0.0, 1.0))

    signals: list[dict[str, Any]] = []
    def add_pattern(name: str, direction: int, score: float, why: str, family: str = "Candlestick") -> None:
        score = float(np.clip(score, 0.0, 1.0))
        if score < 0.46:
            return
        signals.append({"name": name, "direction": "UP" if direction > 0 else "DOWN", "score": round(score * 100.0, 1), "why": why, "family": family})

    # ---------- Single-candle patterns from the newest candle ----------
    c = candles[-1]
    ctx = trend_before(len(candles) - 1)
    rng = max(c["range"], 1.0)
    body = max(c["body_height"], 1.0)
    upper_r = c["upper_wick"] / rng
    lower_r = c["lower_wick"] / rng
    body_r = c["body_ratio"]
    doji = body_r <= 0.24

    hammer_shape = min(1.0, lower_r / 0.52) * 0.50 + min(1.0, max(0.0, 0.46 - body_r) / 0.34) * 0.24 + min(1.0, max(0.0, 0.24 - upper_r) / 0.24) * 0.12
    upper_pin_shape = min(1.0, upper_r / 0.52) * 0.50 + min(1.0, max(0.0, 0.46 - body_r) / 0.34) * 0.24 + min(1.0, max(0.0, 0.24 - lower_r) / 0.24) * 0.12
    add_pattern("Hammer", 1, hammer_shape + max(0.0, -ctx) * 0.14, "Long lower wick with a small body after bearish/downward context.")
    add_pattern("Hanging Man", -1, hammer_shape + max(0.0, ctx) * 0.14, "Hammer-like candle appears after bullish/upward context, warning of rejection.")
    add_pattern("Inverted Hammer", 1, upper_pin_shape + max(0.0, -ctx) * 0.14, "Long upper wick and small body after bearish/downward context.")
    add_pattern("Shooting Star", -1, upper_pin_shape + max(0.0, ctx) * 0.14, "Long upper wick and small body after bullish/upward context.")

    if doji:
        dragon = min(1.0, lower_r / 0.60) * 0.62 + min(1.0, max(0.0, 0.20 - upper_r) / 0.20) * 0.18 + max(0.0, -ctx) * 0.20
        grave = min(1.0, upper_r / 0.60) * 0.62 + min(1.0, max(0.0, 0.20 - lower_r) / 0.20) * 0.18 + max(0.0, ctx) * 0.20
        add_pattern("Dragonfly Doji", 1, dragon, "Doji-like body with dominant lower wick near bearish/downward context.")
        add_pattern("Gravestone Doji", -1, grave, "Doji-like body with dominant upper wick near bullish/upward context.")

    # ---------- Two-candle patterns ----------
    if count >= 2:
        a, b = candles[-2], candles[-1]
        ctx2 = trend_before(len(candles) - 2)
        tol = max(2.0, float(np.median(ranges[-min(count, 20):])) * 0.10)
        engulf = body_contains(b, a, tol)
        harami = body_contains(a, b, tol) and b["body_height"] <= a["body_height"] * 0.82
        size_edge = min(1.0, b["body_height"] / max(a["body_height"], 1.0) / 1.25)

        if a["dir"] < 0 and b["dir"] > 0:
            add_pattern("Bullish Engulfing", 1, (0.58 if engulf else 0.0) + size_edge * 0.22 + max(0.0, -ctx2) * 0.20, "Bullish body visually engulfs the preceding bearish body.")
            add_pattern("Bullish Harami", 1, (0.62 if harami else 0.0) + max(0.0, -ctx2) * 0.22 + small_body(b) * 0.16, "Small bullish body sits inside a larger bearish body after downward context.")
            midpoint = (a["body_top"] + a["body_bottom"]) / 2.0
            piercing_depth = float(np.clip((midpoint - b["close_y"]) / max(a["body_height"] * 0.50, 1.0), 0.0, 1.0))
            add_pattern("Piercing Line", 1, piercing_depth * 0.62 + max(0.0, -ctx2) * 0.22 + min(1.0, b["body_ratio"] / 0.55) * 0.16, "Bullish candle closes deeply into the preceding bearish body.")
        if a["dir"] > 0 and b["dir"] < 0:
            add_pattern("Bearish Engulfing", -1, (0.58 if engulf else 0.0) + size_edge * 0.22 + max(0.0, ctx2) * 0.20, "Bearish body visually engulfs the preceding bullish body.")
            add_pattern("Bearish Harami", -1, (0.62 if harami else 0.0) + max(0.0, ctx2) * 0.22 + small_body(b) * 0.16, "Small bearish body sits inside a larger bullish body after upward context.")
            midpoint = (a["body_top"] + a["body_bottom"]) / 2.0
            cloud_depth = float(np.clip((b["close_y"] - midpoint) / max(a["body_height"] * 0.50, 1.0), 0.0, 1.0))
            add_pattern("Dark Cloud Cover", -1, cloud_depth * 0.62 + max(0.0, ctx2) * 0.22 + min(1.0, b["body_ratio"] / 0.55) * 0.16, "Bearish candle closes deeply into the preceding bullish body.")

        bottom_tol = max(3.0, float(np.median(ranges[-min(20, count):])) * 0.14)
        if a["dir"] < 0 and b["dir"] > 0 and abs(a["bottom"] - b["bottom"]) <= bottom_tol:
            add_pattern("Tweezer Bottom", 1, 0.60 + max(0.0, -ctx2) * 0.25 + min(0.15, b["lower_wick"] / max(b["range"], 1.0) * 0.25), "Two recent candles reject a similar visual low.")
        if a["dir"] > 0 and b["dir"] < 0 and abs(a["top"] - b["top"]) <= bottom_tol:
            add_pattern("Tweezer Top", -1, 0.60 + max(0.0, ctx2) * 0.25 + min(0.15, b["upper_wick"] / max(b["range"], 1.0) * 0.25), "Two recent candles reject a similar visual high.")

    # ---------- Three-candle patterns ----------
    if count >= 3:
        a, b, c3 = candles[-3], candles[-2], candles[-1]
        ctx3 = trend_before(len(candles) - 3)
        mid_a = (a["body_top"] + a["body_bottom"]) / 2.0
        morning = a["dir"] < 0 and small_body(b) > 0.35 and c3["dir"] > 0 and c3["close_y"] < mid_a
        evening = a["dir"] > 0 and small_body(b) > 0.35 and c3["dir"] < 0 and c3["close_y"] > mid_a
        add_pattern("Morning Doji Star" if b["body_ratio"] <= 0.24 else "Morning Star", 1, (0.66 if morning else 0.0) + max(0.0, -ctx3) * 0.22 + min(0.12, c3["body_ratio"] * 0.18), "Bearish move pauses with a small middle candle, then a strong bullish response.")
        add_pattern("Evening Doji Star" if b["body_ratio"] <= 0.24 else "Evening Star", -1, (0.66 if evening else 0.0) + max(0.0, ctx3) * 0.22 + min(0.12, c3["body_ratio"] * 0.18), "Bullish move pauses with a small middle candle, then a strong bearish response.")

        if all(x["dir"] > 0 for x in (a,b,c3)):
            closes = [a["close_y"], b["close_y"], c3["close_y"]]
            progressive = closes[2] < closes[1] < closes[0]
            score = (0.64 if progressive else 0.48) + min(0.20, float(np.mean([a["body_ratio"],b["body_ratio"],c3["body_ratio"]])) * 0.25) + max(0.0, -ctx3) * 0.12
            add_pattern("Three White Soldiers", 1, score, "Three bullish candles advance progressively higher.")
        if all(x["dir"] < 0 for x in (a,b,c3)):
            closes = [a["close_y"], b["close_y"], c3["close_y"]]
            progressive = closes[2] > closes[1] > closes[0]
            score = (0.64 if progressive else 0.48) + min(0.20, float(np.mean([a["body_ratio"],b["body_ratio"],c3["body_ratio"]])) * 0.25) + max(0.0, ctx3) * 0.12
            add_pattern("Three Black Crows", -1, score, "Three bearish candles advance progressively lower.")

        tol = max(2.0, float(np.median(ranges[-min(count, 20):])) * 0.10)
        first_inside = body_contains(a, b, tol) and b["body_height"] < a["body_height"]
        first_engulf = body_contains(b, a, tol)
        if a["dir"] < 0 and b["dir"] > 0 and first_inside and c3["dir"] > 0 and c3["close_y"] < b["close_y"]:
            add_pattern("Three Inside Up", 1, 0.74 + max(0.0, -ctx3) * 0.18, "Bullish harami-style inside setup receives a third-candle upside confirmation.")
        if a["dir"] > 0 and b["dir"] < 0 and first_inside and c3["dir"] < 0 and c3["close_y"] > b["close_y"]:
            add_pattern("Three Inside Down", -1, 0.74 + max(0.0, ctx3) * 0.18, "Bearish harami-style inside setup receives a third-candle downside confirmation.")
        if a["dir"] < 0 and b["dir"] > 0 and first_engulf and c3["dir"] > 0 and c3["close_y"] < b["close_y"]:
            add_pattern("Three Outside Up", 1, 0.76 + max(0.0, -ctx3) * 0.16, "Bullish engulfing setup receives a third-candle upside confirmation.")
        if a["dir"] > 0 and b["dir"] < 0 and first_engulf and c3["dir"] < 0 and c3["close_y"] > b["close_y"]:
            add_pattern("Three Outside Down", -1, 0.76 + max(0.0, ctx3) * 0.16, "Bearish engulfing setup receives a third-candle downside confirmation.")

    # ---------- Price-action / chart context patterns from the uploaded guides ----------
    if count >= 10:
        prior = candles[-12:-2] if count >= 12 else candles[:-2]
        if len(prior) >= 5:
            resistance_y = float(min(x["top"] for x in prior))
            support_y = float(max(x["bottom"] for x in prior))
            span = max(10.0, support_y - resistance_y)
            last = candles[-1]
            near_support = 1.0 - min(1.0, abs(last["bottom"] - support_y) / max(span * 0.16, 2.0))
            near_resistance = 1.0 - min(1.0, abs(last["top"] - resistance_y) / max(span * 0.16, 2.0))
            wick_low = min(1.0, last["lower_wick"] / max(last["body_height"] * 1.6, 1.0))
            wick_high = min(1.0, last["upper_wick"] / max(last["body_height"] * 1.6, 1.0))
            add_pattern("Support Rejection", 1, near_support * 0.46 + wick_low * 0.34 + (0.20 if last["dir"] > 0 else 0.0), "Newest candle rejects a recent visual support area.", "Price Action")
            add_pattern("Resistance Rejection", -1, near_resistance * 0.46 + wick_high * 0.34 + (0.20 if last["dir"] < 0 else 0.0), "Newest candle rejects a recent visual resistance area.", "Price Action")

            # Breakout + retest: previous candle breaches the old boundary, latest returns near it and responds.
            prev = candles[-2]
            buffer_px = max(2.0, span * 0.05)
            up_breach = prev["close_y"] < resistance_y - buffer_px
            dn_breach = prev["close_y"] > support_y + buffer_px
            retest_res = 1.0 - min(1.0, abs(last["y"] - resistance_y) / max(span * 0.18, 2.0))
            retest_sup = 1.0 - min(1.0, abs(last["y"] - support_y) / max(span * 0.18, 2.0))
            add_pattern("Breakout & Retest", 1, (0.52 if up_breach else 0.0) + retest_res * 0.28 + (0.20 if last["dir"] > 0 else 0.0), "Upside breakout is followed by a visual retest/hold of the old resistance area.", "Chart Pattern")
            add_pattern("Breakout & Retest", -1, (0.52 if dn_breach else 0.0) + retest_sup * 0.28 + (0.20 if last["dir"] < 0 else 0.0), "Downside breakout is followed by a visual retest/hold of the old support area.", "Chart Pattern")

            # Double top/bottom approximation using repeated extremes in the latest window.
            recent = candles[-16:] if count >= 16 else candles
            sep = 3
            bottoms = sorted([(float(x["bottom"]), i) for i,x in enumerate(recent)], reverse=True)
            tops = sorted([(float(x["top"]), i) for i,x in enumerate(recent)])
            for arr_ext, direction, name in ((bottoms, 1, "Double Bottom"), (tops, -1, "Double Top")):
                found = None
                for v1,i1 in arr_ext[:6]:
                    for v2,i2 in arr_ext[:8]:
                        if abs(i1-i2) < sep:
                            continue
                        if abs(v1-v2) <= max(4.0, span*0.10):
                            found = (v1,v2,i1,i2); break
                    if found: break
                if found:
                    confirm = 0.18 if (last["dir"] > 0 if direction > 0 else last["dir"] < 0) else 0.0
                    add_pattern(name, direction, 0.58 + confirm + min(0.16, abs(trend_before(len(candles)-1))*0.16), f"Two separated tests formed near a similar visual {'low' if direction>0 else 'high'} with reversal response.", "Chart Pattern")

    signals.sort(key=lambda s: float(s["score"]), reverse=True)
    best = signals[0] if signals else None
    best_score = float(best["score"]) if best else 0.0
    up = [s for s in signals if s["direction"] == "UP" and float(s["score"]) >= 58.0]
    down = [s for s in signals if s["direction"] == "DOWN" and float(s["score"]) >= 58.0]
    up_vote = sum(float(s["score"]) for s in up)
    down_vote = sum(float(s["score"]) for s in down)
    direction = "UP" if up_vote > down_vote else "DOWN" if down_vote > up_vote else "NONE"
    same = up if direction == "UP" else down if direction == "DOWN" else []
    confluence = len(same)
    opposite = down if direction == "UP" else up if direction == "DOWN" else []
    strongest_opp = max([float(s["score"]) for s in opposite], default=0.0)
    conflict = bool(best and strongest_opp >= max(65.0, best_score - 7.0))

    pattern_ok = bool(best and best_score >= 66.0)
    confluence_ok = confluence >= 2 or best_score >= 84.0
    structure_ok = count >= 10 and quality >= 45.0
    no_trade = not (pattern_ok and confluence_ok and structure_ok and not conflict and direction != "NONE")

    if best:
        reasons.append(f"Best pattern: {best['name']} ({best['direction']}) at {best_score:.0f}% visual pattern score.")
    if confluence:
        reasons.append(f"{confluence} pattern confirmations agree on {direction}.")
    if conflict:
        reasons.append("A strong opposite-direction pattern is also present, so the signal is blocked.")
    if not pattern_ok:
        reasons.append("No current pattern reached the minimum pattern threshold.")
    elif not confluence_ok:
        reasons.append("The pattern needs another confirmation; waiting is preferred.")

    if no_trade:
        bias = "NO TRADE"
        confidence = min(68.0, round(best_score * 0.72 + quality * 0.10 + min(confluence,3) * 2.0, 1)) if best else 0.0
    else:
        bias = "UP BIAS" if direction == "UP" else "DOWN BIAS"
        confidence = round(min(94.0, 45.0 + best_score * 0.36 + min(confluence,4) * 4.0 + quality * 0.08), 1)

    setup_quality = "HIGH" if not no_trade and best_score >= 80 and confluence >= 2 and quality >= 65 else "MEDIUM" if not no_trade else "LOW"
    selected = best["name"] if best else "NO CLEAN PATTERN"
    selected_dir = best["direction"] if best else "NONE"
    library = "Candlestick + Price Action Pattern Library V9"

    # Context is used only to validate candle patterns; no technical indicator values are calculated.
    global_ctx = trend_before(len(candles), min(12, count))
    context_label = "UPWARD" if global_ctx > 0.15 else "DOWNWARD" if global_ctx < -0.15 else "SIDEWAYS/MIXED"
    if quality < 65:
        warnings.append("Image is usable but a sharper screenshot/photo would improve candle-pattern geometry.")

    pattern_signals = signals[:10]
    result = {
        "bias": bias, "confidence": confidence, "image_quality_score": quality, "detected_candles": count,
        "visual_trend": context_label, "momentum": "PATTERN ONLY", "volatility": "NOT USED",
        "selected_pattern": selected, "pattern_direction": selected_dir, "pattern_score": round(best_score,1),
        "pattern_signals": pattern_signals, "pattern_library": library, "pattern_library_size": 29,
        "confluence_count": int(confluence), "setup_quality": setup_quality,
        "reasons": reasons[:8], "warnings": warnings[:6],
        "pattern_status": {
            "Mode": "Pure candlestick + price-action pattern recognition",
            "Indicators": "OFF — RSI/EMA/MACD/Stochastic/Bollinger are not used",
            "Context": f"Visual candle context: {context_label}",
            "Candle geometry": f"{count} candle-like structures with body/wick estimates",
        },
        "engine": "RAJA Pattern-Only Engine V9.1 · Candle Count Fix + V8 Focus + Scan Gate", "analysis_crop_mode": crop_name,
    }
    result.update(legacy_aliases(selected, selected_dir, round(best_score,1), pattern_signals, library, 29))
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
        "version": "5.0.0",
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


def analyze_chart_image_mobile_safe(raw: bytes) -> dict[str, Any]:
    """Analyze the frame, rescue sideways mobile photos, then apply a strict signal-quality gate."""
    candidates: list[tuple[int, dict[str, Any]]] = []
    base = analyze_chart_image(raw)
    candidates.append((0, base))

    base_candles = int(base.get("detected_candles") or 0)
    base_trend = str(base.get("visual_trend") or "").upper()
    # Only spend extra CPU when the original frame is suspicious/too sparse.
    if base_candles < max(MIN_SIGNAL_CANDLES + 4, 18) or base_trend == "UNREADABLE":
        for angle in (90, 270):
            try:
                candidates.append((angle, analyze_chart_image(_rotate_image_bytes(raw, angle))))
            except Exception:
                pass
        # 180° is less common, so try it only for a very poor original read.
        if base_candles < 8:
            try:
                candidates.append((180, analyze_chart_image(_rotate_image_bytes(raw, 180))))
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
    try:
        result = analyze_chart_image_mobile_safe(raw)
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    broker = str(request.form.get("broker") or "").strip()[:60]
    market = str(request.form.get("market") or "").strip()[:40]
    pair = str(request.form.get("pair") or "").strip()[:100]
    timeframe = str(request.form.get("timeframe") or "1m")[:20]
    broker_key = "PocketOption" if broker == "Pocket Option" else "Quotex" if broker == "Quotex" else ""
    allowed_markets = BROKER_DATA.get(broker_key, {}) if broker_key else {}
    if not broker_key or market not in allowed_markets:
        return jsonify({"status": "error", "message": "Unsupported broker/market selection."}), 400
    if pair not in allowed_markets.get(market, []):
        return jsonify({"status": "error", "message": "Pair is not in the RAJA AI broker pair list."}), 400
    result.update({"broker": broker, "market": market, "pair": pair, "timeframe": timeframe, "created_at": _now()})
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
