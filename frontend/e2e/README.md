# Playwright E2E (frontend)

## Prerequisites
- Python env with ProTrack deps (API starts via Playwright `webServer`)
- Default login: `admin@prosohm.com` / `Password@123`

Global setup runs `scripts/create_admin_user.py` so that admin exists with the default password.
Override credentials with `E2E_EMAIL` / `E2E_PASSWORD` and set `E2E_SKIP_ADMIN_ENSURE=1` if you do not want the reset.

## Install browsers (once)
```bash
npx playwright install chromium
```

## Run
From `frontend/`:
```bash
npm run test:e2e
npm run test:e2e:headed
npm run test:e2e:ui
```

Playwright starts API (`:8000`) and Vite (`:5173`) unless already running (`reuseExistingServer`).

## Specs
- `auth.setup.ts` — admin storage state
- `login.spec.ts` — bad/good password
- `resource-planning.spec.ts` — Forecast / Reports / shift calendar modes
- `it-computers.spec.ts` — computers page (+ NICs dialog when present)
