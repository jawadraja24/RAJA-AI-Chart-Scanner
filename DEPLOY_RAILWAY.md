# RoadPulse AI — Railway Live Deployment

## Files already prepared

This package is configured for Railway with:

- `railway.json`
- root `requirements.txt`
- `/api/status` health check
- admin password read from a secret environment variable
- configurable persistent data directory
- HTTPS secure admin cookie by default

## Exact steps

1. Create a new private GitHub repository.
2. Upload **the contents of this folder** to the repository root.
   The repository root should contain `backend/`, `web/`, `mobile/`,
   `railway.json`, and `requirements.txt`.

3. Sign in to Railway and choose **New Project → Deploy from GitHub repo**.
4. Select the RoadPulse repository.
5. In the RoadPulse service, open **Variables** and add:

   - `ROADPULSE_ADMIN_PASSWORD` = your private owner PIN/password
   - `ROADPULSE_SERVER_SECRET` = a long random secret string
   - `ROADPULSE_SECURE_COOKIE` = `1`
   - `ROADPULSE_DATA_DIR` = `/data`

6. Add a Railway **Volume** to this service and mount it at:

   `/data`

   This keeps SQLite reports, camera data, settings, and server files across
   restarts/redeployments.

7. Deploy/redeploy the service.

8. Open **Settings / Networking** and choose **Generate Domain**.

Your normal user URL will look like:

`https://your-name.up.railway.app/`

Your hidden owner entry is the same URL with:

`#admin`

Example:

`https://your-name.up.railway.app/#admin`

There is no visible admin navigation link in the normal user screen.

## Important

`#admin` is intentionally hidden from ordinary UI, but it is not a security
mechanism by itself. Server-side authentication is the real protection.

For production, add:
- 2FA
- login rate limiting
- audit logging
- PostgreSQL/PostGIS when traffic/community data grows
- proper end-user authentication
- privacy/consent flows
