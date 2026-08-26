from __future__ import annotations
import base64, getpass, hashlib, json, os
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
ADMIN_FILE = DATA_DIR / "admin.json"
ITERATIONS = 600_000

def hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return base64.b64encode(digest).decode()

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    password = getpass.getpass("Choose Admin password/PIN: ").strip()
    confirm = getpass.getpass("Confirm Admin password/PIN: ").strip()
    if password != confirm:
        raise SystemExit("Passwords do not match.")
    if len(password) < 4:
        raise SystemExit("Use at least 4 characters. Use a longer password + 2FA in production.")
    salt = os.urandom(16)
    payload = {
        "salt": base64.b64encode(salt).decode(),
        "hash": hash_password(password, salt),
        "iterations": ITERATIONS,
        "role": "super_admin",
    }
    ADMIN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Admin password stored as a salted hash. No plaintext password saved.")

if __name__ == "__main__":
    main()
