# ProTrack RC5 — Production release recovery & QA gate

## Verdict (login failure on `http://192.168.20.254/login`)

| Check | Result |
|-------|--------|
| Frontend (IIS static / SPA) | Up — login page loads |
| `GET /api/v1/settings/public` via host | **502 Bad Gateway (IIS ARR)** |
| `POST /api/v1/auth/login` via host | **502 Bad Gateway** |
| Local API on developer PC (`127.0.0.1:8000`) | Healthy (not the production host) |

**Root cause:** IIS on `192.168.20.254` is serving the React app, but its reverse proxy to the FastAPI upstream is failing. This is **not** a wrong-password bug and not a React login-form bug.

Do not trust `http://192.168.20.254/health` alone — IIS SPA rewrite often returns the HTML shell with HTTP 200.

## Senior tester — restore API on `192.168.20.254` (blocking)

1. RDP / console onto `192.168.20.254`.
2. Confirm ARR / reverse-proxy target (usually `http://127.0.0.1:8000`).
3. On the server:
   ```text
   curl http://127.0.0.1:8000/health
   curl http://127.0.0.1:8000/api/v1/settings/public
   ```
4. If local upstream fails → start/restart the API Windows service or:
   ```powershell
   cd <ProTrack deploy dir>
   pip install -r requirements.txt
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
5. If local upstream works but browser still gets 502 → fix IIS ARR / `web.config` proxy port/path.
6. From any LAN PC:
   ```powershell
   .\scripts\check_release_health.ps1 -BaseUrl http://192.168.20.254
   ```
   Must print `RESULT: PASS` before functional testing continues.

### Deploy notes for this RC
- Restart API after pull (phase 19: `team_members.include_in_timesheet_reports`).
- Install `Pillow` (`requirements.txt`) for Excel logos.
- Publish rebuilt `frontend/dist`.
- Startup schema steps now log failures instead of hard-killing the process; still fix any logged step failures before UAT.

## Testing team — section-by-section (after health PASS)

| Section | Smoke checks |
|---------|--------------|
| Login / Auth | Login succeeds; wrong password → 401 message (not 502) |
| Dashboard | Loads; no error boundary |
| Projects | List + open detail |
| Timesheets | Month view; save entry |
| Reports (5 tabs) | Timesheet Reports, Engineering Overview, Project Hours, Team Reports, Customer Timesheet Pack |
| Period selectors | Week/Month/Quarter/Year dropdowns (no bare anchor-only UX) |
| Excel exports | Open file; company heading present |
| Users admin | “Include in timesheet reports” per team assignment saves |
| Exclude check | User with include=off absent from team timesheet report |
| Customer pack | Known customer/month shows hours when data exists |

## QC — audit before UAT

- [ ] `check_release_health.ps1` → PASS on `192.168.20.254`
- [ ] No 502/5xx on login or public settings
- [ ] Frontend build hash updated after publish
- [ ] API `/health` on **localhost:8000** shows expected RC
- [ ] Spot-check Excel + one excluded user
- [ ] Sign-off recorded → release for user testing (UAT)
