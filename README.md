# RoadPulse AI — Starter Project

This starter implements the requested architecture:

- Normal users see only the user login screen.
- There is no visible Admin link in the normal UI.
- Visiting `https://your-domain.example/#admin` opens the hidden Admin login screen.
- Admin authentication is verified by the backend, not by JavaScript.
- The admin password is stored only as a salted PBKDF2 hash.
- The Admin panel contains starter controls for reports, cameras, users and app settings.
- The Flutter starter includes background-driving location scaffolding.

## Security

`#admin` is only a hidden entry point, not real security. Real protection is the
server-side login, HTTPS, secure cookies, rate limiting, and ideally 2FA.

Do not hard-code your admin PIN in HTML, JavaScript, Flutter code, or a public repository.

## Run the backend

```bash
cd backend
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
python setup_admin.py
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- User login: `http://localhost:8000/`
- Hidden admin: `http://localhost:8000/#admin`

When `setup_admin.py` asks for the admin password/PIN, enter your preferred PIN.
Only the hash is stored.

## Background driving mode

A browser/PWA alone should not be relied on for continuous navigation-style background
location. Use the native Flutter app for real driving mode.

For Android: use a foreground location service with a persistent notification.
For iOS: enable the Location background mode and Core Location background updates.

## Production checklist

- HTTPS only
- Rate-limit admin login and add temporary lockout
- Add 2FA/WebAuthn/TOTP
- PostgreSQL + PostGIS
- Audit logs for every admin change
- Separate Super Admin / Moderator / Support permissions
- Legal/country compliance rules for camera-warning behavior


## Live deployment

See `DEPLOY_RAILWAY.md` for the prepared Railway deployment steps.
