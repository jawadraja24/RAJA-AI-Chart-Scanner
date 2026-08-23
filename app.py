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
from flask import Flask, jsonify, request, send_from_directory
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


def analyze_chart_image(raw: bytes) -> dict[str, Any]:
    try:
        image = Image.open(io.BytesIO(raw))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Image could not be opened. Upload a PNG/JPG chart screenshot.") from exc

    w0, h0 = image.size
    if w0 < 240 or h0 < 180:
        raise ValueError("Image is too small. Use a clearer chart screenshot.")

    scale = min(1.0, 1400.0 / max(w0, h0))
    if scale < 1.0:
        image = image.resize(
            (max(1, int(w0 * scale)), max(1, int(h0 * scale))),
            Image.Resampling.LANCZOS,
        )

    arr = np.asarray(image, dtype=np.uint8)
    h, w, _ = arr.shape

    # Focus the quality check and strategy engine on the useful chart area instead
    # of browser chrome / broker sidebars. This prevents clear screenshots from
    # being falsely labelled blurry because large dark UI areas have few edges.
    x1, x2 = int(w * 0.035), int(w * 0.86)
    y1, y2 = int(h * 0.24), int(h * 0.94)
    if x2 - x1 < 220 or y2 - y1 < 160:
        x1, x2 = int(w * 0.06), int(w * 0.94)
        y1, y2 = int(h * 0.12), int(h * 0.90)

    chart = arr[y1:y2, x1:x2]
    ch, cw, _ = chart.shape
    quality, quality_notes = _quality_score(chart)

    r = chart[:, :, 0].astype(np.int16)
    g = chart[:, :, 1].astype(np.int16)
    b = chart[:, :, 2].astype(np.int16)

    # Common red/green/cyan candle themes used by broker chart UIs.
    red = (r > 135) & (r > g * 1.18) & (r > b * 1.10)
    green = (g > 115) & (g > r * 1.10) & (g > b * 0.72)
    cyan = (g > 120) & (b > 120) & (r < 150) & ((g + b) > (r * 1.9 + 70))
    bull = green | cyan
    colored = red | bull

    per_col = colored.sum(axis=0)
    threshold = max(3, int(ch * 0.0055))
    active = per_col >= threshold
    groups = _group_columns(active)

    candles: list[dict[str, Any]] = []
    for left, right in groups:
        width = right - left + 1
        if width > max(38, int(cw * 0.045)):
            continue
        block = colored[:, left:right + 1]
        ys, _ = np.where(block)
        if len(ys) < 6:
            continue
        height = int(ys.max() - ys.min() + 1)
        if height < 4 or height > int(ch * 0.68):
            continue
        red_count = int(red[:, left:right + 1].sum())
        bull_count = int(bull[:, left:right + 1].sum())
        direction = 1 if bull_count >= red_count else -1
        candles.append({
            "x": float((left + right) / 2.0),
            "y": float(np.median(ys)),
            "top": int(ys.min()),
            "bottom": int(ys.max()),
            "dir": direction,
            "pixels": int(len(ys)),
            "range": float(height),
        })

    # Merge body/wick fragments from the same visual candle.
    merged: list[dict[str, Any]] = []
    for c in candles:
        if merged and abs(c["x"] - merged[-1]["x"]) <= 3:
            prev = merged[-1]
            total = prev["pixels"] + c["pixels"]
            prev["y"] = (prev["y"] * prev["pixels"] + c["y"] * c["pixels"]) / max(total, 1)
            prev["x"] = (prev["x"] + c["x"]) / 2
            prev["top"] = min(prev["top"], c["top"])
            prev["bottom"] = max(prev["bottom"], c["bottom"])
            prev["range"] = float(prev["bottom"] - prev["top"] + 1)
            prev["dir"] = c["dir"] if c["pixels"] > prev["pixels"] else prev["dir"]
            prev["pixels"] = total
        else:
            merged.append(dict(c))
    candles = merged[-70:]

    reasons: list[str] = []
    warnings = list(quality_notes)
    count = len(candles)

    empty_strategy = {
        "selected_strategy": "NO CLEAN STRATEGY",
        "strategy_direction": "NONE",
        "strategy_score": 0.0,
        "confluence_count": 0,
        "setup_quality": "LOW",
        "strategy_signals": [],
    }

    if count < 6:
        warnings.append("Not enough colored candle structure was detected. Crop closer to the candle chart or select the correct broker theme.")
        return {
            "bias": "NO TRADE",
            "confidence": 0.0,
            "image_quality_score": quality,
            "detected_candles": count,
            "visual_trend": "UNREADABLE",
            "momentum": "UNREADABLE",
            "volatility": "UNKNOWN",
            "reasons": ["Insufficient readable candle structure for a directional setup."],
            "warnings": warnings,
            **empty_strategy,
            "indicator_status": {
                "Trend / EMA structure": "Not enough readable candle structure",
                "Momentum / RSI proxy": "Not enough readable candle structure",
                "MACD-style momentum": "Not enough readable candle structure",
                "Bollinger-style volatility": "Not enough readable candle structure",
                "Support / Resistance": "Not enough readable candle structure",
                "Price Action": "Visual scan attempted",
            },
            "strategy_library": "Classic TA 15-Setup Library",
            "strategy_library_size": 15,
            "engine": "RAJA Classic TA Strategy Engine V4",
        }

    xs = np.array([c["x"] for c in candles], dtype=float)
    ys = np.array([c["y"] for c in candles], dtype=float)
    dirs = np.array([c["dir"] for c in candles], dtype=float)
    ranges = np.array([c["range"] for c in candles], dtype=float)

    if np.ptp(xs) <= 1:
        slope = 0.0
    else:
        xnorm = (xs - xs.min()) / np.ptp(xs)
        ynorm = ys / max(ch, 1)
        slope = float(np.polyfit(xnorm, ynorm, 1)[0])

    # y decreases when price moves higher on screen.
    trend_strength = float(np.clip(-slope * 4.6, -1.0, 1.0))

    n_recent = max(3, min(7, count // 3))
    recent_y = float(np.mean(ys[-n_recent:]))
    prior_slice = ys[-2 * n_recent:-n_recent] if count >= 2 * n_recent else ys[:max(1, count - n_recent)]
    prior_y = float(np.mean(prior_slice)) if len(prior_slice) else recent_y
    recent_strength = float(np.clip((prior_y - recent_y) / max(ch * 0.075, 1.0), -1.0, 1.0))

    recent_dirs = dirs[-min(12, count):]
    color_strength = float(np.mean(recent_dirs)) if len(recent_dirs) else 0.0
    last3_color = float(np.mean(dirs[-min(3, count):]))

    diffs = np.diff(ys[-min(24, count):]) if count > 1 else np.array([0.0])
    vol = float(np.std(diffs) / max(ch, 1))
    if vol < 0.010:
        volatility = "LOW"
    elif vol < 0.032:
        volatility = "NORMAL"
    else:
        volatility = "HIGH"

    trend_label = "BULLISH" if trend_strength > 0.14 else "BEARISH" if trend_strength < -0.14 else "SIDEWAYS"
    momentum_label = "UP" if recent_strength > 0.12 else "DOWN" if recent_strength < -0.12 else "MIXED"

    # ---------------- Classic TA / book-inspired strategy engine V4 ----------------
    # This library translates classical technical-analysis ideas into visual proxies.
    # It does NOT fabricate exact EMA/RSI/MACD values from screenshots and it does not
    # promise a winning trade. Each setup contributes only when its visible structure
    # is strong enough, then the conservative confluence gate can still return NO TRADE.
    signals: list[dict[str, Any]] = []

    def add_signal(name: str, direction: int, score: float, why: str) -> None:
        score = float(np.clip(score, 0.0, 1.0))
        if score < 0.34:
            return
        signals.append({
            "name": name,
            "direction": "UP" if direction > 0 else "DOWN",
            "score": round(score * 100.0, 1),
            "why": why,
        })

    # Shared range context used by several chart-pattern strategies.
    base_n = min(max(8, count - 4), count)
    base = ys[-base_n:-3] if count >= 9 else ys[:-2]
    prev_high_y = float(np.min(base)) if len(base) >= 4 else float(np.min(ys[:-1]))
    prev_low_y = float(np.max(base)) if len(base) >= 4 else float(np.max(ys[:-1]))
    prior_span = max(prev_low_y - prev_high_y, ch * 0.04)
    buffer_px = max(2.0, ch * 0.008)
    last_mean = float(np.mean(ys[-2:]))
    near_res = 1.0 - min(1.0, abs(float(ys[-2]) - prev_high_y) / max(prior_span * 0.22, 1.0))
    near_sup = 1.0 - min(1.0, abs(float(ys[-2]) - prev_low_y) / max(prior_span * 0.22, 1.0))

    # 1) Trend Continuation — classical trend-following alignment.
    up_cont = max(0.0, trend_strength) * 0.44 + max(0.0, recent_strength) * 0.34 + max(0.0, color_strength) * 0.22
    dn_cont = max(0.0, -trend_strength) * 0.44 + max(0.0, -recent_strength) * 0.34 + max(0.0, -color_strength) * 0.22
    add_signal("Trend Continuation", 1, up_cont, "Uptrend, recent displacement and bullish candle colour are aligned.")
    add_signal("Trend Continuation", -1, dn_cont, "Downtrend, recent displacement and bearish candle colour are aligned.")

    # 2) Pullback Continuation — trend, counter-move, then resumption.
    if count >= 6:
        pre = float(np.mean(dirs[-5:-2]))
        resume = float(np.mean(dirs[-2:]))
        up_pull = max(0.0, trend_strength) * 0.48 + max(0.0, -pre) * 0.22 + max(0.0, resume) * 0.30
        dn_pull = max(0.0, -trend_strength) * 0.48 + max(0.0, pre) * 0.22 + max(0.0, -resume) * 0.30
        add_signal("Pullback Continuation", 1, up_pull, "Bullish structure shows a counter-move followed by renewed buying candles.")
        add_signal("Pullback Continuation", -1, dn_pull, "Bearish structure shows a counter-move followed by renewed selling candles.")

    # 3) Micro Trend Structure — recent higher/lower candle path agrees with direction.
    if count >= 8:
        micro_now = float(np.mean(ys[-3:]))
        micro_prev = float(np.mean(ys[-7:-3]))
        micro_shift = float(np.clip((micro_prev - micro_now) / max(ch * 0.055, 1.0), -1.0, 1.0))
        up_micro = max(0.0, micro_shift) * 0.58 + max(0.0, last3_color) * 0.42
        dn_micro = max(0.0, -micro_shift) * 0.58 + max(0.0, -last3_color) * 0.42
        add_signal("Micro Trend Structure", 1, up_micro, "The latest candle cluster is stepping higher with bullish colour confirmation.")
        add_signal("Micro Trend Structure", -1, dn_micro, "The latest candle cluster is stepping lower with bearish colour confirmation.")

    # 4) Range Breakout — newest candles push outside the preceding visible range.
    if len(base) >= 4:
        up_distance = max(0.0, (prev_high_y - last_mean - buffer_px) / max(ch * 0.045, 1.0))
        dn_distance = max(0.0, (last_mean - prev_low_y - buffer_px) / max(ch * 0.045, 1.0))
        up_break = min(1.0, up_distance) * 0.62 + max(0.0, last3_color) * 0.38
        dn_break = min(1.0, dn_distance) * 0.62 + max(0.0, -last3_color) * 0.38
        add_signal("Range Breakout", 1, up_break, "Recent candles are pushing above the preceding visible price range.")
        add_signal("Range Breakout", -1, dn_break, "Recent candles are pushing below the preceding visible price range.")

        # 5) Breakout Retest — a recent breach returns to the boundary and resumes.
        if count >= 7:
            recent4 = ys[-4:]
            breached_up = float(np.min(recent4[:-1])) < (prev_high_y - buffer_px)
            breached_dn = float(np.max(recent4[:-1])) > (prev_low_y + buffer_px)
            retest_res = 1.0 - min(1.0, abs(float(ys[-1]) - prev_high_y) / max(prior_span * 0.18, 1.0))
            retest_sup = 1.0 - min(1.0, abs(float(ys[-1]) - prev_low_y) / max(prior_span * 0.18, 1.0))
            up_retest = (0.46 if breached_up else 0.0) + max(0.0, retest_res) * 0.28 + max(0.0, dirs[-1]) * 0.26
            dn_retest = (0.46 if breached_dn else 0.0) + max(0.0, retest_sup) * 0.28 + max(0.0, -dirs[-1]) * 0.26
            add_signal("Breakout Retest", 1, up_retest, "A recent upside break is retesting the old boundary with bullish response.")
            add_signal("Breakout Retest", -1, dn_retest, "A recent downside break is retesting the old boundary with bearish response.")

        # 6) Support Rejection.
        up_reject = max(0.0, near_sup) * 0.48 + max(0.0, dirs[-1]) * 0.30 + max(0.0, recent_strength) * 0.22
        add_signal("Support Rejection", 1, up_reject, "Price tested a recent visual low/support area and bullish candles reacted.")

        # 7) Resistance Rejection.
        dn_reject = max(0.0, near_res) * 0.48 + max(0.0, -dirs[-1]) * 0.30 + max(0.0, -recent_strength) * 0.22
        add_signal("Resistance Rejection", -1, dn_reject, "Price tested a recent visual high/resistance area and bearish candles reacted.")

        # 8) Range Rejection — mean-reversion only when broader trend is weak.
        if abs(trend_strength) < 0.22:
            side_bonus = max(0.0, 1.0 - abs(trend_strength) / 0.22)
            up_range = up_reject * 0.70 + side_bonus * 0.30
            dn_range = dn_reject * 0.70 + side_bonus * 0.30
            add_signal("Range Rejection", 1, up_range, "Sideways structure rejected a recent lower boundary.")
            add_signal("Range Rejection", -1, dn_range, "Sideways structure rejected a recent upper boundary.")

        # 9) Failed Breakout Reversal — breach then quick return inside the range.
        if count >= 5:
            penult_y = float(ys[-2])
            last_y = float(ys[-1])
            failed_up = penult_y < (prev_high_y - buffer_px) and last_y >= prev_high_y and dirs[-1] < 0
            failed_dn = penult_y > (prev_low_y + buffer_px) and last_y <= prev_low_y and dirs[-1] > 0
            fail_up_score = (0.66 if failed_up else 0.0) + max(0.0, -dirs[-1]) * 0.16 + max(0.0, -recent_strength) * 0.18
            fail_dn_score = (0.66 if failed_dn else 0.0) + max(0.0, dirs[-1]) * 0.16 + max(0.0, recent_strength) * 0.18
            add_signal("Failed Breakout Reversal", -1, fail_up_score, "Price briefly broke above resistance but returned inside with bearish rejection.")
            add_signal("Failed Breakout Reversal", 1, fail_dn_score, "Price briefly broke below support but returned inside with bullish rejection.")

        # 10) Double-Test Reversal — two touches near an edge plus latest rejection.
        look = ys[-min(18, count):]
        tol = max(prior_span * 0.12, ch * 0.012)
        support_touches = int(np.sum(np.abs(look - prev_low_y) <= tol))
        resist_touches = int(np.sum(np.abs(look - prev_high_y) <= tol))
        up_double = min(1.0, support_touches / 3.0) * 0.50 + max(0.0, near_sup) * 0.24 + max(0.0, dirs[-1]) * 0.26
        dn_double = min(1.0, resist_touches / 3.0) * 0.50 + max(0.0, near_res) * 0.24 + max(0.0, -dirs[-1]) * 0.26
        add_signal("Double-Test Reversal", 1, up_double, "The lower boundary has been tested repeatedly and the latest candle reacts upward.")
        add_signal("Double-Test Reversal", -1, dn_double, "The upper boundary has been tested repeatedly and the latest candle reacts downward.")

    # 11) Momentum Burst — recent displacement expands versus prior movement.
    if count >= 10:
        prior_move = float(np.mean(np.abs(np.diff(ys[-10:-4])))) + 1e-6
        recent_move = float(np.mean(np.abs(np.diff(ys[-4:]))))
        expansion = float(np.clip((recent_move / prior_move - 0.9) / 1.3, 0.0, 1.0))
        up_mom = expansion * 0.42 + max(0.0, recent_strength) * 0.36 + max(0.0, last3_color) * 0.22
        dn_mom = expansion * 0.42 + max(0.0, -recent_strength) * 0.36 + max(0.0, -last3_color) * 0.22
        add_signal("Momentum Burst", 1, up_mom, "Recent bullish displacement has expanded versus the preceding candles.")
        add_signal("Momentum Burst", -1, dn_mom, "Recent bearish displacement has expanded versus the preceding candles.")

    # 12) Three-Candle Drive — three same-direction candles with directional path.
    if count >= 4:
        same_up = float(np.mean(dirs[-3:])) >= 0.66
        same_dn = float(np.mean(dirs[-3:])) <= -0.66
        path_up = ys[-1] < ys[-2] < ys[-3]
        path_dn = ys[-1] > ys[-2] > ys[-3]
        up_drive = (0.52 if same_up else 0.0) + (0.28 if path_up else 0.0) + max(0.0, recent_strength) * 0.20
        dn_drive = (0.52 if same_dn else 0.0) + (0.28 if path_dn else 0.0) + max(0.0, -recent_strength) * 0.20
        add_signal("Three-Candle Drive", 1, up_drive, "Three recent candles show a compact bullish drive with a rising visual path.")
        add_signal("Three-Candle Drive", -1, dn_drive, "Three recent candles show a compact bearish drive with a falling visual path.")

    # 13) Compression Breakout — quiet movement followed by directional expansion.
    if count >= 12:
        old_steps = np.abs(np.diff(ys[-12:-4]))
        new_steps = np.abs(np.diff(ys[-4:]))
        old_mean = float(np.mean(old_steps)) + 1e-6
        new_mean = float(np.mean(new_steps))
        release = float(np.clip((new_mean / old_mean - 1.0) / 1.5, 0.0, 1.0))
        old_quiet = float(np.clip(1.0 - np.std(old_steps) / max(ch * 0.02, 1.0), 0.0, 1.0))
        up_comp = release * 0.48 + old_quiet * 0.18 + max(0.0, recent_strength) * 0.20 + max(0.0, last3_color) * 0.14
        dn_comp = release * 0.48 + old_quiet * 0.18 + max(0.0, -recent_strength) * 0.20 + max(0.0, -last3_color) * 0.14
        add_signal("Compression Breakout", 1, up_comp, "A quieter candle cluster is releasing into stronger bullish displacement.")
        add_signal("Compression Breakout", -1, dn_comp, "A quieter candle cluster is releasing into stronger bearish displacement.")

    # 14) Exhaustion Reversal — abnormally large prior candle followed by opposite reaction.
    if count >= 8:
        med_range = float(np.median(ranges[-min(12, count):])) + 1e-6
        prior_range_ratio = float(ranges[-2] / med_range)
        stretch = float(np.clip((prior_range_ratio - 1.35) / 1.25, 0.0, 1.0))
        prior_dir = float(dirs[-2])
        last_dir = float(dirs[-1])
        up_exhaust = stretch * 0.52 + max(0.0, -prior_dir) * 0.18 + max(0.0, last_dir) * 0.30
        dn_exhaust = stretch * 0.52 + max(0.0, prior_dir) * 0.18 + max(0.0, -last_dir) * 0.30
        add_signal("Exhaustion Reversal", 1, up_exhaust, "A stretched bearish candle is followed by a bullish reversal response.")
        add_signal("Exhaustion Reversal", -1, dn_exhaust, "A stretched bullish candle is followed by a bearish reversal response.")

    # 15) Range Rotation — in sideways conditions, movement rotates away from one edge.
    if len(base) >= 4 and abs(trend_strength) < 0.26:
        current_pos = float(np.clip((float(ys[-1]) - prev_high_y) / max(prior_span, 1.0), 0.0, 1.0))
        # y=0 near visual resistance/high, y=1 near support/low.
        up_rot = max(0.0, current_pos - 0.56) * 1.8 * 0.52 + max(0.0, dirs[-1]) * 0.28 + max(0.0, recent_strength) * 0.20
        dn_rot = max(0.0, 0.44 - current_pos) * 1.8 * 0.52 + max(0.0, -dirs[-1]) * 0.28 + max(0.0, -recent_strength) * 0.20
        add_signal("Range Rotation", 1, up_rot, "Sideways price is rotating upward from the lower half of the visible range.")
        add_signal("Range Rotation", -1, dn_rot, "Sideways price is rotating downward from the upper half of the visible range.")

    # Strategy ranking and directional confluence.
    signals.sort(key=lambda s: float(s["score"]), reverse=True)
    best = signals[0] if signals else None
    up_scores = [float(s["score"]) / 100.0 for s in signals if s["direction"] == "UP" and float(s["score"]) >= 48.0]
    dn_scores = [float(s["score"]) / 100.0 for s in signals if s["direction"] == "DOWN" and float(s["score"]) >= 48.0]
    up_vote = float(sum(up_scores))
    dn_vote = float(sum(dn_scores))
    confluence_direction = 1 if up_vote > dn_vote else -1 if dn_vote > up_vote else 0
    confluence_count = len(up_scores) if confluence_direction > 0 else len(dn_scores) if confluence_direction < 0 else 0

    direction_score = 0.48 * trend_strength + 0.30 * recent_strength + 0.14 * color_strength
    if confluence_direction:
        vote_edge = (up_vote - dn_vote) / max(up_vote + dn_vote, 1e-6)
        direction_score += 0.22 * float(np.clip(vote_edge, -1.0, 1.0))
    direction_score = float(np.clip(direction_score, -1.0, 1.0))

    candle_factor = min(1.0, count / 24.0)
    quality_factor = max(0.45, quality / 100.0)
    best_score = (float(best["score"]) / 100.0) if best else 0.0
    agreement = min(1.0, confluence_count / 3.0)
    confidence = (
        46.0
        + abs(direction_score) * 28.0
        + best_score * 12.0
        + agreement * 8.0
    ) * (0.82 + 0.18 * candle_factor) * (0.86 + 0.14 * quality_factor)
    confidence = round(max(0.0, min(93.0, confidence)), 1)

    # Explain core market structure.
    if trend_label == "BULLISH":
        reasons.append("Visible candle path is sloping upward across the chart region.")
    elif trend_label == "BEARISH":
        reasons.append("Visible candle path is sloping downward across the chart region.")
    else:
        reasons.append("Visible candle path is mostly sideways / mixed.")

    if momentum_label == "UP":
        reasons.append("Recent detected candles are positioned higher than the preceding group.")
    elif momentum_label == "DOWN":
        reasons.append("Recent detected candles are positioned lower than the preceding group.")
    else:
        reasons.append("Recent candle momentum is mixed.")

    if best:
        reasons.append(f"Best visual strategy: {best['name']} ({best['direction']}) at {best['score']:.0f}% setup score.")
    if confluence_count:
        reasons.append(f"{confluence_count} strategy confirmations agree on the same direction.")

    # Volatility is a filter, not a standalone direction signal.
    if volatility == "HIGH":
        warnings.append("High visual volatility detected; entry quality requires stronger confluence.")
    if quality < 45:
        warnings.append("Image quality is below the preferred threshold.")

    # Conservative gate for short-expiry binary-style visual scans:
    # require a clear strategy, sufficient image/candles, and directional agreement.
    best_dir = 1 if best and best["direction"] == "UP" else -1 if best and best["direction"] == "DOWN" else 0
    strategy_ok = bool(best and best_score >= 0.52)
    direction_agrees = bool(best_dir and np.sign(direction_score) == best_dir)
    confluence_ok = confluence_count >= 2 or best_score >= 0.72
    volatility_ok = volatility != "HIGH" or (best_score >= 0.66 and confluence_count >= 2)
    structure_ok = count >= 8 and quality >= 36 and abs(direction_score) >= 0.16

    no_trade = not (strategy_ok and direction_agrees and confluence_ok and volatility_ok and structure_ok)

    if no_trade:
        bias = "NO TRADE"
        confidence = round(min(confidence, 68.0), 1)
        if not strategy_ok:
            reasons.append("No visual strategy reached the minimum setup threshold.")
        elif not confluence_ok:
            reasons.append("Strategy confluence is too weak; waiting is preferred.")
        elif not direction_agrees:
            reasons.append("Strategy direction conflicts with the broader candle structure.")
        elif not volatility_ok:
            reasons.append("Volatility is too high for the current level of confirmation.")
        else:
            reasons.append("The setup does not pass the conservative entry filter.")
    else:
        bias = "UP BIAS" if best_dir > 0 else "DOWN BIAS"

    setup_quality = (
        "HIGH" if not no_trade and best_score >= 0.72 and confluence_count >= 3 and quality >= 60
        else "MEDIUM" if not no_trade
        else "LOW"
    )

    selected_strategy = best["name"] if best else "NO CLEAN STRATEGY"
    strategy_direction = best["direction"] if best else "NONE"
    strategy_score = round(best_score * 100.0, 1)

    return {
        "bias": bias,
        "confidence": confidence,
        "image_quality_score": quality,
        "detected_candles": count,
        "visual_trend": trend_label,
        "momentum": momentum_label,
        "volatility": volatility,
        "direction_score": round(direction_score, 3),
        "selected_strategy": selected_strategy,
        "strategy_direction": strategy_direction,
        "strategy_score": strategy_score,
        "confluence_count": int(confluence_count),
        "setup_quality": setup_quality,
        "strategy_signals": signals[:8],
        "strategy_library": "Classic TA 15-Setup Library",
        "strategy_library_size": 15,
        "reasons": reasons[:8],
        "warnings": warnings[:5],
        "indicator_status": {
            "Trend / EMA structure": f"Visual trend proxy: {trend_label}; exact EMA values require OHLC",
            "Momentum / RSI proxy": f"Visual momentum proxy: {momentum_label}; exact RSI is not fabricated",
            "MACD-style momentum": "Directional acceleration is estimated from recent candle displacement",
            "Bollinger-style volatility": f"Visual volatility regime: {volatility}; exact bands require OHLC",
            "Support / Resistance": "Recent visual range boundaries and rejection behaviour are evaluated",
            "Price Action": f"{count} candle-like structures analyzed",
        },
        "engine": "RAJA Classic TA Strategy Engine V4",
    }


@app.get("/")
def home():
    return send_from_directory(APP_DIR, "index.html")


@app.get("/manifest.json")
def manifest():
    return send_from_directory(APP_DIR, "manifest.json")


@app.get("/sw.js")
def sw():
    return send_from_directory(APP_DIR, "sw.js", mimetype="application/javascript")


@app.get("/health")
def health():
    return jsonify({
        "status": "ok",
        "app": "RAJA AI Chart Scanner",
        "version": "2.0.0",
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
    if not key or not user or not device:
        return jsonify({"status": "error", "message": "Key, user/UID and device are required."}), 400
    rec = get_license(key)
    if not rec or not rec.get("active"):
        return jsonify({"status": "error", "message": "Invalid or revoked license key."}), 401
    if _license_expired(rec):
        return jsonify({"status": "error", "message": "License expired. Renew access to continue."}), 401
    if _norm_user(rec.get("user_id")) != user:
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
        result = analyze_chart_image(raw)
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
