# Deployment update

See [DEPLOYMENT.md](DEPLOYMENT.md) for Vercel setup and [INTELLIGENCE.md](INTELLIGENCE.md) for model guardrails. The Gemini REST adapter is implemented but has not been tested with a live key.

# Kairo backend — Supabase integration

## Status

Supabase project: `gxscvzroxvugsrysejpr` (Singapore). The project Auth settings endpoint was reached successfully with the supplied publishable key; email authentication is enabled. No database password is stored in this repository. The migration has not yet been applied and a real signed-in user's session has not yet been tested.

## Next setup steps

1. Open the project's SQL Editor. Review and run `migrations/001_supabase.sql` once against the new database. It creates the record store, ownership index, and migration marker, enables RLS, and revokes direct table access from browser roles. It does not modify existing tables. If a table named `records` already exists, stop and prepare a migration for that schema instead.
2. Create a demo user in Authentication > Users. Set its password in the dashboard, not in chat. The user must have a confirmed email to sign in when email confirmation is required.
3. In the eventual Vercel backend project's environment settings, set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` from `.env.example`.
4. Privately set `DATABASE_URL` using the Transaction pooler URI. Use `postgresql+psycopg://`, the supplied project username/host/port, and the NEW password. Percent-encode password characters in a URL; do not wrap the password in brackets. Do not paste credentials in chat or commit them.
5. Deploy after adding the Vercel entrypoint/configuration. This repository has not been deployed yet. Configure Auth site URL and redirect allowlist once the website URL is known.
6. Verify the database schema, sign in as two separate test users, and run end-to-end isolation checks on the hosted deployment.

The publishable key is not a user access token. The future frontend signs in through Supabase Auth and sends the returned session access token as `Authorization: Bearer ...` to Kairo.

## Runtime and local tests

Python 3.11+. Install `requirements.lock.txt` in an isolated environment. Run `python -m pytest -q` from this directory. The environment prepared in this chat lives at `../../work/kairo-venv`.

Production requires explicit `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_PUBLISHABLE_KEY` environment variables. The application never defaults to SQLite. Start with `python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000` after setting those variables. `.env.example` is documentation only; the app does not automatically load it.

Tests explicitly inject an in-memory/file SQLite database and local test token, or mock Supabase's Auth endpoint. Test-token injection is rejected for PostgreSQL and on Vercel. Legacy `KAIRO_API_TOKEN` environment authentication has been removed. Old single-user SQLite files need a separate ownership migration; do not silently reuse them.

## Authentication and data access

- FastAPI validates user access tokens against this project's `/auth/v1/user` endpoint. Missing/invalid sessions return 401. Auth outages fail closed with 503.
- A request-local context carries only the verified user ID; no owner ID from client payloads is trusted.
- Every user-record query and update filters by that ID. Creation and idempotency records receive the same ownership scope.
- The API database connection is privileged, so explicit backend ownership checks are essential. RLS blocks direct browser access rather than granting browser writes that could bypass guardrails. No service-role API key is required.
- The AI budget remains an application-wide record, separate from user-owned data. Reserve calls must run inside the serialized transaction before provider attempts.
- PostgreSQL uses a one-connection application pool, no overflow, disabled automatic prepared statements, TLS, bounded connection timeouts, and transaction-level advisory locking. Migrations are separate from startup.

## API and behavior

See `openapi.json` or `/docs` for request schemas. `/health` is public; data endpoints require a user session. `/auth/me` returns the verified user ID.

- `/captures`: persist text pending AI interpretation.
- `/entries`: create/list drafts; retrieve and revise individual entries with version checks.
- `/entries/{id}/accept`: deterministic capacity checks and explicit risk acknowledgment.
- `/capacity/check`: previews using explicit availability windows.
- `/calendar/query`: accepted scheduled entries and daily/weekly occurrences.
- `/profile`: saved timezone and availability.
- `/reminders`, `/reminders/due`, `/reminders/{id}/actions`: foreground reminder polling, snooze, acknowledgment and telemetry.
- `/focus` and `/focus/{id}/stop`: persistent focus timestamps.
- `/entries/{id}/complete`: actual-work feedback; `/learning/duration`: category-based median suggestion and sample count.
- `/telemetry`: the current user's correction and decision history.

Create calls require `Idempotency-Key`; edits use `version`. Edits return commitments to draft/deferred and cancel pending reminders. The UI recreates reminders after reacceptance. Recurring reminder acknowledgment/dismissal advances to the next future occurrence, coalescing missed occurrences.

## Current boundaries

Gemini, frontend, Vercel deployment, and real PostgreSQL verification remain pending. No background push or audio delivery is implemented. Calendar recurrence uses fixed-offset daily/weekly timing, not DST-aware wall-clock scheduling. Capacity is bounded to a 31-day horizon and assumes flexible tasks are splittable. Unknown estimates remain incomplete. Duration suggestions use exact user-supplied categories; semantic matching and priority adaptation are future work.

The store is a small versioned JSON record envelope. Global transaction serialization prioritizes demo correctness, not high throughput. Account deletion cleanup, pagination, and sustained load testing remain future work.

## References

- https://supabase.com/docs/reference/python/auth-getuser
- https://supabase.com/docs/guides/database/connecting-to-postgres
- https://supabase.com/docs/guides/database/postgres/row-level-security
